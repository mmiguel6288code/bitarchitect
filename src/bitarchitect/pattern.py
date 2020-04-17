import re, ast, io
from enum import Enum
from math import ceil
from .bits_io import SEEK_SET, SEEK_CUR, SEEK_END, uint_to_bytes, bytes_to_uint, BitsIO, reverse_bytes, invert_bytes
from .bit_utils import Encoding
from base64 import b16decode
import logarhythm

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
    TAKEALL = 14 #args = (encoding,)
    JUMP = 15 #args = (num_bits,jump_type)
    MARKERSTART = 16 #args = (byte_literal)
    MARKEREND = 17 #args = (byte_literal)


class ModType(Enum):
    """
    This enumeration defines the modify types available for MOD and MODSET directives
    """
    REVERSE=1
    INVERT=2
    ENDIANSWAP=3
    PULL=4
    ENDIANCHECK=5 #not actually a transformation, but used in a placeholder for Constructor() to check that endian swap size is whole number of bytes

class Setting(Enum):
    """
    This enumeration defines the setting values available for MODSET directives
    """
    FALSE=0
    TRUE=1
    TOGGLE=2

class JumpType(Enum):
    """
    This enumeration defines the modify types available for MOD and MODSET directives
    """
    START=1
    FORWARD=2
    BACKWARD=3
    END=4

