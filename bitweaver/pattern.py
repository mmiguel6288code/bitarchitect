import re, ast, io, struct
from enum import Enum
from math import ceil
import bits_io

SEEK_SET = bits_io.SEEK_SET
SEEK_CUR = bits_io.SEEK_CUR
SEEK_END = bits_io.SEEK_END

class Directive(Enum):
    VALUE = 1 #args = (num_bits, encoding)
    MOVE = 2 #args = (num_bits, whence)
    ZEROS= 3 #args = (num_bits)
    ONES = 4 #args = (num_bits)
    MOD = 5 #args = (num_bits,modify_type) 
    MODSET = 6 #args = (modify_type,setting)
    SETLABEL = 7 #args = (label,)
    DEFLABEL = 8 #args = (label,value)
    MATCHLABEL = 9 #args = (label,)
    NESTOPEN = 10 #args = (,)
    NESTCLOSE = 11 #args = (,)
    ASSERTION = 12 #args = (value,)

class Encoding(Enum):
    UINT = 1 #unsigned integer
    SINT = 2 #signed 2's complement integer
    SPFP = 3 #single precision floating point
    DBFP = 4 #double precision floating point
    LHEX = 5 #lower case hex string 
    UHEX = 6 #upper case hex string 
    BINS = 7 #bin string
    BYTS = 8 #bytes object

class ModType(Enum):
    REVERSE=1
    INVERT=2

