"""
The primary purpose of this module is to provide the tools needed to define and use bit structure definitions (blueprints) to translate between binary data and parsed data (python lists and values).

The goal is for a single blueprint to specify a bit structure and that no separate code needs to be written to extract vs construct binary data to/from python parsed data.

A blueprint can be either a string or a function with a specific signature.
A string blueprint is interpreted as a parsing pattern and can be used when the bit structure is fixed and no conditional branching or loops are required to extract the data.
Otherwise, a function blueprint is used. A function blueprint receives a single argument, by convention, called a tool. The tool may be an instance of either an Extractor class or a Constructor class. The former is used for extracting binary data to python variables. The latter is used for constructing binary data from python variables. From the perspective of designing the blueprint, it does not matter which of the two the tool is when the blueprint function is called. The tool is called with parsing patterns. Different patterns can be applied depending on conditionals and loops in normal python within the blueprint function.

For parsing pattern documentation, see the docstring for the pattern_parse() function.
"""
import re, ast, io, struct
from enum import Enum
from math import ceil
from .bits_io import SEEK_SET, SEEK_CUR, SEEK_END, uint_to_bytes, bytes_to_uint, BitsIO, reverse_bytes, invert_bytes
from .formats import from_hex

class Directive(Enum):
    """
    This enumeration defines the directives represented by different pattern tokens
    """
    VALUE = 1 #args = (num_bits, encoding)
    NEXT = 2 #args = (num_bits,)
    ZEROS= 3 #args = (num_bits,)
    ONES = 4 #args = (num_bits,)
    MOD = 5 #args = (num_bits,modify_type) 
    MODOFF = 6 #args = (offset_bits,num_bits,modify_type) 
    MODSET = 7 #args = (modify_type,setting)
    SETLABEL = 8 #args = (label,)
    DEFLABEL = 9 #args = (label,value)
    MATCHLABEL = 10 #args = (label,)
    NESTOPEN = 11 #args = (,)
    NESTCLOSE = 12 #args = (,)
    ASSERTION = 13 #args = (value,)
    TAKEALL = 14 #args = (,)
    MARKER = 15 #args = (byte_literal)

class Encoding(Enum):
    """
    This enumeration defines the value encodings available for VALUE pattern tokens
    """
    UINT = 1 #unsigned integer
    SINT = 2 #signed 2's complement integer
    SPFP = 3 #single precision floating point
    DPFP = 4 #double precision floating point
    LHEX = 5 #lower case hex string 
    UHEX = 6 #upper case hex string 
    BINS = 7 #bin string
    BYTS = 8 #bytes object

class ModType(Enum):
    """
    This enumeration defines the modify types available for MOD and MODSET directives
    """
    REVERSE=1
    INVERT=2
    ENDIANSWAP=3
    PULL=4
    

class Setting(Enum):
    """
    This enumeration defines the setting values available for MODSET directives
    """
    FALSE=0
    TRUE=1
    TOGGLE=2