def pattern_parse(pattern):
    """
    Interprets the provided pattern into a sequence of directives and arguments that are provided to a maker.

    Yields tuples where the first element is the matched token string, the second is the directive enum value, and the rest are the arguments for that directive.
    """
    logger = logarhythm.getLogger('parse_pattern')
    logger.format = logarhythm.build_format(time=None,level=False)
    logger.debug('pattern started')
    pattern = pattern.strip()
    pos = 0
    tok_parse = re.compile('\\s*([rip]\\d+\\.(?:\\d+|$)|[usfxXbBnpjJrizoeC]\\d+|[RIE][ynt]|!#"|#["#]|=#"|[\\[\\]=\\{\\}]|[riBC]$|m[$^]"|j[sfbe]\\d+)')
    label_parse = re.compile('([^"]+)"')
    space_equals_parse = re.compile('\\s*=')
    expr_parse = re.compile('([^;]+);')
    num_parse = re.compile('\\d+')
    num_inf_parse = re.compile('\\d+|\\$')
    comment_parse = re.compile('.*?$',re.S|re.M)
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
            'r':(Directive.MODOFF,ModType.REVERSE),
            'i':(Directive.MODOFF,ModType.INVERT),
            'p':(Directive.MODOFF,ModType.PULL),
            }
    setting_codes = {
            'R':(Directive.MODSET,ModType.REVERSE),
            'I':(Directive.MODSET,ModType.INVERT),
            'E':(Directive.MODSET,ModType.ENDIANSWAP),
            }
    num_and_arg_codes = {
            'u':(Directive.VALUE,Encoding.UINT),
            's':(Directive.VALUE,Encoding.SINT),
            'x':(Directive.VALUE,Encoding.LHEX),
            'X':(Directive.VALUE,Encoding.UHEX),
            'b':(Directive.VALUE,Encoding.BINS),
            'B':(Directive.VALUE,Encoding.BYTS),
            'C':(Directive.VALUE,Encoding.CHAR),
            'r':(Directive.MOD,ModType.REVERSE),
            'i':(Directive.MOD,ModType.INVERT),
            'e':(Directive.MOD,ModType.ENDIANSWAP),
            }
    negate_num_codes = set('Jp')
    setting_map = {
            'y':Setting.TRUE,
            'n':Setting.FALSE,
            't':Setting.TOGGLE,
            }
    jump_codes = {
            's':JumpType.START,
            'f':JumpType.FORWARD,
            'b':JumpType.BACKWARD,
            'e':JumpType.END,
            }

    repetition_stack = []

    tokmatch = tok_parse.match(pattern,pos)
    if tokmatch is not None:
        pos = tokmatch.end(0)

    while tokmatch is not None:
        tok = tokmatch.group(1)
        code = tok[0]

        instruction = None
        
        if '.' in tok: #MODOFF
            if '$' in tok: #MODOFF with $
                m = int(tok[1:].split('.')[0])
                n = None
                directive,modtype = modoff_codes[code]
                instruction = (tok,directive,m,n,modtype)

            else: #MODOFF with numbers
                m,n = [int(x) for x in tok[1:].split('.')]
                directive,modtype = modoff_codes[code]
                instruction = (tok,directive,m,n,modtype)
        elif tok == 'B$': #TAKEALL BYTS
            instruction = (tok,Directive.TAKEALL,Encoding.BYTS)
        elif tok == 'C$': #TAKEALL CHAR
            instruction = (tok,Directive.TAKEALL,Encoding.CHAR)
        elif tok == 'r$': #MOD
            instruction = (tok,Directive.MOD,None,ModType.REVERSE)
        elif tok == 'i$': #MOD
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
            labelmatch = label_parse.match(pattern,pos)
            tok += labelmatch.group(0)
            pos = labelmatch.end(0)
            label = labelmatch.group(1)
            instruction = (tok,Directive.SETLABEL,label)
        elif tok == '!#"': #DEFLABEL
            labelmatch = label_parse.match(pattern,pos)
            tok += labelmatch.group(0)
            pos = labelmatch.end(0)
            label = labelmatch.group(1)
            space_equals_match = space_equals_parse.match(pattern,pos)
            tok += space_equals_match.group(0)
            pos = space_equals_match.end(0)
            expr_match = expr_parse.match(pattern,pos)
            tok += expr_match.group(0)
            pos = expr_match.end(0)
            expr = expr_match.group(1)
            value = ast.literal_eval(expr.strip())
            instruction = (tok,Directive.DEFLABEL,label,value)

        elif tok == '=#"': #MATCHLABEL
            labelmatch = label_parse.match(pattern,pos)
            tok += labelmatch.group(0)
            pos = labelmatch.end(0)
            label = labelmatch.group(1)
            instruction = (tok,Directive.MATCHLABEL,label)

        elif tok == '=': #ASSERTION 
            expr_match = expr_parse.match(pattern,pos)
            tok += expr_match.group(0)
            pos = expr_match.end(0)
            expr = expr_match.group(1)
            value = ast.literal_eval(expr.strip())
            instruction = (tok,Directive.ASSERTION,value)
        elif tok == '{': #REPETITION CAPTURE START
            new_capture = [None] #first element is how many times to repeat; initialized to None and filled out when capture is complete
            if len(repetition_stack) > 0: #if nested repetition, need to connect previous capture to this new one
                repetition_stack[-1].append(new_capture)
            repetition_stack.append(new_capture) #new capture is focus now
            logger.debug('Beginning "{" repetition level %d' % len(repetition_stack))
        elif tok == '}': #REPETITION CAPTURE END
            logger.debug('Ending "}" repetition level %d' % len(repetition_stack))
            repetition_capture = repetition_stack.pop(-1)
            num_inf_match = num_inf_parse.match(pattern,pos) #collect number
            tok += num_inf_match.group(0)
            pos = num_inf_match.end(0)
            if num_inf_match.group(0) == '$':
                repetition_capture[0] = float('inf')
            else:
                repetition_capture[0] = int(num_inf_match.group(0)) #population first element with repetition number
            if len(repetition_stack) == 0: #if all repetitions are done
                yield from _process_repetition_capture(repetition_capture,logger)
        elif tok == '##': #COMMENT
            comment_match = comment_parse.match(pattern,pos)
            tok += comment_match.group(0)
            pos = comment_match.end(0)
            logger.debug('Comment: %s' % tok)
        elif tok.startswith('m'): 
            if tok[1] == '^': #MARKERSTART
                directive = Directive.MARKERSTART
            elif tok[1] == '$': #MARKEREND
                directive = Directive.MARKEREND
            hexmatch = hex_parse.match(pattern,pos)
            tok += hexmatch.group(0)
            pos = hexmatch.end(0)
            hex_literal = hexmatch.group(1)
            byte_literal = b16decode(hex_literal,True)
            instruction = (tok,directive,byte_literal)
        elif code == 'j':
            code2 = tok[1]
            num_bits = int(tok[2:])
            jump_type = jump_codes[code2]
            instruction = (tok,Directive.JUMP,num_bits,jump_type)
        else:
            raise Exception('Unknown token: %s' % tok)

        if instruction is not None:
            if len(repetition_stack) > 0:
                logger.debug('store rep level %d %s' % (len(repetition_stack),repr(instruction)))
                repetition_stack[-1].append(instruction)
            else:
                logger.debug('yield %s' % (repr(instruction)))
                yield instruction
        tokmatch = tok_parse.match(pattern,pos)
        if tokmatch is not None:
            pos = tokmatch.end(0)
    if pos < len(pattern):
        raise Exception('Unable to parse pattern after position %d: %s' % (pos,pattern[pos:pos+20]+'...'))
    logger.debug('pattern completed')
