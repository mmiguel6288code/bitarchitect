import re, ast, io, struct
from enum import Enum
from math import ceil
import bits_io

SEEK_SET = bits_io.SEEK_SET
SEEK_CUR = bits_io.SEEK_CUR
SEEK_END = bits_io.SEEK_END

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

class Encoding(Enum):
    """
    This enumeration defines the value encodings available for VALUE pattern tokens
    """
    UINT = 1 #unsigned integer
    SINT = 2 #signed 2's complement integer
    SPFP = 3 #single precision floating point
    DBFP = 4 #double precision floating point
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

class Setting(Enum):
    """
    This enumeration defines the setting values available for MODSET directives
    """
    FALSE=0
    TRUE=1
    TOGGLE=2


def parse(pattern):
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
        i<m>.<n> = Invert the n bits that are offset forward from the current seek position by m bits. Does not move the seek position

    In the expressions defining the following tokens, <t|y|n> refers to any of the three letters "t", "y", or "n".
        "y" is interpreted as yes or True
        "n" is interpreted as no or False
        "t" is interpreted as toggle from the current value i.e. yes -> no and no -> yes

    Setting tokens:
        R<t|y|n>  = Reverse all setting. Settings are preserved from execution to execution of the same session.
        I<t|y|n> = Invert all setting. Settings are preserved from execution to execution of the same session.

    Non-value consuming tokens:
        z<n> = Represents a sequence of zeros n bits long
        o<n> = Represents a sequence of ones n bits long
        n<n> = The next n bits are don't cares that are skipped in extracting and assumed zero in constructing

    Value Nesting:
        [...] = Signify structural nesting. Each open nesting within a pattern should be closed.

    Labels assignment:
        #"<label>" = Associate the previously parsed value with the label specified between the double quotes. Label names can consist of any characters besides the double quote character.
        !#"<label>"=<python_expr>; = Evaluate the python expression and associate it with the label. The label may not contain a double quote character. The python expression may not contain a semi-colon. The expression should be a python literal, not refer to a variable.

    Assertions:
        =<python_expr>; = Assert the previously parsed value, decoded to final form (e.g. hex) is equal to the evaluation of the provided python expression. The python expression must not contain a semi-colon nor a pound sign (#). The expression should be a python literal, not refer to a variable.
        =#"<label>" = Assert the previously parsed value, decoded to final form (e.g. hex) is equal to the value associated with the provided label

    Repetition:
        {<pattern>}<n> = Repeat the pattern n times

    """
    pos = 0
    tok_parse = re.compile('\\s*([ri]\\d+\\.\\d+|[usfxXbBnpjJrizo]\\d+|[RI][ynt]|!#"|#"|=#"|[\\[\\]=\\{\\}]|B!')
    label_parse = re.compile('([^"]+)"')
    space_equals_parse = re.compile('\\s*=')
    expr_parse = re.compile('([^;]+);')
    num_parse = re.compile('\\d+')

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
    pos = tokmatch.end(0)

    repetition_stack = []

    while tokmatch is not None:
        tok = tokmatch.group(1)
        code = tok[0]

        instruction = None
        
        if '.' in tok: #MODOFF
            m,n = [int(x) for x in tok[1:].split('.')]
            directive,modtype = modoff_codes[code]
            instruction = (tok,directive,m,n,modtype)
        elif tok == 'B!': #TAKEALL
            instruction = (tok,Directive.TAKEALL)
        elif code in num_and_arg_codes: #VALUE, MOD
            directive,arg = num_and_arg_tokens[code]
            n = int(tok[1:])
            if code in negate_num_tokens:
                n = -n
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
                yield from process_repetition_capture(repetition_capture)
        else:
            raise Exception('Unknown token: %s' % tok)

        if instruction is not None:
            if len(repetition_stack) > 0:
                repetition_stack[-1].append(instruction)
            else:
                yield instruction
        tokmatch = tok_parse.match(pattern,pos)
        pos = tokmatch.end(0)
def process_repetition_capture(repetition_capture):
    count = repetition_capture[0]
    for iteration in range(count):
        for item in repetition_capture[1:]:
            if isinstance(item,list):
                yield from process_repetition_capture(item)
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
        return struct.unpack('f',bits_io.uint_to_bytes(uint_value,num_bits))[0]
    elif encoding == Encoding.DPFP:
        #1 sign bit, 11 exponent bits, 52 mantissa bits
        #uint_value,mantissa = divmod(uint_value,1<<52)
        #sign,exponent = divmod(uint_value,1<<11)
        #return (float(mantissa)/(1<<52)+1)*(1<<(exponent-1023))*(-1)**sign
        if num_bits != 64:
            raise Exception('Double Precision Floating Point values must be 64 bits')
        return struct.unpack('d',bits_io.uint_to_bytes(uint_value,num_bits))[0]
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
        return bits_io.uint_to_bytes(uint_value,num_total_bits)

def uint_encode(value,num_bits,encoding):
    """
    Takes a value and encodes it into a uint according to a supported encoding scheme
    """
    if encoding == Encoding.UINT:
        return value
    elif encoding == Encoding.SINT:
        if value >= 0:
            return value
        else:
            return value + (1<<num_bits)
    elif encoding == Encoding.SPFP:
        return bits_io.bytes_to_uint(struct.pack('f',value))
    elif encoding == Encoding.DPFP:
        return bits_io.bytes_to_uint(struct.pack('d',value))
    elif encoding == Encoding.LHEX or encoding == Encoding.UHEX:
        return int(value,16)
    elif encoding == Encoding.BINS:
        return int(value,2)
    elif encoding == Encoding.BYTS:
        return bits_io.bytes_to_uint(value)

class ZerosError(Exception):pass
class OnesError(Exception):pass
class AssertionError(Exception):pass
class IncompleteDataError(Exception):pass
class MatchLabelError(Exception):pass
class NestingError(Exception):pass

class Operator():
    """
    This is a common base class for the Extractor and Constructor classes.
    In both classes, the way the API for accessing label data is the same - basically treat the operator object as if it were a dictionary

    The __init__(), __call__(), results(), and handle_...() functions must be implemented by each subclass.
    """
    def __init__(self,data_source,labels=None):
        """
        Initialize the operator object with a data source and a labels dictionary
        """
        raise NotImplementedError
    def __call__(self,pattern):
        """
        Apply the operator against the data source according to the provided pattern.
        Return the data record consisting of the values corresponding to the pattern data.
        """
        raise NotImplementedError
        return data_record
    def results(self):
        """
        Return the cumulative results of all calls
        """
        raise NotImplementedError
    def at_eof(self):
        return self.bits.at_eof()
    def __getitem__(self,label):
        return self.labels[label]
    def __setitem__(self,label,value):
        self.labels[label] = value
    def __delitem__(self,label):
        del self.labels[label]
    def keys(self):
        yield from self.labels.keys()
    def items(self):
        yield from self.labels.items()
    def values(self):
        yield from self.labels.values()
    def __iter__(self):
        yield from self.labels
    def __len__(self):
        return len(self.labels)

class Extractor(Operator):
    """
    The Extractor takes binary bytes data and extracts data values out of it.
    """
    def __init__(self,bytes_obj,labels=None):
        self.bytes_obj = bytes_obj
        self.bits = bits_io.BitsIO(bytes_obj)
        self.reverse_all = False
        self.invert_all = False
        self.last_value = None
        if labels is None:
            labels = {}
        self.labels = labels
        self.data_extraction = []
        self.stack_extraction = [self.data_extraction]
    def __call__(self,pattern):
        self.data_record = []
        self.stack_record = [self.data_record]
        for instruction in parse(pattern):
            tok = instruction[0]
            self.tok = tok
            directive = instruction[1]
            args = instruction[2:]
            method_name = 'handle_'+directive.name.lower()
            method = getattr(self,method_name)
            method(*args)
        if len(self.stack_record) > 1:
            raise NestingError('There exists a "[" with no matching "]"')
        elif len(self.stack_record) < 1:
            raise NestingError('There exists a "]" with no matching "["')
    def results(self):
        return self.data_extraction

    def handle_value(self,num_bits,encoding):
        uint_value,num_extracted = self.bits.read(num_bits,reverse=self.reverse_all,invert=self.invert_all)
        if num_extracted != num_bits:
            raise IncompleteDataError('Token = %s; Expected bits = %d; Extracted bits = %d' % (self.tok,num_bits,num_extracted))
        value = uint_decode(uint_value,num_bits,encoding)
        self.stack_record[-1].append(value)
        self.stack_extraction[-1].append(value)
        self.last_value = value
        return value
    def handle_next(self,num_bits):
        self.bits.seek(num_bits,SEEK_CUR)
    def handle_zeros(self,num_bits):
        value,num_extracted = self.bits.read(num_bits,reverse=self.reverse_all,invert=self.invert_all)
        if num_extracted != num_bits:
            raise IncompleteDataError('Token = %s; Expected bits = %d; Extracted bits = %d' % (self.tok,num_bits,num_extracted))
        if value != 0:
            raise ZerosError('Token = %s; Expected all zeros; Extracted value = %d' % (self.tok,value))

    def handle_ones(self,num_bits):
        value,num_extracted = self.bits.read(num_bits,reverse=self.reverse_all,invert= not self.invert_all)
        if num_extracted != num_bits:
            raise IncompleteDataError('Token = %s; Expected bits = %d; Extracted bits = %d' % (self.tok,num_bits,num_extracted))
        if value != 0:
            raise OnesError('Token = %s; Expected all ones (inversion to be all zeros); Inversion of extracted value = %d' % (self.tok,value))
    def handle_mod(self,num_bits,modtype):
        if modtype == ModType.REVERSE:
            self.bits.reverse(num_bits)
        elif modtype == ModType.INVERT:
            self.bits.invert(num_bits)
        else:
            raise Exception('Token = %s; Invalid modtype: %s' % (self.tok,repr(modtype)))
    def handle_modoff(self,offset_bits,num_bits,modtype):
        pos = self.bits.tell()
        self.bits.seek(offset_bits,SEEK_CUR)
        if modtype == ModType.REVERSE:
            self.bits.reverse(num_bits)
        elif modtype == ModType.INVERT:
            self.bits.invert(num_bits)
        else:
            raise Exception('Token = %s; Invalid modtype: %s' % (self.tok,repr(modtype)))
        self.bits.seek(pos)

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
        self.labels[label] = self.last_value
    def handle_deflabel(self,label,value):
        self.labels[label] = value
    def handle_matchlabel(self,label):
        if not label in self.labels:
            raise MatchLabelError('Token = %s; Label "%s" does not exist' % (self.tok,label))
        if self.last_value != self.labels[label]:
            raise MatchLabelError('Token = %s; Last value of %s does not match value associated with Label "%s": %s ' % (self.tok,repr(self.last_value),label,repr(self.labels[label])))
    def handle_nestopen(self):
        new_record = []
        self.stack_record[-1].append(new_record) #embed new record into the previous record
        self.stack_record.append(new_record) #make the new record the active record being worked on
        self.stack_extraction[-1].append(new_record) #embed new record into the previous record
        self.stack_extraction.append(new_record) #make the new record the active record being worked on
    def handle_nestclose(self):
        if len(self.stack_record) == 0:
            raise NestingError('there exists a "]" with no matching "["')
        self.stack_record.pop(-1) #stop modifying the current record and modify whatever one we were doing before it
        self.stack_extraction.pop(-1) #stop modifying the current record and modify whatever one we were doing before it

    def handle_assertion(self,value):
        if self.last_value != value:
            raise AssertionError('Token = %s; Expected value = %s; Extracted value = %s' % (self.tok,repr(value),repr(self.last_value)))
    def handle_takeall(self):
        value = self.bits.remaining_bytes(reverse=self.reverse_all,invert=self.invert_all)
        self.stack_record[-1].append(value)
        self.stack_extraction[-1].append(value)
        self.last_value = value
        return value

def flatten(data_obj):
    """
    The flatten function takes a nested data structure (list of lists of lists etc) and returns a flattened version of it (list of values) as well as a flatten pattern that stores the nesting information.
    """
    flat = []
    pattern = []
    stack = [[data_obj,0]]
    while len(stack) > 0:
        target,pos = stack[-1]
        if pos >= len(target):
            stack.pop(-1)
            pattern.append(']')
        else:
            item = target[pos]
            stack[-1][1] += 1
            if isinstance(item,(list,tuple)):
                stack.append([item,0])
                pattern.append('[')
            else:
                flat.append(item)
                pattern.append('.')
    return flat,''.join(pattern)
def deflatten(flat,pattern):
    """
    The deflatten function takes a flat data structure (list of values) and a flatten pattern, and produces a nested data structure according to those inputs.
    This is the inverse function of flatten()
    """
    data_obj = []
    stack = [data_obj]
    pos = 0
    for token in pattern:
        if token == '[':
            new_record = []
            stack[-1].append(new_record)
            stack.append(new_record)
        elif token == ']':
            stack.pop(-1)
        elif token == '.':
            stack[-1].append(flat[pos])
            pos += 1
    return data_obj

        

class Constructor(Operator):
    """
    The Constructor class takes a sequence of values (nested or not), and constructs a byte sequence according to provided patterns.
    """
    def __init__(self,data_obj,labels=None):
        self.data_obj = data_obj

        #Simply flatten the data obj. The order of traversal is what is important, not the structure.
        self.flat,self.flat_pattern = flatten(data_obj)
        self.flat_pos = 0
        self.reverse_all = False
        self.invert_all = False
        self.last_value = None
        self.bytes_obj = io.BytesIO()
        self.bits = bits_io.BitsIO(bytes_obj)
        if labels is None:
            labels = {}
        self.labels = labels

    def __call__(self,pattern):
        self.data_record = []
        self.stack = [data_record]
        for instruction in parse(pattern):
            tok = instruction[0]
            self.tok = tok
            directive = instruction[1]
            args = instruction[2:]
            method_name = 'handle_'+directive.name.lower()
            method = getattr(self,method_name)
            method(*args)
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
        pos = self.bits.tell()
        for tok,modtype,start,num_bits in self.mod_operations[::-1]:
            self.bits.seek(start)
            if modtype == ModType.REVERSE:
                self.bits.reverse(num_bits)
            elif modtype == ModType.INVERT:
                self.bits.invert(num_bits)
            else:
                raise Exception('Token = %s; Invalid modtype: %s' % (tok,repr(modtype)))
        self.bits.seek(pos)
        if len(self.stack) > 1:
            raise NestingError('There exists a "[" with no matching "]"')
        elif len(self.stack) < 1:
            raise NestingError('There exists a "]" with no matching "["')
        return self.data_record
    def results(self):
        return self.bytes_obj
            
    def handle_value(self,num_bits,encoding):
        value = self.flat[self.flat_pos]
        self.flat_pos += 1
        self.data_record.append(value)
        uint_value = uint_encode(value,num_bits,encoding)
        self.bits.write(uint_value,num_bits,reverse=self.reverse_all,invert=self.invert_all)
        self.last_value = value
    def handle_next(self,num_bits):
        self.bits.seek(num_bits,SEEK_CUR)
    def handle_zeros(self,num_bits):
        self.bits.write(0,num_bits,reverse=self.reverse_all,invert=self.invert_all)
    def handle_ones(self,num_bits):
        self.bits.write(0,num_bits,reverse=self.reverse_all,invert=not self.invert_all)
    def handle_mod(self,num_bits,modtype):
        #the bit stream does not fully exist yet, so store all reversals and inversions, then apply them at the end
        self.mod_operations.append((self.tok,mod_type,self.bits.tell(),num_bits))
    def handle_modoff(self,offset_bits,num_bits,modtype):
        #the bit stream does not fully exist yet, so store all reversals and inversions, then apply them at the end
        self.mod_operations.append((self.tok,mod_type,self.bits.tell()+offset_bits,num_bits))
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
        self.labels[label] = self.last_value
    def handle_deflabel(self,label,value):
        self.labels[label] = value
    def handle_matchlabel(self,label):
        if not label in self.labels:
            raise MatchLabelError('Token = %s; Label "%s" does not exist' % (self.tok,label))
        if self.last_value != self.labels[label]:
            raise MatchLabelError('Token = %s; Last value of %s does not match value associated with Label "%s": %s ' % (self.tok,repr(self.last_value),label,repr(self.labels[label])))
    def handle_nestopen(self):
        new_record = []
        self.stack[-1].append(new_record) #embed new record into the previous record
        self.stack.append(new_record) #make the new record the active record being worked on
    def handle_nestclose(self):
        if len(self.stack) == 0:
            raise nestingerror('there exists a "]" with no matching "["')
        self.stack.pop(-1) #stop modifying the current record and modify whatever one we were doing before it

    def handle_assertion(self,value):
        if self.last_value != value:
            raise AssertionError('Token = %s; Expected value = %s; Extracted value = %s' % (self.tok,repr(value),repr(self.last_value)))
    def handle_takeall(self):
        value = self.flat[self.flat_pos]
        self.flat_pos += 1
        self.data_record.append(value)
        self.bits.write_remaining_bytes(value)
        self.last_value = value

class Blueprint():
    """
    The Blueprint class is intended to be subclassed into sublcasses that define a binary structure.
    The subclass can then be used to either extract data from a byte sequence or construct a byte sequence given data.


    Usage example: Zip local file header
        class ZipLocalFileHeader(Blueprint):
            \"\"\"
            See https://en.wikipedia.org/wiki/Zip_(file_format)#Local_file_header 
            \"\"\"
            @classmethod
            def definition(operator):
                operator('r32 r0.8 r8.8 r16.8 r24.8') #endian swap of first 32 bits - i.e. reverse next 32 bits, then reverse back each byte
                signature, = operator('x32 #"signature"') 
                    #This capture the zip header signature as hex string
                    #The return value of operator() contains all captured values
                    #The pattern #"<label>" is used to assign the previously extracted value to a label

                assert(signature == operator['signature']) #can treat operator like a dictionary to grab values that we assigned to labels

                #grab the next fixed length items
                fields = operator('''
                    {u16}5 {u32}3 
                    u16 #"filename_len" 
                    u16 #"extra_field_len"
                    ''')
                    #{<pattern>}<n> repeats the pattern n times

                #use the filename_len value to determine how many bits to grab an reinterpret as a bytes object (basically a string); "B" is for Bytes
                filename_pattern = 'B' + str(8*operator['filename_len'])
                operator(filename_pattern)

                #the extra field length is the number of bytes the extra field is made of. The extra field is composed of chunks with a 16 bit code and a 16 bit length
                m = operator['extra_field_len']
                num_chunks = m/4 #m bytes = m/4 chunks since each chunk is 32 bits
                extra_pattern = '{[u16 u16]}' + str(num_chunks) 
                    #the [ and ] characters inside denote that the two u16 values should be captured together (in their own sublist)
                operator('['+extra_pattern+']') #capture all the extra field chunks in a single large sublist

                operator('B!') #grab the rest of the file as a bytes object

        with open('somefile.zip','rb') as f:
            data = ZipLocalFileHeader.extract(f)
            #data[0] will be the signature
            ...
            #data[6] will be CRC-32
            ...
            #data[12] will be a list of pairs of ID codes and lengths corresponding to the extra field
            #data[13] will be a bytes object corresponding to the rest of the file

        data[6] = 0 #erase the CRC
        with open('badfile.zip','wb') as f:
            f.write(ZipLocalFileHeader.construct(data).getbuffer())
        #this writes an identical copy of the original zip file except that the CRC-32 is zeroed out





    Usage example: Endian swap
        class EndianSwapper32(Blueprint):
            @classmethod
            def definition(operator):
                while not operator.at_eof(): #repeat for all 32-bit words (i.e. until we run out of data)
                    operator('r32 r0.8 r8.8 r16.8 r24.8 B32') 
                        #reverse the next 32 bits, then re-reverses each byte within those 32 bits, then grabs the final modified 32 bits
        with open('somefile','rb') as f:
            swapped = b''.join(EndianSwapper32.extract(f))
        with open('swappedfile','wb') as f:
            f.write(swapped)





    """

def extract(bytes_obj,blueprint_func):
    operator = Extractor(bytes_obj)
    blueprint_func(operator)
    return operator.results()
def construct(data_obj,blueprint_func):
    operator = Constructor(data_obj)
    blueprint_func(operator)
    return operator.results()

with open('somefile','rb') as f:
    swapped = b''.join(extract(f,endian_swapper32))