def pattern_parse(pattern):
    """
    Interprets the provided pattern into a sequence of directives and arguments.

    Yields tuples where the first element is the matched token string, the second is the directive enum value, and the rest are the arguments for that directive.

    In the expressions defining tokens below, <n> is to be replaced with an unsigned integer value.
    e.g. u<n> would be written in an actual pattern as u5 or u100.

    Data value tokens:
        u<n> = Represents an unsigned integer that is n bits long.
        s<n> = Represents a signed integer that is n bits long.
        f32 = Represents a single-precision floating point value (32 bits long).
        f64 = Represents a double-precision floating point value (64 bits long).
        x<n> = Represents a hex string (lower case) that is n bits long.
        X<n> = Represents a hex string (upper case) that is n bits long.
        b<n> = Represents a bin string that is n bits long.
        B<n> = Represents a bytes object that is n bits long.
        
    Stream modifiers:
        r<n> = Reverse the next n bits without moving the seek position
        i<n> = Invert the next n bits without moving the seek position
        r<m>.<n> = Reverse the n bits that are offset forward from the current seek position by m bits. Does not move the seek position
        r<m>.! = Reverse the remaining bits that are offset forward from the current seek position by m bits. Does not move the seek position. Inserts the calculated value of n into the data structure during extraction mode. Uses the value of n in the data structure during construction mode.
        i<m>.<n> = Invert the n bits that are offset forward from the current seek position by m bits. Does not move the seek position
        i<m>.! = Inverts the remaining bits that are offset forward from the current seek position by m bits. Does not move the seek position. Inserts the calculated value of n into the data structure during extraction mode. Uses the value of n in the data structure during construction mode.
        e<n> = Endian swap. n must be a multiple of 8. Equivalent to reversing all n bits and then individually reversing each byte. Does not move the seek position.

    Lengthless tokens:
        B! = Represents the rest of the data stream. Translates to a triplet [byte_data,first_byte_value, first_byte_bits]. The second two parameters represent the remainder of the current byte while the first parameter is the byte data after.
        r! = Reverses all bits between the current position and the end of the set of data.
        i! = Inverts all bits between the current position and the end of the set of data.

    In the expressions defining the following tokens, <t|y|n> refers to any of the three letters "t", "y", or "n".
        "y" is interpreted as yes or True
        "n" is interpreted as no or False
        "t" is interpreted as toggle from the current value i.e. yes -> no and no -> yes

    Setting tokens:
        R<t|y|n>  = Reverse all setting. When enabled, each read is preceded by a reversal for the same number of bits. e.g. u<n> is treated as r<n>u<n>
        I<t|y|n> = Invert all setting. When enabled, each read is preceded by an inversion for the same number of bits. e.g. u<n> is treated as i<n>u<n>

    Non-value consuming tokens:
        z<n> = Represents a sequence of zeros n bits long
        o<n> = Represents a sequence of ones n bits long
        n<n> = The next n bits are don't cares that are skipped in extracting and assumed zero in constructing

    Value Nesting:
        [...] = Signify structural nesting

    Labels assignment:
        #"<label>" = Associate the previously parsed value with the label specified between the double quotes. Label names can consist of any characters besides the double quote character.
        !#"<label>"=<python_expr>; = Evaluate the python expression and associate it with the label. The label may not contain a double quote character. The python expression may not contain a semi-colon. The expression should be a python literal, not refer to a variable.

    Assertions:
        =<python_expr>; = Assert the previously parsed value, decoded to final form (e.g. hex) is equal to the evaluation of the provided python expression. The python expression must not contain a semi-colon nor a pound sign (#). The expression should be a python literal, not refer to a variable.
        =#"<label>" = Assert the previously parsed value, decoded to final form (e.g. hex) is equal to the most recent value associated with the provided label

    Repetition:
        {<pattern>}<n> = Repeat the pattern n times

    Comments:
        ##<any string> 

    Pull:
        p<m>.<n> = Pulls the block of data offset that is forward by m bits and is length n to the current seek position. Equivalent to r<m+n> r<n> r<m>.<n>
        p<m>.! = Sets n to correspond to the remainder of the data following the m offset.
            Equivalent to calculating the full stream length L and setting n = L-m, then performing p<m>.<n>. Inserts the computed n value into the data structure, which is used for construction.

    Marker:
        m"<hex_literal>" =  In extraction mode, scan forward in bytes until bytes matching the given hex literal is found. When invoked, the current bit seek position must be on a byte boundary (i.e. a multiple of 8).The hex literal must correspond to a whole number of bytes (i.e. an even number of hex characters). When found, the extractor will perform a pull operation on the matched pattern, move the seek position past it, and return a data value equal to the number of bits that were traversed during the scan. If this pattern is found at a bit offset m relative to what was the curret bit seek position, and n is the size in bits of the literal, then this operation is equivalent to p<m>.<n> n<n> and having the value m being inserted into the data structure (extracted list structure). In construction mode, the literal is inserted into the byte stream and pushed using the m value from the data structure. 
    """
    pos = 0
    tok_parse = re.compile('\\s*([rip]\\d+\\.(?:\\d+|!)|[usfxXbBnpjJrizo]\\d+|[RI][ynt]|!#"|#["#]|=#"|[\\[\\]=\\{\\}]|[riB]!|m")')
    label_parse = re.compile('([^"]+)"')
    space_equals_parse = re.compile('\\s*=')
    expr_parse = re.compile('([^;]+);')
    num_parse = re.compile('\\d+')
    comment_parse = re.compile('.+\n',re.S)
    hex_parse = re.compile('([A-F0-9a-f]+)\"')

    no_arg_codes = {
            '[': Directive.NESTOPEN,
            ']': Directive.NESTCLOSE,
            }
    num_codes = {
            'z':Directive.ZEROS,
            'o':Directive.ONES,
            'n':Directive.NEXT,
            }
    modoff_codes = {
            'r':(Directive.MOD,ModType.REVERSE),
            'i':(Directive.MOD,ModType.INVERT),
            'p':(Directive.MOD,ModType.PULL),
            }
    setting_codes = {
            'R':(Directive.MODSET,ModType.REVERSE),
            'I':(Directive.MODSET,ModType.INVERT),
            }
    num_and_arg_codes = {
            'u':(Directive.VALUE,Encoding.UINT),
            's':(Directive.VALUE,Encoding.SINT),
            'x':(Directive.VALUE,Encoding.LHEX),
            'X':(Directive.VALUE,Encoding.UHEX),
            'b':(Directive.VALUE,Encoding.BINS),
            'B':(Directive.VALUE,Encoding.BYTS),
            'r':(Directive.MOD,ModType.REVERSE),
            'i':(Directive.MOD,ModType.INVERT),
            }
    negate_num_codes = set('Jp')
    setting_map = {
            'y':Setting.TRUE,
            'n':Setting.FALSE,
            't':Setting.TOGGLE,
            }

    tokmatch = tok_parse.match(pattern,pos)

    repetition_stack = []

    while tokmatch is not None:
        tok = tokmatch.group(1)
        code = tok[0]

        instruction = None
        
        if '.' in tok: #MODOFF
            if '!' in tok: #MODOFF with !
                m = int(tok[1:].split('.')[0])
                n = None
                directive,modtype = modoff_codes[code]
                instruction = (tok,directive,m,n,modtype)

            else: #MODOFF with numbers
                m,n = [int(x) for x in tok[1:].split('.')]
                directive,modtype = modoff_codes[code]
                instruction = (tok,directive,m,n,modtype)
        elif tok == 'B!': #TAKEALL
            instruction = (tok,Directive.TAKEALL)
        elif tok == 'r!': #MOD
            instruction = (tok,Directive.MOD,None,ModType.REVERSE)
        elif tok == 'i!': #MOD
            instruction = (tok,Directive.MOD,None,ModType.REVERSE)
        elif code in num_and_arg_codes: #VALUE, MOD
            directive,arg = num_and_arg_codes[code]
            n = int(tok[1:])
            if code in negate_num_codes:
                n = -n
            if code == 'e':
                if n % 8 != 0:
                    raise Exception('"e" tokens must have a size that is a multiple of 8 bits: %s' % tok)
            instruction = (tok,directive,n,arg)
        elif code in no_arg_codes: #NESTOPEN, NESTCLOSE
            directive = no_arg_codes[code]
            instruction = (tok,directive)
        elif code in setting_codes: #MODSET
            directive,modtype = setting_codes[code]
            setting = setting_map[tok[1]]
            instruction = (tok,directive,modtype,setting)
        elif code in num_codes: #ZEROS, ONES, NEXT
            directive= num_codes[code]
            n = int(tok[1:])
            instruction = (tok,directive,n)
        elif tok == '#"': #SETLABEL
            labelmatch = label_parse.match(pattern,pos+2)
            pos = labelmatch.end(0)
            label = labelmatch.group(1)
            instruction = (tok+labelmatch.group(0),Directive.SETLABEL,label)
        elif tok == '!#"': #DEFLABEL
            labelmatch = label_parse.match(pattern,pos+3)
            pos = labelmatch.end(0)
            label = labelmatch.group(1)
            space_equals_match = space_equals_parse.match(pattern,pos)
            pos = space_equals_match.end(0)
            expr_match = expr_parse.match(pattern,pos)
            pos = expr_match.end(0)
            expr = expr_match.group(1)
            value = ast.literal_eval(expr)
            instruction = (tok+labelmatch.group(0) + space_equals_match.group(0) + expr_match.group(0),Directive.DEFLABEL,label,value)

        elif tok == '=#"': #MATCHLABEL
            labelmatch = label_parse.match(pattern,pos+3)
            pos = labelmatch.end(0)
            label = labelmatch.group(1)
            instruction = (tok+labelmatch.group(0),Directive.MATCHLABEL,label)

        elif tok == '=': #ASSERTION 
            expr_match = expr_parse.match(pattern,pos)
            pos = expr_match.end(0)
            expr = expr_match.group(1)
            value = ast.literal_eval(expr)
            instruction = (tok+expr_match.group(0),Directive.ASSERTION,value)
        elif tok == '{': #REPETITION CAPTURE START
            new_capture = [None] #first element is how many times to repeat; initialized to None and filled out when capture is complete
            if len(repetition_stack) > 0: #if nested repetition, need to connect previous capture to this new one
                repetition_stack[-1].append(new_capture)
            repetition_stack.append(new_capture) #new capture is focus now
        elif tok == '}': #REPETITION CAPTURE END
            repetition_capture = repetition_stack.pop(-1)
            num_match = num_parse.match(pattern,pos) #collect number
            pos = num_match.end(0)
            repetition_capture[0] = int(num_match.group(0)) #population first element with repetition number
            if len(repetition_stack) == 0: #if all repetitions are done
                yield from _process_repetition_capture(repetition_capture)
        elif tok == '##': #COMMENT
            comment_match = comment_parse.match(pattern,pos)
            pos = expr_match.end(0)
        elif tok == 'm"': #MARKER
                hexmatch = hex_parse.match(pattern,pos+2)
                pos = hexmatch.end(0)
                hex_literal = hexmatch.group(1)
                byte_literal = from_hex(hex_literal)
                instruction = (tok+hexmatch.group(0),Directive.MARKER,byte_literal)

        else:
            raise Exception('Unknown token: %s' % tok)

        if instruction is not None:
            if len(repetition_stack) > 0:
                repetition_stack[-1].append(instruction)
            else:
                yield instruction
        tokmatch = tok_parse.match(pattern,pos)
        if tokmatch is not None:
            pos = tokmatch.end(0)