def _process_repetition_capture(repetition_capture,logger):
    count = repetition_capture[0]
    if count == float('inf'):
        iteration = 0
        while True:
            for item in repetition_capture[1:]:
                if isinstance(item,list):
                    yield from _process_repetition_capture(item,logger)
                else:
                    logger.debug('repetition %d yield %s' % (iteration+1,repr(item)))
                    yield item
            iteration += 1
    else:
        for iteration in range(count):
            for item in repetition_capture[1:]:
                if isinstance(item,list):
                    yield from _process_repetition_capture(item,logger)
                else:
                    logger.debug('repetition %d yield %s' % (iteration+1,repr(item)))
                    yield item


class ZerosError(Exception):pass
class OnesError(Exception):pass
class AssertionError(Exception):pass
class IncompleteDataError(Exception):pass
class MatchLabelError(Exception):pass
class NestingError(Exception):pass

def flatten(data_structure):
    """
    The flatten function takes a nested data structure (list of lists of lists etc) and returns a flattened version of it (list of values) as well as a flatten pattern that stores the nesting information.

    >>> flatten([1,'abc',[0,[1,1,[5]],'def'],9,10,11])
    ([1, 'abc', 0, 1, 1, 5, 'def', 9, 10, 11], '..[.[..[.]].]...')
    """
    data_stream = []
    structure_pattern = []
    stack = [[data_structure,0]]
    while len(stack) > 0:
        target,pos = stack[-1]
        if pos >= len(target):
            stack.pop(-1)
            structure_pattern.append(']')
        else:
            item = target[pos]
            stack[-1][1] += 1
            if isinstance(item,(list,tuple)):
                stack.append([item,0])
                structure_pattern.append('[')
            else:
                data_stream.append(item)
                structure_pattern.append('.')
    structure_pattern.pop(-1) #remove trailing ]
    return data_stream,''.join(structure_pattern)
def deflatten(structure_pattern,data_stream):
    """
    The deflatten function takes a structure pattern flat and a data stream (list of values), and produces a nested data structure according to those inputs.
    This is the inverse function of flatten()
    >>> deflatten('..[.[..[.]].]...',[1, 'abc', 0, 1, 1, 5, 'def', 9, 10, 11])
    [1, 'abc', [0, [1, 1, [5]], 'def'], 9, 10, 11]
    """
    data_structure = []
    stack = [data_structure]
    pos = 0
    for token in structure_pattern:
        if token == '[':
            new_sublist = []
            stack[-1].append(new_sublist)
            stack.append(new_sublist)
        elif token == ']':
            stack.pop(-1)
        elif token == '.':
            stack[-1].append(data_stream[pos])
            pos += 1
    return data_structure

def get_stream_index(structure_pattern,structure_index):
    """
    Translates the sequence of indices identifying an item  in a hierarchy
    to the index identifying the same item in the flattened data stream.
    The structure indices must point to a value, not a list.
    >>> get_stream_index('..[[[.]..].].',[0])
    0
    >>> get_stream_index('..[[[.]..].].',[2,0,0,0])
    2
    >>> get_stream_index('..[[[.]..].].',[2,1])
    5
    """
    structure_index = list(structure_index)
    stream_index = 0 
    current_structure_index  = [0] 
    for p in structure_pattern:
        if p == '[':
            if current_structure_index >= structure_index:
                raise Exception('Provided structure_index does not point to a non-list element')
            current_structure_index.append(0)
        elif p == ']':
            if current_structure_index >= structure_index:
                raise Exception('Provided structure_index does not point to a non-list element')
            current_structure_index.pop(-1)
            current_structure_index[-1] += 1
        elif p == '.':
            if current_structure_index == structure_index:
                return stream_index
            stream_index += 1
            current_structure_index[-1] += 1
        else:
            raise Exception('Invalid character in structure pattern: %s' % repr(p))

def get_structure_index(structure_pattern,stream_index):
    """
    Translates the stream index into a sequence of structure indices identifying an item in a hierarchy whose structure is specified by the provided structure pattern.
    >>> get_structure_index('...',1)
    [1]
    >>> get_structure_index('.[.].',1)
    [1, 0]
    >>> get_structure_index('.[[...],..].',1)
    [1, 0, 0]
    >>> get_structure_index('.[[...]...].',2)
    [1, 0, 1]
    >>> get_structure_index('.[[...]...].',3)
    [1, 0, 2]
    >>> get_structure_index('.[[...]...].',4)
    [1, 1]
    >>> get_structure_index('.[[...]...].',5)
    [1, 2]
    >>> get_structure_index('.[[...]...].',6)
    [1, 3]
    >>> get_structure_index('.[[...]...].',7)
    [2]
    """
    structure_index = [0]
    current_stream_index = 0
    for p in structure_pattern:
        if p == '[':
            structure_index.append(0)
        elif p == '.':
            if current_stream_index == stream_index:
                return structure_index
            structure_index[-1] += 1
            current_stream_index += 1
        elif p == ']':
            structure_index.pop(-1)
            structure_index[-1] += 1
        else:
            raise Exception('Invalid character in structure pattern: %s' % repr(p))
    raise Exception('Provided stream index does not exist in the provided structure pattern')

