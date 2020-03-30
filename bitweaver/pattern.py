import re
from enum import Enum
import bits_io

SEEK_SET = bits_io.SEEK_SET
SEEK_CUR = bits_io.SEEK_CUR
SEEK_END = bits_io.SEEK_END

class Directive(Enum):
    VALUE = 1 #args = (num_bits, encoding)
    MOVE = 2 #args = (num_bits, whence)
    CONSTANT= 3 #args = (num_bits, value)
    MOD = 4 #args = (num_bits,modify_type) 
    MODSET = 5 #args = (modify_type,setting)
    SETLABEL = 6 #args = (label,)
    MATCHLABEL = 7 #args = (label,)
    NESTOPEN = 8 #args = (,)
    NESTCLOSE = 9 #args = (,)

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
    Interprets the provided pattern into a sequence of directives.

    The result is an iterable that yields tuples.
    The first element is the directive enum value and the rest are the arguments for that directive.

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
        next = n<n> #for building, skipped bits will be assumed to be zero
        previous = p<n>
        jump = j<n> where n = bit position in stream
        
    Stream modifiers:
        reverse = r<n>
        invert = i<n>

    Setting tokens:
        reverse_each = R<t|y|n> for toggle, yes, or no
        invert_each = I<t|y|n> for toggle, yes, or no

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

    """
    pos = 0
    tok_parse = re.compile('^\\s*([usfxXbBnpjJrizo]\\d+|[RI][ynt]|[\\[\\]"=]')

    negate_num_tokens = set('Jp')
    no_arg_tokens = set('[]')
    setting_tokens = set('RI')
    label_tokens = set('"=')
    num_and_arg_tokens = {
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
            'z':(Directive.CONSTANT,0),
            'o':(Directive.CONSTANT,1),
            'r':(Directive.MOD,ModType.REVERSE),
            'i':(Directive.MOD,ModType.INVERT),
            }

    tokmatch = tok_parse.match(pattern,pos)
    pos = tokmatch.end(0)
    while tokmatch is not None:
        tok = tokmatch.group(1)
        code = tok[0]
        if code in num_and_arg_tokens:
            directive,arg = num_and_arg_tokens[code]
            n = int(tok[1:])
            if code in negate_num_tokens:
                n = -n
            yield (directive,n,arg)
        elif code in 


        if tok[0] in 'usfxXbBnpjJrizo':
            n = int(tok[1:])

        tokmatch = tok_parse.match(pattern,pos)
        pos = tokmatch.end(0)

def construct(pattern,data_obj):
    ...
def extract(pattern,bytes_obj):
    ...
    

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