def _process_repetition_capture(repetition_capture):
    count = repetition_capture[0]
    for iteration in range(count):
        for item in repetition_capture[1:]:
            if isinstance(item,list):
                yield from _process_repetition_capture(item)
            else:
                yield item

def uint_decode(uint_value,num_bits,encoding):
    """
    Takes a uint value and decodes (interprets) it according to a supported encoding scheme
    """
    if encoding == Encoding.UINT:
        return uint_value
    elif encoding == Encoding.SINT:
        msb = (1<<(num_bits-1))
        if uint_value >= msb:
            return uint_value - (1<<num_bits)
        else:
            return uint_value
    elif encoding == Encoding.SPFP:
        #1 sign bit, 8 exponent bits, 23 mantissa bits
        #uint_value,mantissa = divmod(uint_value,1<<23)
        #sign,exponent = divmod(uint_value,1<<8)
        #return (float(mantissa)/(1<<23)+1)*(1<<(exponent-127))*(-1)**sign
        if num_bits != 32:
            raise Exception('Single Precision Floating Point values must be 32 bits')
        return struct.unpack('>f',uint_to_bytes(uint_value,num_bits))[0]
    elif encoding == Encoding.DPFP:
        #1 sign bit, 11 exponent bits, 52 mantissa bits
        #uint_value,mantissa = divmod(uint_value,1<<52)
        #sign,exponent = divmod(uint_value,1<<11)
        #return (float(mantissa)/(1<<52)+1)*(1<<(exponent-1023))*(-1)**sign
        if num_bits != 64:
            raise Exception('Double Precision Floating Point values must be 64 bits')
        return struct.unpack('>d',uint_to_bytes(uint_value,num_bits))[0]
    elif encoding == Encoding.LHEX:
        num_hex_digits = int(ceil(num_bits/4.0))
        return (('%%0%dx' % num_hex_digits) % uint_value)
    elif encoding == Encoding.UHEX:
        num_hex_digits = int(ceil(num_bits/4.0))
        return (('%%0%dX' % num_hex_digits) % uint_value)
    elif encoding == Encoding.BINS:
        return ('{:0%db}' % num_bits).format(uint_value)
    elif encoding == Encoding.BYTS:
        num_total_bits = num_bits + (num_bits % 8)
        return uint_to_bytes(uint_value,num_total_bits)