class Maker():
    """
    This is a common base class for the Extractor and Constructor classes.
    The __init__(), __call__(), and handle_...() functions must be implemented by each subclass.
    """
    def __init__(self,data_source):
        """
        Initialize the maker object with a data source
        """
        raise NotImplementedError
        self.labels = {}
    def __call__(self,pattern):
        """
        Apply the maker against the data source according to the provided pattern.
        Return the data record consisting of the values corresponding to the pattern data.
        """
        raise NotImplementedError
        return data_record
    def __getitem__(self,label):
        return self.labels[label][-1][0]
    def __setitem__(self,label,value):
        self.labels[label].append((value,None,None))
    def __delitem__(self,label):
        del self.labels[label]

    def tell_buffer(self):
        return self.bit_stream.tell()
    def tell_stream(self):
        return self._translate_to_original(self.tell())
    def index_structure(self):
        return list(self.index_stack)
    def index_stream(self):
        return self.flat_pos
    def finalize(self):
        raise NotImplementedError

    def at_eof(self):
        return self.bits.at_eof()

    def __bytes__(self):
        return bytes(self.bit_stream)
    def _translate_to_original(self,pos):
        orig_pos = pos
        for tok, modtype, start, offset, num_bits in self.mod_operations[::-1]:
            mstart = start + offset
            mend = mstart + num_bits
            if modtype == ModType.REVERSE:
                if mstart <= orig_pos <= mend:
                    orig_pos = mend - (orig_pos - mstart)
            elif modtype == ModType.INVERT or modtype == ModType.ENDIANCHECK:
                pass
            else:
                raise Exception('Invalid modtype for _translate_to_original: %s' % modtype)
        return orig_pos

    def _translate_from_original(self,orig_pos):
        pos = orig_pos
        for tok, modtype, start, offset, num_bits in self.mod_operations:
            mstart = start + offset
            mend = mstart + num_bits
            if modtype == ModType.REVERSE:
                if mstart <= pos <= mend:
                    pos = mend - (pos - mstart)
            elif modtype == ModType.INVERT or modtype == ModType.ENDIANCHECK:
                pass
            else:
                raise Exception('Invalid modtype for _translate_to_original: %s' % modtype)
        return pos


