"""

Need to translate whatever we get into a sequene of bits or bytes object

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