def uint_encode(value,num_bits,encoding):
    """
    Takes a value and encodes it into a uint according to a supported encoding scheme

    >>> uint_encode('000101',6,Encoding.BINS)
    5
    >>> uint_decode(5,6,Encoding.BINS)
    '000101'
    >>> ord('A')
    65
    >>> uint_decode(65,8,Encoding.BYTS)
    b'A'
    >>> import struct, math
    >>> from formats import to_hex
    >>> to_hex(struct.pack('>f',math.pi))
    b'40490fdb'
    >>> '%08x' % uint_encode(math.pi,32,Encoding.SPFP)[0]
    '40490fdb'

    >>> 
    >>> import struct, math
    >>> from formats import to_hex
    >>> to_hex(struct.pack('>d',math.pi))
    b'400921fb54442d18'
    >>> '%08x' % uint_encode(math.pi,64,Encoding.DPFP)
    Traceback (most recent call last):
      File "<console>", line 1, in <module>
    TypeError: not all arguments converted during string formatting
    >>> '%08x' % uint_encode(math.pi,64,Encoding.DPFP)[0]
    '400921fb54442d18'
    >>> Encoding
    <enum 'Encoding'>
    >>> dir(Encoding)
    ['BINS', 'BYTS', 'DPFP', 'LHEX', 'SINT', 'SPFP', 'UHEX', 'UINT', '__class__', '__doc__', '__members__', '__module__']
    >>> uint_encode(777,Encoding.BINS)
    Traceback (most recent call last):
      File "<console>", line 1, in <module>
    TypeError: uint_encode() missing 1 required positional argument: 'encoding'
    >>> uint_encode(777,32,Encoding.BINS)
    Traceback (most recent call last):
      File "<console>", line 1, in <module>
      File "/storage/emulated/0/Code/bitweaver/bitweaver/pattern.py", line 390, in uint_encode
        return int(value,2)
    TypeError: int() can't convert non-string with explicit base
    >>> uint_encode('110010100101',32,Encoding.BINS)
    3237
    >>> uint_encode('111111',6,Encoding.SINT)
    Traceback (most recent call last):
      File "<console>", line 1, in <module>
      File "/storage/emulated/0/Code/bitweaver/bitweaver/pattern.py", line 379, in uint_encode
        if value >= 0:
    TypeError: '>=' not supported between instances of 'str' and 'int'
    >>> uint_encode(-1,6,Encoding.SINT)
    63
    """
    if encoding == Encoding.UINT:
        return value
    elif encoding == Encoding.SINT:
        if value >= 0:
            return value
        else:
            return value + (1<<num_bits)
    elif encoding == Encoding.SPFP:
        return bytes_to_uint(struct.pack('>f',value))
    elif encoding == Encoding.DPFP:
        return bytes_to_uint(struct.pack('>d',value))
    elif encoding == Encoding.LHEX or encoding == Encoding.UHEX:
        return int(value,16)
    elif encoding == Encoding.BINS:
        return int(value,2)
    elif encoding == Encoding.BYTS:
        return bytes_to_uint(value)

class ZerosError(Exception):pass
class OnesError(Exception):pass
class AssertionError(Exception):pass
class IncompleteDataError(Exception):pass
class MatchLabelError(Exception):pass
class NestingError(Exception):pass

def flatten(data_obj):
    """
    The flatten function takes a nested data structure (list of lists of lists etc) and returns a flattened version of it (list of values) as well as a flatten pattern that stores the nesting information.

    >>> flatten([1,'abc',[0,[1,1,[5]],'def'],9,10,11])
    ([1, 'abc', 0, 1, 1, 5, 'def', 9, 10, 11], '..[.[..[.]].]...')
    """
    flat_list = []
    flat_pattern = []
    stack = [[data_obj,0]]
    while len(stack) > 0:
        target,pos = stack[-1]
        if pos >= len(target):
            stack.pop(-1)
            flat_pattern.append(']')
        else:
            item = target[pos]
            stack[-1][1] += 1
            if isinstance(item,(list,tuple)):
                stack.append([item,0])
                flat_pattern.append('[')
            else:
                flat_list.append(item)
                flat_pattern.append('.')
    flat_pattern.pop(-1)
    return flat_list,''.join(flat_pattern)
def deflatten(flat_pattern,flat_list):
    """
    The deflatten function takes a flat data structure (list of values) and a flatten pattern, and produces a nested data structure according to those inputs.
    This is the inverse function of flatten()
    >>> deflatten([1, 'abc', 0, 1, 1, 5, 'def', 9, 10, 11], '..[.[..[.]].]...')
    [1, 'abc', [0, [1, 1, [5]], 'def'], 9, 10, 11]
    """
    data_obj = []
    stack = [data_obj]
    pos = 0
    for token in flat_pattern:
        if token == '[':
            new_record = []
            stack[-1].append(new_record)
            stack.append(new_record)
        elif token == ']':
            stack.pop(-1)
        elif token == '.':
            stack[-1].append(flat_list[pos])
            pos += 1
    return data_obj