class Extractor(Maker):
    """
    The Extractor takes binary bytes data and extracts data values out of it.
    """
    def __init__(self,byte_stream):
        self.byte_stream = byte_stream
        self.bit_stream = BitsIO(byte_stream)

        #Initialize settings
        self.reverse_all = False
        self.invert_all = False
        self.endianswap_all = False

        self.last_value = None
        self.last_index_stack = None

        self.labels = {}

        self.data_stream = []
        self.flat_labels = []
        self.flat_pattern = [] #list of characters
        self.flat_pos = 0
        self.index_stack = [0]

        self.data_structure = []
        self.stack_data = [self.data_structure]
        self.mod_operations = [] # tok, modtype, start, offset, num_bits
        self.logger = logarhythm.getLogger('Extractor')
        self.logger.format = logarhythm.build_format(time=None,level=False)

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
        if len(self.stack_data) > 1:
            raise NestingError('There exists a "[" with no matching "]"')
        elif len(self.stack_data) < 1:
            raise NestingError('There exists a "]" with no matching "["')
        self.flat_pattern = ''.join(self.flat_pattern)

    def _apply_settings(self,num_bits,encoding):
        pos = self.tell_buffer()
        if self.reverse_all:
            self.bit_stream.reverse(num_bits)
            self.mod_operations.append((self.tok,ModType.REVERSE,pos,0,num_bits))
        if self.invert_all:
            self.bit_stream.invert(num_bits)
            self.mod_operations.append((self.tok,ModType.INVERT,pos,0,num_bits))
        if self.endianswap_all and encoding != Encoding.CHAR:
            self._endianswap(num_bits)

    def _consume_bits(self,num_bits=None,encoding=Encoding.UINT):
        self._apply_settings(num_bits,encoding)
        uint_value,num_extracted = self.bit_stream.read(num_bits)
        if num_extracted != num_bits:
            import pdb; pdb.set_trace()
            raise IncompleteDataError('Token = %s; Expected bits = %d; Extracted bits = %d' % (self.tok,num_bits,num_extracted))
        value = uint_decode(uint_value,num_bits,encoding)
        return value

    def _insert_data(self,value):
        self.stack_record[-1].append(value)
        self.stack_data[-1].append(value)
        self.last_value = value
        self.flat_pattern.append('.')
        self.data_stream.append(value)
        self.flat_labels.append(None)
        self.flat_pos += 1
        self.last_index_stack = tuple(self.index_stack)
        self.index_stack[-1] += 1
    def _insert_data_record(self,record):
        l = len(record)
        self.stack_record[-1].append(record)
        self.stack_data[-1].append(record)
        self.last_value = record[-1]
        self.flat_pattern.extend('['+'.'*l+']')
        self.data_stream.extend(record)
        self.flat_labels.extend([None]*l)
        self.flat_pos += l
        self.last_index_stack = tuple(self.index_stack)
        self.index_stack[-1] += 1

    def _endianswap(self,n):
        if n % 8 != 0:
            raise Exception('Endian swap must be performed on a multiple of 8 bits: %s' % self.tok)
        pos = self.tell_buffer()
        self.bit_stream.reverse(n)
        self.mod_operations.append((self.tok,ModType.REVERSE,pos,0,n))
        for i in range(0,n,8):
            self.bit_stream.reverse(8)
            self.bit_stream.seek(8,SEEK_CUR)
            self.mod_operations.append((self.tok,ModType.REVERSE,pos,i,8))
        self.bit_stream.seek(pos)

    def _pull(self,m,n):
        pos = self.tell_buffer()
        if n is None:
            L = len(self.bit_stream)
            n = L - (pos+m)
            self._insert_data(n)
        self.bit_stream.reverse(m+n)
        self.mod_operations.append((self.tok,ModType.REVERSE,pos,0,m+n))
        self.bit_stream.reverse(n)
        self.mod_operations.append((self.tok,ModType.REVERSE,pos,0,n))
        self.bit_stream.seek(n,SEEK_CUR)
        self.bit_stream.reverse(m)
        self.mod_operations.append((self.tok,ModType.REVERSE,pos,n,m))
        self.bit_stream.seek(pos)
        return n


    def handle_value(self,num_bits,encoding):
        value = self._consume_bits(num_bits,encoding)
        self._insert_data(value)
        self.logger.debug('%s = %r' % (self.tok,value))
        return value

    def handle_takeall(self,encoding):
        pos = self.tell_buffer()
        if pos % 8 != 0:
            raise Exception('%s requires the bit seek position to be on a byte boundary' % self.tok)
        L = len(self.bit_stream)
        num_bits = L - self.tell_buffer()
        self._apply_settings(num_bits,encoding)

        bytes_data,first_byte_value,first_byte_bits = self.bit_stream.read_bytes()
        value = bytes_data
        self._insert_data(value)
        return value

    def handle_next(self,num_bits):
        self.bit_stream.seek(num_bits,SEEK_CUR) #these bits are don't cares

    def handle_zeros(self,num_bits):
        value = self._consume_bits(num_bits)
        if value != 0:
            raise ZerosError('Token = %s; Expected all zeros; Extracted value = %d' % (self.tok,value))

    def handle_ones(self,num_bits):
        value = self._consume_bits(num_bits)
        all_ones = (1<<num_bits)-1
        if value != all_ones:
            raise OnesError('Token = %s; Expected all ones (%d); Extracted value = %d' % (self.tok,all_ones,value))

    def handle_mod(self,num_bits,modtype):
        pos = self.tell_buffer()
        if modtype == ModType.REVERSE:
            self.bit_stream.reverse(num_bits)
            self.mod_operations.append((self.tok,ModType.REVERSE,pos,0,num_bits))
        elif modtype == ModType.INVERT:
            self.bit_stream.invert(num_bits)
            self.mod_operations.append((self.tok,ModType.INVERT,pos,0,num_bits))
        elif modtype == ModType.ENDIANSWAP:
            self._endianswap(num_bits)
        else:
            raise Exception('Token = %s; Invalid modtype: %s' % (self.tok,repr(modtype)))

    def handle_marker(self,bytes_literal):
        orig_bytes_literal = bytes_literal
        pos = self.tell_buffer()
        if pos % 8 != 0:
            raise Exception('Marker operation must occur when bit seek position is a multiple of 8')
        if self.invert_all:
            bytes_literal = invert_bytes(bytes_literal)
        if self.reverse_all:
            bytes_literal = reverse_bytes(bytes_literal)
        if self.endianswap_all:
            bytes_literal = bytes_literal[::-1]

        m = bits_offset = self.bit_stream.find(bytes_literal)
        self.handle_nestopen()
        self._insert_data(m) #insert m 
        n = self._pull(m,None) #p<m>.$ - will insert n
        self.handle_nestclose()
        marker = self._consume_bits(len(bytes_literal)*8,Encoding.BYTS) #skip past the marker itself, applying any needed mod_operations
        if marker != orig_bytes_literal:
            raise Exception('Marker scan consumption did not match expected bytes literal')
        self.logger.debug('Scan for %s: offset = %d, pulled bits = %d' % (repr(orig_bytes_literal),m,n))


    def handle_modoff(self,offset_bits,num_bits,modtype):
        pos = self.tell_buffer()
        if modtype == ModType.REVERSE:
            if num_bits is None:
                L = len(self.bit_stream)
                num_bits = L - (pos+offset_bits)
                self._insert_data(num_bits)
            self.bit_stream.seek(offset_bits,SEEK_CUR)
            self.bit_stream.reverse(num_bits)
            self.mod_operations.append((self.tok,ModType.REVERSE,pos,offset_bits,num_bits))
        elif modtype == ModType.INVERT:
            if num_bits is None:
                L = len(self.bit_stream)
                num_bits = L - (pos+offset_bits)
                self._insert_data(num_bits)
            self.bit_stream.seek(offset_bits,SEEK_CUR)
            self.bit_stream.invert(num_bits)
            self.mod_operations.append((self.tok,ModType.INVERT,pos,offset_bits,num_bits))
        elif modtype == ModType.PULL:
            self._pull(offset_bits,num_bits)
        else:
            raise Exception('Token = %s; Invalid modtype: %s' % (self.tok,repr(modtype)))
        self.bit_stream.seek(pos)

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
        elif modtype == ModType.ENDIANSWAP:
            if setting == Setting.TRUE:
                self.endianswap_all = True
            elif setting == Setting.FALSE:
                self.endianswap_all = False
            elif setting == Setting.TOGGLE:
                self.endianswap_all = not self.endianswap_all
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
        new_record = []
        self.stack_data[-1].append(new_record) #embed new record into the previous record
        self.stack_data.append(new_record) #make the new record the active record being worked on
        self.flat_pattern.append('[')
        self.index_stack.append(0)

    def handle_nestclose(self):
        if len(self.stack_data) == 1:
            raise NestingError('there exists a "]" with no matching "["')
        self.last_value = self.stack_record[-1]
        if len(self.stack_record) == 1:
            self.data_record = [self.data_record] #expand out as if there were some [ in previous call
            self.stack_record = [self.data_record]
        else:
            self.stack_record.pop(-1) #stop modifying the current record and modify whatever one we were doing before it
        self.stack_data.pop(-1) #stop modifying the current record and modify whatever one we were doing before it
        self.flat_pattern.append(']')
        self.index_stack.pop(-1)
        self.index_stack[-1] += 1

    def handle_assertion(self,value):
        if self.last_value != value:
            raise AssertionError('Token = %s; Expected value = %s; Extracted value = %s' % (self.tok,repr(value),repr(self.last_value)))


    def handle_jump(self,num_bits,jump_type):
        pos = self.tell_buffer()
        L = len(self.bit_stream)
        if jump_type in [JumpType.FORWARD,JumpType.BACKWARD]:
            self.logger.debug('Jump relative pos -> orig = %d -> %d' % (pos,target_orig))
            target_orig = self._translate_to_original(pos)
        elif jump_type == JumpType.END:
            self.logger.debug('Jump relative to end: %d' % L)
            target_orig = L
        else:
            self.logger.debug('Jump relative to beginning')
            target_orig = 0
        if jump_type in [JumpType.START, JumpType.FORWARD]:
            self.logger.debug('Jump forward offset: %d + %d = %d' % (target_orig,num_bits,target_orig+num_bits))
            target_orig += num_bits

        else:
            self.logger.debug('Jump backward offset: %d - %d = %d' % (target_orig,num_bits,target_orig-num_bits))
            target_orig -= num_bits

        target = self._translate_from_original(target_orig)
        self.logger.debug('Jump target translation: orig -> pos = %d -> %d' % (target_orig,target))
        offset = target - pos
        self.logger.debug('Jump actual buffer offset = %d - %d = %d' % (target,pos,offset))
        if offset < 0:
            raise Exception('Jump is to already parsed location: %s' % self.tok)
        if offset > 0:
            #num_bits = L - (pos + offset) #by providing a value, that makes it not get put into the data structure - it needs to be put into the data structure though
            num_bits = self._pull(offset,None)
            self.logger.debug('Jump pull offset = %d, num_bits = %d' % (offset,num_bits))