class Setting(Enum):
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
        
    Movement tokens:
        n<n> = Moves the current position forward by n bits
        p<n> = Moves the current position backwards by n bits
        j<n> = Moves to n bits after the beginning of the bit stream
        J<n> = Moves to n bits before the end of the bit stream
        
    Stream modifiers:
        r<n> = Reverse the next n bits without moving the seek position
        i<n> = Invert the next n bits without moving the seek position

    In the expressions defining the following tokens, <t|y|n> refers to any of the three letters "t", "y", or "n".
        "y" is interpreted as yes or True
        "n" is interpreted as no or False
        "t" is interpreted as toggle from the current value i.e. yes -> no and no -> yes

    Setting tokens:
        R<t|y|n>  = Reverse all setting. Settings are preserved from execution to execution of the same session.
        I<t|y|n> = Invert all setting. Settings are preserved from execution to execution of the same session.

    Misc tokens:
        z<n> = Represents a sequence of zeros n bits long
        o<n> = Represents a sequence of ones n bits long
        [...] = Signify structural nesting
        #"<label>" = Associate the previously parsed value with the label specified between the double quotes. Label names can consist of any characters besides the double quote character.
        !#"<label>"=<python_expr>; = Evaluate the python expression and associate it with the label. The label may not contain a double quote character. The python expression may not contain a semi-colon. The expression should be a python literal, not refer to a variable.
        =<python_expr>; = Assert the previously parsed value, decoded to final form (e.g. hex) is equal to the evaluation of the provided python expression. The python expression must not contain a semi-colon nor a pound sign (#). The expression should be a python literal, not refer to a variable.
        =#"<label>" = Assert the previously parsed value, decoded to final form (e.g. hex) is equal to the value associated with the provided label

    """
    pos = 0
    tok_parse = re.compile('\\s*([usfxXbBnpjJrizo]\\d+|[RI][ynt]|!#"|#"|=#"|[\\[\\]=]')
    label_parse = re.compile('([^"]+)"')
    space_equals_parse = re.compile('\\s*=')
    expr_parse = re.compile('([^;]+);')

    no_arg_codes = {
            '[': Directive.NESTOPEN,
            ']': Directive.NESTCLOSE,
            }
    num_codes = {
            'z':Directive.ZEROS,
            'o':Directive.ONES,
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
            'n':(Directive.MOVE,SEEK_CUR),
            'p':(Directive.MOVE,SEEK_CUR),
            'j':(Directive.MOVE,SEEK_SET),
            'J':(Directive.MOVE,SEEK_END),
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

    while tokmatch is not None:
        tok = tokmatch.group(1)
        code = tok[0]
        if code in num_and_arg_tokens: #VALUE, MOVE, MOD
            directive,arg = num_and_arg_tokens[code]
            n = int(tok[1:])
            if code in negate_num_tokens:
                n = -n
            yield (tok,directive,n,arg)
        elif code in no_arg_codes: #NESTOPEN, NESTCLOSE
            directive = no_arg_codes[code]
            yield (tok,directive)
        elif code in setting_codes: #MODSET
            directive,modtype = setting_codes[code]
            setting = setting_map[tok[1]]
            yield (tok,directive,modtype,setting)
        elif code in num_codes: #ZEROS, ONES
            directive= num_codes[code]
            n = int(tok[1:])
            yield (tok,directive,n)
        elif tok == '#"': #SETLABEL
            labelmatch = label_parse.match(pattern,pos+2)
            pos = labelmatch.end(0)
            label = labelmatch.group(1)
            yield (tok+labelmatch.group(0),Directive.SETLABEL,label)
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
            yield (tok+labelmatch.group(0) + space_equals_match.group(0) + expr_match.group(0),Directive.DEFLABEL,label,value)

        elif tok == '=#"': #MATCHLABEL
            labelmatch = label_parse.match(pattern,pos+3)
            pos = labelmatch.end(0)
            label = labelmatch.group(1)
            yield (tok+labelmatch.group(0),Directive.MATCHLABEL,label)

        elif tok == '=': #ASSERTION 
            expr_match = expr_parse.match(pattern,pos)
            pos = expr_match.end(0)
            expr = expr_match.group(1)
            value = ast.literal_eval(expr)
            yield (tok+expr_match.group(0),Directive.ASSERTION,value)

        else:
            raise Exception('Unknown token: %s' % tok)

def uint_decode(uint_value,num_bits,encoding):
    """
    Takes a uint value and decodes (interprets) it according to an encoding scheme
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
    Takes a value and encodes it into a uint according to an encoding scheme
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

class Extractor():
    def __init__(self,pattern,bytes_obj,data_obj=None,labels=None):
        self.pattern = pattern
        self.bytes_obj = bytes_obj
        self.bits = bits_io.BitsIO(bytes_obj)
        self.reverse_all = False
        self.reverse_all = True
        self.last_value = None
        if data_obj is None:
            data_obj = []
        self.data_obj = data_obj
        self.stack = [data_obj]
        if labels is None:
            labels = {}
        self.labels = labels
        for instruction in parse(pattern):
            tok = instruction[0]
            self.tok = tok
            directive = instruction[1]
            args = instruction[2:]
            method_name = 'handle_'+directive.name.lower()
            method = getattr(self,method_name)
            method(*args)

    def handle_value(self,num_bits,encoding):
        uint_value,num_extracted = self.bits.read(num_bits,reverse=self.reverse_all,invert=self.invert_all)
        if num_extracted != num_bits:
            raise IncompleteDataError('Token = %s; Expected bits = %d; Extracted bits = %d' % (self.tok,num_bits,num_extracted))
        value = uint_decode(uint_value,num_bits,encoding)
        self.stack[-1].append(value)
        self.last_value = value
        return value
    def handle_move(self,num_bits,whence):
        self.bits.seek(num_bits,whence)
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
        self.stack.pop(-1) #stop modifying the current record and modify whatever one we were doing before it
    def handle_assertion(self,value):
        if self.last_value != value:
            raise AssertionError('Token = %s; Expected value = %s; Extracted value = %s' % (self.tok,repr(value),repr(self.last_value)))

def flatten(data_obj):
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

        

class Constructor():
    def __init__(self,pattern,data_obj,bytes_obj=None,labels=None):
        self.pattern = pattern
        self.data_obj = data_obj
        self.flat,self.flat_pattern = flatten(data_obj)
        self.flat_pos = 0
        self.reverse_all = False
        self.invert_all = False
        self.mod_operations = []
        self.last_value = None
        if bytes_obj is None:
            bytes_obj = io.BytesIO()
        self.bytes_obj = bytes_obj
        self.bits = bits_io.BitsIO(bytes_obj)
        if labels is None:
            labels = {}
        self.labels = labels
        for instruction in parse(pattern):
            tok = instruction[0]
            self.tok = tok
            directive = instruction[1]
            args = instruction[2:]
            method_name = 'handle_'+directive.name.lower()
            method = getattr(self,method_name)
            method(*args)
        pos = self.bits.tell()
        for tok,modtype,start,num_bits in self.mod_operations:
            self.bits.seek(start)
            if modtype == ModType.REVERSE:
                self.bits.reverse(num_bits)
            elif modtype == ModType.INVERT:
                self.bits.invert(num_bits)
            else:
                raise Exception('Token = %s; Invalid modtype: %s' % (tok,repr(modtype)))
        self.bits.seek(pos)
            
    def handle_value(self,num_bits,encoding):
        value = self.flat[self.flat_pos]
        self.flat_pos += 1
        uint_value = uint_encode(value,num_bits,encoding)
        self.bits.write(uint_value,num_bits,reverse=self.reverse_all,invert=self.invert_all)
        self.last_value = value
    def handle_move(self,num_bits,whence):
        self.bits.seek(num_bits,whence)
    def handle_zeros(self,num_bits):
        self.bits.write(0,num_bits,reverse=self.reverse_all,invert=self.invert_all)
    def handle_ones(self,num_bits):
        self.bits.write(0,num_bits,reverse=self.reverse_all,invert=not self.invert_all)
    def handle_mod(self,num_bits,modtype):
        #the bit stream does not fully exist yet, so store all reversals and inversions, then apply them at the end
        self.mod_operations.append((self.tok,mod_type,self.bits.tell(),num_bits))
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
        pass
    def handle_nestclose(self):
        pass
    def handle_assertion(self,value):
        if self.last_value != value:
            raise AssertionError('Token = %s; Expected value = %s; Extracted value = %s' % (self.tok,repr(value),repr(self.last_value)))

def execute(pattern,bytes_obj,mode='r',data_obj=None):
    """
    Execute a pattern against a bytes_obj.
    If mode == 'r', then bytes_obj is parsed according to the pattern.
    If mode == 'w', then bytes_obj is constructed
    """

"""

Need to translate whatever we get into a sequence of bits or bytes object

bf = BitForge(<instance of (bytes|BytesIO|file opened as 'rb')>,mode=<'r'|'w'>,codec=<bytes|hex|bin|base64|bz2|zip>)

blueprint = Blueprint()

Commands:
    blueprint = blueprint.do(pattern)
    blueprint = blueprint.do_repeat(count,pattern)
    blueprint = blueprint.do_for(iteration_label,iterable,pattern)
    blueprint = blueprint.do_while(condition,pattern)
    blueprint = blueprint.do_if(condition,pattern)
    blueprint = blueprint.do_elseif(condition,pattern)
    blueprint = blueprint.do_else(pattern)
Termination:
    Parsing/building will terminate when the pattern runs out or when the data runs out

References:
    ref(ref_id,expr=None,expr_var_name='x')

Control tokens:
    Just like methods above, but patterns (last input) are not quoted.
    u1u2u3 
    do_repeat(ref(0),u4u2u4) 
    u1u5u8 
    do_if(ref(0,'eq',5), [u7u1]) 
    do_else([]) 
    u1u1u1

Non-consuming tokens:
    reverse = r<n>
    invert = i<n>

Setting tokens:
    reverse_each = R<t|y|n> for toggle, yes, or no
    invert_each = I<t|y|n> for toggle, yes, or no

Movement tokens:
    next = n<n> #for building, skipped bits will be assumed to be zero
    previous = p<n>
    jump = j<n> where n = bit position in stream

Data tokens:
    unsigned = u<n>
    signed = s<n>
    single = f32
    double = f64
    hex = x<n>|X<n>
    bin = b<n>
    bytes = y<n>

Formatting tokens:
    nesting = [u1u2u3]
    labels = u5 "number of streams"

Constraint/Construction tokens:
    zeroes = z<n>
    ones = o<n>
    match = 
        u5 "number of streams" (=5) #can be preceded by label
        u5 (=5) #label not required
        u5 (="x") #can check against existing label

Reference IDs:
    Most recent item by index = 0 (last item parsed), 1 (one before that), etc
    Most recent item assigned to label = "number of streams"

blueprint.parse(byte) -> data
blueprint.parse(byte,include_labels=True) -> data,labels
blueprint.build(data) -> bytes

"""
#from .bitforge import *