def get_flat_index(flat_pattern,nested_indices):
    nested_indices = list(nested_indices)
    cumulative_index = 0
    index_stack = [0]
    target_index = nested_indices.pop(0)
    last_index = len(nested_indices) == 0
    skip_level = None
    for p in flat_pattern:
        if p == '[':
            if not last_index and target_index == index_stack[-1]:
                target_index = nested_indices.pop(0)
                last_index = len(nested_indices) == 0
            else:
                skip_level = len(index_stack)
            index_stack.append(0)
        elif p == '.':
            if last_index and target_index == index_stack[-1]:
                return cumulative_index
            index_stack[-1] += 1
            cumulative_index += 1
        elif p == ']':
            index_stack.pop(-1)
            index_stack[-1] += 1
            if skip_level is not None and len(index_stack) == skip_level:
                skip_level = None
        
def get_nested_indices(flat_pattern,flat_index):
    index_stack = [0]
    cumulative_index = 0
    for p in flat_pattern:
        if p == '[':
            index_stack.append(0)
        elif p == '.':
            if cumulative_index == flat_index:
                return index_stack
            index_stack[-1] += 1
        elif p == ']':
            index_stack.pop(-1)
            index_stack[-1] += 1



class Tool():
    """
    This is a common base class for the Extractor and Constructor classes.
    The __init__(), __call__(), and handle_...() functions must be implemented by each subclass.
    """
    def __init__(self,data_source):
        """
        Initialize the tool object with a data source
        """
        raise NotImplementedError
        self.labels = {}
    def __call__(self,pattern):
        """
        Apply the tool against the data source according to the provided pattern.
        Return the data record consisting of the values corresponding to the pattern data.
        """
        raise NotImplementedError
        return data_record
    def __getitem__(self,label):
        self.labels[label][-1][0]
    def __setitem__(self,label,value):
        self.labels[label].append((value,None,None))
    def __delitem__(self,label):
        del self.labels[label]


    def finalize(self):
        raise NotImplementedError

    def at_eof(self):
        return self.bits.at_eof()

    def __bytes__(self):
        return bytes(self.bits_io_obj)