class Constructor(Maker):
    """
    The Constructor class takes a sequence of values (nested or not), and constructs a byte sequence according to provided patterns.
    """
    def __init__(self,data_structure):
        self.data_structure = data_structure

        #Simply flatten the data obj. The order of traversal is what is important, not the structure.
        self.data_stream,self.flat_pattern = flatten(data_structure)
        self.flat_labels = [None]*len(self.data_stream)
        self.flat_pos = 0
        self.index_stack = [0]

        
        #initialize settings
        self.reverse_all = False
        self.invert_all = False
        self.endianswap_all = False
        
        self.last_value = None
        self.last_index_stack = None
        self.byte_stream = io.BytesIO()
        self.bit_stream = BitsIO(self.byte_stream)
        self.labels = {}
        self.mod_operations = []
        self.logger = logarhythm.getLogger('Constructor')
        self.logger.format = logarhythm.build_format(time=None,level=False)

    def __call__(self,pattern):
        self.data_record = []
        self.stack = [self.data_record]
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
        pos = self.tell_buffer()
        L = len(self.bit_stream)
        for tok,modtype,start,offset,num_bits in self.mod_operations[::-1]:
            if num_bits is None:
                num_bits = L - (start+offset)
            if modtype == ModType.ENDIANCHECK:
                if num_bits % 8 != 0:
                    raise Exception('Endian swap must be performed on a multiple of 8 bits: %s' % self.tok)
                continue
            if modtype == ModType.REVERSE:
                self.bit_stream.seek(start+offset)
                self.bit_stream.reverse(num_bits)
            elif modtype == ModType.INVERT:
                self.bit_stream.seek(start+offset)
                self.bit_stream.invert(num_bits)
            else:
                raise Exception('Token = %s; Invalid modtype: %s' % (tok,repr(modtype)))
        self.bit_stream.seek(pos)

    def _pull(self,m,n):
        if n is None:
            n,_ = self._consume_data()
        pos = self.tell_buffer()
        self.mod_operations.append((self.tok,ModType.REVERSE,pos,0,m+n))
        self.mod_operations.append((self.tok,ModType.REVERSE,pos,0,n))
        self.mod_operations.append((self.tok,ModType.REVERSE,pos,n,m))
        return n

    def _endianswap(self,n):
        pos = self.tell()
        self.mod_operations.append((self.tok,ModType.REVERSE,pos,0,n))
        for i in range(0,n,8):
            self.mod_operations.append((self.tok,ModType.REVERSE,pos,i,8))
        self.mod_operations.append((self.tok,ModType.ENDIANCHECK,pos,0,n)) #add at end, so that check happens first when mod_operations is processed backwards

    def _apply_settings(self,num_bits,encoding):
        pos = self.tell_buffer()
        if self.reverse_all:
            self.mod_operations.append((self.tok,ModType.REVERSE,pos,0,num_bits))
        if self.invert_all:
            self.mod_operations.append((self.tok,ModType.INVERT,pos,0,num_bits))
        if self.endianswap_all and encoding != Encoding.CHAR:
            self._endianswap(num_bits)


    def _consume_data(self,num_bits=None,encoding=Encoding.UINT):
        value = self.data_stream[self.flat_pos]
        self.flat_pos += 1
        self.stack[-1].append(value)
        uint_value = uint_encode(value,num_bits,encoding)
        self.last_value = value
        self.last_index_stack = tuple(self.index_stack)
        self.index_stack[-1] += 1
        return uint_value,value

    def _insert_bits(self,uint_value,num_bits,encoding=Encoding.UINT):
        self._apply_settings(num_bits,encoding)
        self.bit_stream.write(uint_value,num_bits)

            
    def handle_value(self,num_bits,encoding):
        uint_value,value = self._consume_data(num_bits,encoding)
        self._insert_bits(uint_value,num_bits,encoding)
        self.logger.debug('%s = %r' % (self.tok,value))

    def handle_takeall(self,encoding):
        first_byte_value,first_byte_bits,bytes_data = self.data_stream[self.flat_pos]
        self.flat_pos += 1
        self.stack[-1].append(bytes_data)
        self.last_value = bytes_data
        self.last_index_stack = tuple(self.index_stack)
        self.index_stack[-1] += 1
        pos = self.tell_buffer()
        self._apply_settings(None,encoding)
        self.bit_stream.write_bytes(bytes_data,first_byte_value,first_byte_bits)

    def handle_next(self,num_bits):
        #bits are don't care - no reversals or inversions
        self.bit_stream.write(0,num_bits)

    def handle_zeros(self,num_bits):
        self._insert_bits(0,num_bits)

    def handle_ones(self,num_bits):
        all_ones = (1<<num_bits)-1
        self._insert_bits(all_ones,num_bits)

    def handle_mod(self,num_bits,modtype):
        #the bit stream does not fully exist yet, so store all reversals and inversions, then apply them at the end
        if modtype == ModType.ENDIANSWAP:
            self._endianswap(num_bits)
        else:
            self.mod_operations.append((self.tok,mod_type,self.tell_buffer(),0,num_bits))

    def handle_marker(self,bytes_literal):
        num_bits = len(bytes_literal)*8
        pos = self.tell_buffer()
        if pos % 8 != 0:
            raise Exception('Marker operation requires bit seek position to be a multiple of 8')
        self.handle_nestopen()
        m,_ = self._consume_data()
        n,_ = self._consume_data()
        self.handle_nestclose()
        self._pull(m,n)
        self._insert_bits(uint_encode(bytes_literal,num_bits,Encoding.BYTS),num_bits,Encoding.BYTS)
        self.logger.debug('Scan for %s: offset = %d, pulled bits = %d' % (repr(bytes_literal),m,n))

    def handle_modoff(self,offset_bits,num_bits,modtype):
        #the bit stream does not fully exist yet, so store all reversals and inversions, then apply them at the end
        if num_bits is None: #for when $ is in token
            num_bits,_ = self._consume_data()
        pos = self.tell_buffer()
        if modtype == ModType.PULL:
            self._pull(offset_bits,num_bits)
        else:
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
        elif modtype == ModType.ENDIANSWAP:
            if setting == Setting.TRUE:
                self.endianswap_all = True
            elif setting == Setting.FALSE:
                self.endianswap_all = False
            elif setting == Setting.TOGGLE:
                self.endianswap_all = not self.endianswap_all
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
        self.last_value = self.stack[-1]
        if len(self.stack) == 1:
            self.data_record = [self.data_record] #expand out as if there were a [ in some previous call
            self.stack = [self.data_record]
        else:
            self.stack.pop(-1) #stop modifying the current record and modify whatever one we were doing before it
        self.index_stack.pop(-1)
        self.index_stack[-1] += 1

    def handle_assertion(self,value):
        if self.last_value != value:
            raise AssertionError('Token = %s; Expected value = %s; Extracted value = %s' % (self.tok,repr(value),repr(self.last_value)))

    def handle_jump(self,num_bits,jump_type):
        pos = self.tell()
        L = len(self.bit_stream)
        if jump_type in [JumpType.FORWARD,JumpType.BACKWARD]:
            self.logger.debug('Jump relative pos -> orig = %d -> %d' % (pos,target_orig))
            target_orig = self._translate_to_original(pos)
        elif jump_type == JumpType.END:
            self.logger.debug('Jump relative to end: %d' % L)
            target_orig = L
        else:
            self.logger.debug('Jump relative to beginning')
            target_orig = 0
        if jump_type in [JumpType.START, JumpType.FORWARD]:
            self.logger.debug('Jump forward offset: %d + %d = %d' % (target_orig,num_bits,target_orig+num_bits))
            target_orig += num_bits
        else:
            self.logger.debug('Jump backward offset: %d - %d = %d' % (target_orig,num_bits,target_orig-num_bits))
            target_orig -= num_bits
        target = self._translate_from_original(target_orig)
        self.logger.debug('Jump target translation: orig -> pos = %d -> %d' % (target_orig,target))
        offset = target - pos
        self.logger.debug('Jump actual buffer offset = %d - %d = %d' % (target,pos,offset))
        if offset < 0:
            raise Exception('Jump is to already parsed location: %s' % self.tok)
        if offset > 0:
            self._pull(offset,None)
            self.logger.debug('Jump pull offset = %d, num_bits = %d' % (offset,num_bits))

def extract(blueprint,byte_stream,*args,**kwargs):
    maker = Extractor(byte_stream)
    if isinstance(blueprint,(bytes,str)):
        result = maker(blueprint)
    else:
        result = blueprint(maker,*args,**kwargs)
    maker.finalize()
    return maker, result

def extract_data_structure(blueprint,byte_stream,*args,**kwargs):
    maker,result = extract(blueprint,byte_stream,*args,**kwargs)
    return maker.data_structure

def extract_data_stream(blueprint,byte_stream,*args,**kwargs):
    maker,result = extract(blueprint,byte_stream,*args,**kwargs)
    return maker.data_stream

def construct(blueprint,data_stream,*args,**kwargs):
    maker = Constructor(data_stream)
    if isinstance(blueprint,(bytes,str)):
        result = maker(blueprint)
    else:
        result = blueprint(maker,*args,**kwargs)
    maker.finalize()
    return maker,result

def construct_bytes_stream(data_stream,blueprint,*args,**kwargs):
    maker,result = construct(blueprint,data_stream,*args,**kwargs)
    return maker.bytes_stream