class Extractor(Tool):
    """
    The Extractor takes binary bytes data and extracts data values out of it.
    """
    def __init__(self,bytes_io_obj):
        self.bytes_io_obj = bytes_io_obj
        self.bits_io_obj = BitsIO(bytes_io_obj)

        self.reverse_all = False
        self.invert_all = False

        self.last_value = None
        self.last_index_stack = None

        self.labels = {}

        self.flat_list = []
        self.flat_labels = []
        self.flat_pattern = [] #list of characters
        self.flat_pos = 0
        self.index_stack = [0]

        self.data_obj = []
        self.stack_data = [self.data_obj]

    def __call__(self,pattern):
        self.data_record = []
        self.stack_record = [self.data_record]

        for instruction in pattern_parse(pattern):
            tok = instruction[0]
            self.tok = tok
            directive = instruction[1]
            args = instruction[2:]
            method_name = 'handle_'+directive.name.lower()
            method = getattr(self,method_name)
            method(*args)
        return self.data_record

    def finalize(self):
        if len(self.stack_record) > 1:
            raise NestingError('There exists a "[" with no matching "]"')
        elif len(self.stack_record) < 1:
            raise NestingError('There exists a "]" with no matching "["')
        self.flat_pattern = ''.join(self.flat_pattern)

    def handle_value(self,num_bits,encoding):
        if self.reverse_all:
            self.bits_io_obj.reverse(num_bits)
        if self.invert_all:
            self.bits_io_obj.invert(num_bits)
        uint_value,num_extracted = self.bits_io_obj.read(num_bits)
        if num_extracted != num_bits:
            raise IncompleteDataError('Token = %s; Expected bits = %d; Extracted bits = %d' % (self.tok,num_bits,num_extracted))
        value = uint_decode(uint_value,num_bits,encoding)

        self.stack_record[-1].append(value)
        self.stack_data[-1].append(value)
        self.last_value = value

        self.flat_pattern.append('.')
        self.flat_list.append(value)
        self.flat_labels.append(None)
        self.flat_pos += 1
        self.last_index_stack = tuple(self.index_stack)
        self.index_stack[-1] += 1
        return value

    def handle_takeall(self):
        if self.reverse_all:
            self.bits_io_obj.reverse()
        if self.invert_all:
            self.bits_io_obj.invert()
        bytes_data,first_byte_value,first_byte_bits = self.bits_io_obj.read_bytes()
        values = [first_byte_value,first_byte_bits,bytes_data]
        self.stack_record[-1].append(values)
        self.stack_data[-1].append(values)
        self.last_value = bytes_data
        self.flat_pattern.extend('[...]')
        self.flat_list.extend(values)
        self.flat_labels.extend([None,None,None])
        self.flat_pos += 3
        self.last_index_stack = tuple(self.index_stack)
        self.index_stack[-1] += 1
        return value

    def handle_next(self,num_bits):
        self.bits_io_obj.seek(num_bits,SEEK_CUR) #these bits are don't cares

    def handle_zeros(self,num_bits):
        if self.reverse_all:
            self.bits_io_obj.reverse(num_bits)
        if self.invert_all:
            self.bits_io_obj.invert(num_bits)
        value,num_extracted = self.bits_io_obj.read(num_bits)
        if num_extracted != num_bits:
            raise IncompleteDataError('Token = %s; Expected bits = %d; Extracted bits = %d' % (self.tok,num_bits,num_extracted))
        if value != 0:
            raise ZerosError('Token = %s; Expected all zeros; Extracted value = %d' % (self.tok,value))

    def handle_ones(self,num_bits):
        if self.reverse_all:
            self.bits_io_obj.reverse(num_bits)
        if self.invert_all:
            self.bits_io_obj.invert(num_bits)
        value,num_extracted = self.bits_io_obj.read(num_bits)
        if num_extracted != num_bits:
            raise IncompleteDataError('Token = %s; Expected bits = %d; Extracted bits = %d' % (self.tok,num_bits,num_extracted))
        all_ones = (1<<num_bits)-1
        if value != all_ones:
            raise OnesError('Token = %s; Expected all ones (%d); Extracted value = %d' % (self.tok,all_ones,value))

    def handle_mod(self,num_bits,modtype):
        if modtype == ModType.REVERSE:
            self.bits_io_obj.reverse(num_bits)
        elif modtype == ModType.INVERT:
            self.bits_io_obj.invert(num_bits)
        elif modtype == ModType.ENDIANSWAP:
            pos = self.bits_io_obj.tell()
            self.bits_io_obj.reverse(num_bits)
            for i in range(0,num_bits,8):
                self.bits_io_obj.reverse(8)
                self.bits_io_obj.seek(8,SEEK_CUR)
            self.bits_io_obj.seek(pos)
        else:
            raise Exception('Token = %s; Invalid modtype: %s' % (self.tok,repr(modtype)))

    def handle_marker(self,bytes_literal):
        pos = self.bits_io_obj.tell()
        if pos % 8 != 0:
            raise Exception('Marker operation must occur when bit seek position is a multiple of 8')

        if self.invert_all:
            bytes_literal = invert_bytes(bytes_literal)
        if self.reverse_all:
            bytes_literal = reverse_bytes(bytes_literal)
        m = bits_offset = self.bits_io_obj.find(bytes_literal)
        num_bits = len(bytes_literal)*8

        value = m
        n = num_bits
        self.stack_record[-1].append(value)
        self.stack_data[-1].append(value)
        self.last_value = value

        self.flat_pattern.append('.')
        self.flat_list.append(value)
        self.flat_labels.append(None)
        self.flat_pos += 1
        self.last_index_stack = tuple(self.index_stack)
        self.index_stack[-1] += 1

        self.bits_io_obj.reverse(m+n)
        self.bits_io_obj.reverse(n)
        self.bits_io_obj.seek(n,SEEK_CUR)
        self.bits_io_obj.reverse(m)
        self.bits_io_obj.seek(pos+n)

    def handle_modoff(self,offset_bits,num_bits,modtype):
        pos = self.bits_io_obj.tell()
        if num_bits is None:
            L = len(self)
            num_bits = L - offset_bits
            self.stack_record[-1].append(num_bits)
            self.stack_data[-1].append(num_bits)
            self.last_value = num_bits

            self.flat_pattern.append('.')
            self.flat_list.append(num_bits)
            self.flat_labels.append(None)
            self.flat_pos += 1
            self.last_index_stack = tuple(self.index_stack)
            self.index_stack[-1] += 1


        if modtype == ModType.REVERSE:
            self.bits_io_obj.seek(offset_bits,SEEK_CUR)
            self.bits_io_obj.reverse(num_bits)
        elif modtype == ModType.INVERT:
            self.bits_io_obj.seek(offset_bits,SEEK_CUR)
            self.bits_io_obj.invert(num_bits)
        elif modtype == ModType.PULL:
            self.bits_io_obj.reverse(offset_bits+num_bits)
            self.bits_io_obj.reverse(num_bits)
            self.bits_io_obj.seek(num_bits,SEEK_CUR)
            self.bits_io_obj.reverse(offset_bits)
        else:
            raise Exception('Token = %s; Invalid modtype: %s' % (self.tok,repr(modtype)))
        self.bits_io_obj.seek(pos)

    def handle_modset(self,modtype,setting):
        if modtype == ModType.REVERSE:
            if setting == Setting.TRUE:
                self.reverse_all = True
            elif setting == Setting.FALSE:
                self.reverse_all = False
            elif setting == Setting.TOGGLE:
                self.reverse_all = not self.reverse_all
            else:
                raise Exception('Token = %s; Invalid setting: %s' % (self.tok,repr(setting)))
        elif modtype == ModType.INVERT:
            if setting == Setting.TRUE:
                self.invert_all = True
            elif setting == Setting.FALSE:
                self.invert_all = False
            elif setting == Setting.TOGGLE:
                self.invert_all = not self.invert_all
            else:
                raise Exception('Token = %s; Invalid setting: %s' % (self.tok,repr(setting)))
        else:
            raise Exception('Token = %s; Invalid modtype: %s' % (self.tok,repr(modtype)))

    def handle_setlabel(self,label):
        if not label in self.labels:
            self.labels[label] = []
        self.labels[label].append((self.last_value,self.last_index_stack,self.flat_pos-1))
        self.flat_labels[-1] = label

    def handle_deflabel(self,label,value):
        if not label in self.labels:
            self.labels[label] = []
        self.labels[label].append((self.last_value,None,None))

    def handle_matchlabel(self,label):
        if not label in self.labels:
            raise MatchLabelError('Token = %s; Label "%s" does not exist' % (self.tok,label))
        if self.last_value != self.labels[label][-1][0]:
            raise MatchLabelError('Token = %s; Last value of %s does not match value associated with Label "%s": %s ' % (self.tok,repr(self.last_value),label,repr(self.labels[label][-1][0])))

    def handle_nestopen(self):
        new_record = []
        self.stack_record[-1].append(new_record) #embed new record into the previous record
        self.stack_record.append(new_record) #make the new record the active record being worked on
        self.stack_extraction[-1].append(new_record) #embed new record into the previous record
        self.stack_extraction.append(new_record) #make the new record the active record being worked on
        self.flat_pattern.append('[')
        self.index_stack.append(0)

    def handle_nestclose(self):
        if len(self.stack_record) == 0:
            raise NestingError('there exists a "]" with no matching "["')
        self.stack_record.pop(-1) #stop modifying the current record and modify whatever one we were doing before it
        self.stack_extraction.pop(-1) #stop modifying the current record and modify whatever one we were doing before it
        self.flat_pattern.append(']')
        self.index_stack.pop(-1)
        self.index_stack[-1] += 1

    def handle_assertion(self,value):
        if self.last_value != value:
            raise AssertionError('Token = %s; Expected value = %s; Extracted value = %s' % (self.tok,repr(value),repr(self.last_value)))

class Constructor(Tool):
    """
    The Constructor class takes a sequence of values (nested or not), and constructs a byte sequence according to provided patterns.
    """
    def __init__(self,data_obj):
        self.data_obj = data_obj

        #Simply flatten the data obj. The order of traversal is what is important, not the structure.
        self.flat_list,self.flat_pattern = flatten(data_obj)
        self.flat_labels = [None]*len(self.flat_list)
        self.flat_pos = 0
        self.index_stack = [0]
        self.reverse_all = False
        self.invert_all = False
        self.last_value = None
        self.last_index_stack = None
        self.bytes_io_obj = io.BytesIO()
        self.bits_io_obj = bits_io.BitsIO(bytes_obj)
        self.labels = {}

    def __call__(self,pattern):
        self.data_record = []
        self.stack = [data_record]
        for instruction in pattern_parse(pattern):
            tok = instruction[0]
            self.tok = tok
            directive = instruction[1]
            args = instruction[2:]
            method_name = 'handle_'+directive.name.lower()
            method = getattr(self,method_name)
            method(*args)
        return self.data_record

    def finalize(self):
        if len(self.stack) > 1:
            raise NestingError('There exists a "[" with no matching "]"')
        elif len(self.stack) < 1:
            raise NestingError('There exists a "]" with no matching "["')

        #perform mod operations in reverse
        #   This works because there is no pattern ability to seek backwards or to an absolute position
        #   and because mod opererations modify positions in front of them without moving the seek position.
        #   Every extract that is impacted by a mod operation is therefore guaranteed to happen after that
        #   mod operation was performed during an extract. If the extract happened first, the seek position
        #   would have moved forward, and there would be no way to move backwards to make the mod operation
        #   affect those bits. Additionally, every sequence of bits is extracted exactly once.
        #   It is equivalent to imagine all mod operations happening together before any extraction operations,
        #   then performing all extraction operations. In construction context, this means that all construction
        #   operations can happen first without regard to mod operations happening, then performing all mod
        #   operations in reverse order to construct the original sequence of bits.
        pos = self.bits_io_obj.tell()
        for tok,modtype,start,offset,num_bits in self.mod_operations[::-1]:
            if modtype == ModType.REVERSE:
                self.bits_io_obj.seek(start+offset)
                self.bits_io_obj.reverse(num_bits)
            elif modtype == ModType.INVERT:
                self.bits_io_obj.seek(start+offset)
                self.bits_io_obj.invert(num_bits)
            elif modtype == ModType.PULL:
                #reverse order
                self.bits_io_obj.seek(start+num_bits)
                self.bits_io_obj.reverse(offset)
                self.bits_io_obj.seek(start)
                self.bits_io_obj.reverse(num_bits)
                self.bits_io_obj.reverse(offset+num_bits)
            else:
                raise Exception('Token = %s; Invalid modtype: %s' % (tok,repr(modtype)))
        self.bits_io_obj.seek(pos)
            
    def handle_value(self,num_bits,encoding):
        value = self.flat_list[self.flat_pos]
        self.flat_pos += 1
        self.data_record.append(value)
        uint_value = uint_encode(value,num_bits,encoding)
        pos = self.bits_io_obj.tell()
        if self.reverse_all:
            self.mod_operations.append(None,ModType.REVERSE,pos,0,num_bits)
        if self.invert_all:
            self.mod_operations.append(None,ModType.INVERT,pos,0,num_bits)
        self.bits_io_obj.write(uint_value,num_bits)
        self.last_value = value
        self.last_index_stack = tuple(self.index_stack)
        self.index_stack[-1] += 1

    def handle_takeall(self):
        first_byte_value,first_byte_bits,bytes_data = self.flat_list[self.flat_pos:self.flat_pos+3]
        self.flat_pos += 3
        self.data_record.append([first_byte_value,first_byte_bits,bytes_data])
        pos = self.bits_io_obj.tell()
        if self.reverse_all:
            self.mod_operations.append(None,ModType.REVERSE,pos,0,None)
        if self.invert_all:
            self.mod_operations.append(None,ModType.INVERT,pos,0,None)
        self.bits_io_obj.write_bytes(bytes_data,first_byte_value,first_byte_bits)
        self.last_value = bytes_data
        self.last_index_stack = tuple(self.index_stack)
        self.index_stack[-1] += 1

    def handle_next(self,num_bits):
        #bits are don't care - no reversals or inversions
        self.bits_io_obj.write(0,num_bits)

    def handle_zeros(self,num_bits):
        if self.reverse_all:
            self.mod_operations.append(None,ModType.REVERSE,pos,0,num_bits)
        if self.invert_all:
            self.mod_operations.append(None,ModType.INVERT,pos,0,num_bits)

        self.bits_io_obj.write(0,num_bits)

    def handle_ones(self,num_bits):
        if self.reverse_all:
            self.mod_operations.append(None,ModType.REVERSE,pos,0,num_bits)
        if self.invert_all:
            self.mod_operations.append(None,ModType.INVERT,pos,0,num_bits)
        all_ones = (1<<num_bits)-1
        self.bits_io_obj.write(all_ones,num_bits)

    def handle_mod(self,num_bits,modtype):
        #the bit stream does not fully exist yet, so store all reversals and inversions, then apply them at the end
        if modtype == ModType.REVERSE or modtype == ModType.INVERT:
            self.mod_operations.append((self.tok,mod_type,self.bits_io_obj.tell(),0,num_bits))
        elif modtype == ModType.ENDIANSWAP:
            #reverse order
            pos = self.bits_io_obj.tell()
            for i in range(0,num_bits,8)[::-1]:
                self.mod_operations.append((self.tok,ModType.REVERSE,pos,i,8))
            self.mod_operations.append((self.tok,ModType.REVERSE,pos,0,num_bits))

    def handle_marker(self,bytes_literal):
        num_bits = len(bytes_literal)*8

        offset_bits = self.flat_list[self.flat_pos]
        self.flat_pos += 1
        self.data_record.append(offset_bits)
        self.last_value = offset_bits
        self.last_index_stack = tuple(self.index_stack)
        self.index_stack[-1] += 1

        pos = self.bits_io_obj.tell()
        if pos % 8 != 0:
            raise Exception('Pull operation requires bit seek position to be a multiple of 8')
        self.mod_operations.append((self.tok,ModType.PULL,pos,offset_bits,num_bits))
        self.bits_io_obj.write(uint_encode(bytes_literal,num_bits,Encoding.BYTS),num_bits)
        if self.reverse_all:
            self.mod_operations.append(None,ModType.REVERSE,pos,0,num_bits)
        if self.invert_all:
            self.mod_operations.append(None,ModType.INVERT,pos,0,num_bits)
            

    def handle_modoff(self,offset_bits,num_bits,modtype):
        #the bit stream does not fully exist yet, so store all reversals and inversions, then apply them at the end
        if num_bits is None: #for when ! is in token
            num_bits = self.flat_list[self.flat_pos]
            self.flat_pos += 1
            self.data_record.append(num_bits)
            self.last_value = num_bits
            self.last_index_stack = tuple(self.index_stack)
            self.index_stack[-1] += 1
        pos = self.bits_io_obj.tell()
        self.mod_operations.append((self.tok,mod_type,pos,offset_bits,num_bits))

    def handle_modset(self,modtype,setting):
        if modtype == ModType.REVERSE:
            if setting == Setting.TRUE:
                self.reverse_all = True
            elif setting == Setting.FALSE:
                self.reverse_all = False
            elif setting == Setting.TOGGLE:
                self.reverse_all = not self.reverse_all
            else:
                raise Exception('Token = %s; Invalid setting: %s' % (self.tok,repr(setting)))
        elif modtype == ModType.INVERT:
            if setting == Setting.TRUE:
                self.invert_all = True
            elif setting == Setting.FALSE:
                self.invert_all = False
            elif setting == Setting.TOGGLE:
                self.invert_all = not self.invert_all
            else:
                raise Exception('Token = %s; Invalid setting: %s' % (self.tok,repr(setting)))
        else:
            raise Exception('Token = %s; Invalid modtype: %s' % (self.tok,repr(modtype)))

    def handle_setlabel(self,label):
        if not label in self.labels:
            self.labels[label] = []
        self.labels[label].append((self.last_value,self.last_index_stack,self.flat_pos-1))

    def handle_deflabel(self,label,value):
        self.labels[label].append((value,None,None))

    def handle_matchlabel(self,label):
        if not label in self.labels:
            raise MatchLabelError('Token = %s; Label "%s" does not exist' % (self.tok,label))
        if self.last_value != self.labels[label][-1][0]:
            raise MatchLabelError('Token = %s; Last value of %s does not match value associated with Label "%s": %s ' % (self.tok,repr(self.last_value),label,repr(self.labels[label][-1][0])))

    def handle_nestopen(self):
        new_record = []
        self.stack[-1].append(new_record) #embed new record into the previous record
        self.stack.append(new_record) #make the new record the active record being worked on
        self.index_stack.append(0)

    def handle_nestclose(self):
        if len(self.stack) == 0:
            raise nestingerror('there exists a "]" with no matching "["')
        self.stack.pop(-1) #stop modifying the current record and modify whatever one we were doing before it
        self.index_stack.pop(-1)
        self.index_stack[-1] += 1

    def handle_assertion(self,value):
        if self.last_value != value:
            raise AssertionError('Token = %s; Expected value = %s; Extracted value = %s' % (self.tok,repr(value),repr(self.last_value)))

def extract(blueprint_func,bytes_io_obj):
    tool = Extractor(bytes_io_obj)
    blueprint_func(tool)
    tool.finalize()
    return tool

def extract_data(blueprint_func,bytes_io_obj):
    tool = extract(blueprint_func,bytes_io_obj)
    return tool.data_obj

def construct(blueprint_func,data_obj):
    tool = Constructor(data_obj)
    blueprint_func(tool)
    tool.finalize()
    return tool

def construct_bytes(data_obj,blueprint_func):
    tool = construct(blueprint_func,data_obj)
    return bytes(tool)
