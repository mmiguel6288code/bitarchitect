"""
Key Ideas:
    ( 1) A byte stream is a sequence of bytes. May be an instance of bytes, bytearray, memoryview, BytesIO, file
    ( 2) A bit stream is a sequence of bits. An instance of bitarchitect.BitsIO. Every bit stream has an underlying buffer that is a byte stream.
    ( 3) A binary format specification is an interpretation of a sequence of bits that divides its regions into fields with specific interpretations.
    ( 4) A data structure is a hierarchy i.e. a list of elements which are either values or other hierarchies (lists).
    ( 5) A data stream is a sequence of python values. A data structure can be flattened into a data stream. Conversely, a data stream can be hierarchically rearranged into a data structure.
    ( 6) Extraction is the process of interpreting a byte stream into a data structure. It is the inverse of construction.
    ( 7) Construction is the process of building a byte stream from a data structure. It is the inverse of extraction.
    ( 8) A blueprint is a series of common instructions that enable both extraction and construction according to a common interpretation of a binary file format specification.
    ( 9) A parsing pattern is a string consisting of tokens that describe basic extraction and construction operations. 
    (10) A token is a short string within a parsing pattern that has a primitive extraction operation interpretation as well as a complementary primitive construction operation interpretation. 
    (11) A token class is a template representation of a set of tokens with the same purpose but different details (such as number of bits involved).
    (12) A Maker implements the extraction/construction primitive instructions and other infrastructure to apply a blueprint. A Maker is either an Extractor or a Constructor.
    (13) Bit seek position refers to the current point of reading/writing within a bit stream.
    (14) The data stream index refers to the current point of insertion/referencing within a data stream.
    (15) A blueprint is extractable if it can be used with an Extractor.
    (16) A blueprint is constructible if it can be used with a Constructor.
    (17) A blueprint is bijective if it is both extractable and constructible

The purpose of this module is to provide the tools needed to implement bijective blueprints.

Simple blueprints can be defined as a single parsing pattern string that conforms to the bitarchitect pattern language.
More complex blueprints are defined as a python functions. These may assert multiple parsing patterns in conjunction with python conditional branching and loops.
The author of a blueprint typically writes the function with extraction in mind.
By following the rules outlined in this documentation, the resulting blueprint function will be usable for construction as well.


Blueprint/Maker API:

    Defining a string Blueprint:
        A string blueprint is just a parsing pattern.

    Defining a function Blueprint:
        The first argument of every blueprint function is the maker object.
        A blueprint function may have additional arguments after that, but the first argument must be the maker object.

        def my_blueprint_function(maker,*args,**kwargs):
            ...

        Within the blueprint function, the maker may be called with a parsing pattern as if the maker object were a function.
        The return value of doing this will be a data structure containing only the items that were parsed in that call.
        Additionally, if the parsing results in any labels being assigned, the maker object can be keyed as if it were a dictionary to return the most recent value for a given label.

        def my_blueprint_function(maker,*args,**kwargs):
            values = maker('u16 #"param1" u5 #"x" u2')

            param1 = maker['param1']
            x = maker['x']
            ...

        The maker.tell_buffer() method returns the current bit position in the internal make object's bit stream buffer. This may not correspond to the position in the pre-extraction or post-construction bit stream.

        The maker.tell_stream() method returns the corresponding bit position in the pre-extraction or post-construction bit stream. This may not correspond to the current bit position in the internal make object's bit stream buffer.

        The maker.index_structure(n=0) method, when n is given as 0, returns the list of indices indicating where the next item to be inserted into/taken from the data structure is.
            If a negative value of n is provided, then the result will be the list of indices for the item at that negative index in the data stream.
            Recall in python that indexing a list with -1 gives the last element, -2 gives the second to last element, etc.
            For example if maker.index_structure(0) == [0,3,1], then the next item will be inserted/taken at maker.data_structure[0][3][1].
            maker.index_structure(-1) will return [0,3,0]

        The maker.index_stream() method returns the single index number indicating where the next item will be inserted into/taken from the data stream.
            For example, if the result is 201, then the next item will be inserted/taken at maker.data_stream[201]

    Invoking a Blueprint:
        To invoke a blueprint in extraction mode, use one of the following bitarchitect functions:
            (1) maker = extract(blueprint,byte_stream,*args,**kwargs)
                Returns the maker object that has fully extracted the given byte stream using the blueprint. 
                If the blueprint is a function:
                    Args and kwargs are passed into the function after the maker object.
                    The return value of the function will be stored in maker.blueprint_result
                If the blueprint is a string:
                    Args and kwargs are not used.
                    maker.blueprint_result will be None
                The data structure and data stream can be obtained from:
                    maker.data_structure
                    maker.data_stream

            (2) data_structure = extract_data_structure(blueprint,byte_stream,*args,**kwargs)
                Returns the data structure that has been fully extracted from the given byte stream using the blueprint.
                If the blueprint is a function:
                    Args and kwargs are passed into the function after the maker object.

            (3) data_stream = extract_data_stream(blueprint,byte_stream,*args,**kwargs)
                Returns the data stream that has been fully extracted from the given byte stream using the blueprint.
                If the blueprint is a function:
                    Args and kwargs are passed into the function after the maker object.

        To invoke a blueprint in construction mode, use one of the following bitarchitect functions:
            (1) maker = construct(blueprint,data_stream,*args,**kwargs)
                Returns the maker object that has fully constructed a byte stream from the given data stream using the blueprint.
                The data stream can be either a true data stream (flat list) or a data structure (hierarchy) without any difference assuming the two representations have the same order in traversing values.
                If the blueprint is a function:
                    Args and kwargs are passed into the function after the maker object.
                    The return value of the function will be stored in maker.blueprint_result
                If the blueprint is a string:
                    Args and kwargs are not used.
                    maker.blueprint_result will be None
                The byte stream can be obtained from:
                    maker.byte_stream

            (2) byte_stream = construct_byte_stream(blueprint,data_stream,*args,**kwargs)
                Returns the byte stream that has been constructed from the given data stream using the blueprint.
                byte_stream will be a python bytes object.
                If the blueprint is a function:
                    Args and kwargs are passed into the function after the maker object.
Modification operations:
    All modification operations ultimately are either bit reversals or bit inversions at specific offsets and for specific lengths.
    Both of these primitive operations are their own inverses.
    More complex operations (pull, jump, marker scan) involve chaining together reversals and/or using scanning for markers to determine specific offsets and lengths for reversals.

Extraction algorithm:
    Extraction involves copying the original bytes into a bit stream buffer and starting with an empty data stream and an empty data structure.
    All bits before the bit seek position of the buffer are considered extracted.
    All bits after the bit seek position of the buffer are to be extracted.
    The data stream and data structures are built as the bit seek position moves forward.
    Modification operations occur in the buffer as soon as the tokens are processed.
    Modification or consumption of bits prior to the bit seek position is not allowed (otherwise the blueprint is non-constructable)

Construction algorithm:
    Construction involves producing an empty bit stream buffer and starting with a populated data stream.
    Modification operations in general are interpreted as applying forward from the seek position. Since the buffer is being constructed, there are no bits ahead of the seek position.
    Thus, in the first pass through the tokens, modification operations are saved in order, along with the seek position at which they are each intended to be applied, but not actually applied, whereas bit producing instructions result in writes to the buffer.
    After the first pass, the buffer is the correct and final size, however the bits reflect data stream order and not the order in the file format specification.
    Modification operations are performed in reverse order to move the bits to the correct order according to the file format specification.
    The seek position is updated for each modification operation to be at the point that it was when that modification operation's token was first encountered.
    For reversals and inversions, the construction operation is identical to the extraction operation because those operations are their own inverses. More complex operations are also given extraction and construction inverses which work as long as the pattern rules are followed.
        
Token class Specification:
    Tokens in a parsing pattern correspond to directives that are interpreted differently depending on whether the maker is an Extractor or a Constructor.

    The following templating expressions are used in the token grammar provided below:

    The following characters consistently follow the given themes. Knowing this can serve as a memory aid.
        ^ = Related to the beginning of something
        $ = Related to the end of something
        <n> = A positive integer number representing the size of a field
        <m> = A positive integer number representing a relative offset in the bit stream buffer
        <k> = A positive integer representing an offset in the bit stream format specification
        <i> = A positive integer representing an ID of some sort
        <x> = Denotes a marker in the bit stream of some sort
    e.g. u<n> could be written in an actual pattern as u5 or u100.

    Finite value tokens:
        Extractor context:
            The following token classes cause an Extractor to consume a specified number of bits and decode those bits in a specified way.
            The decoded value is inserted into the data stream and data structure.
        Constructor context:
            The following token classes cause a Constructor to consume a value from the data stream, encode it into bits, and insert it into the bit stream.

        u<n> = Represents an unsigned integer that is <n> bits long.
        s<n> = Represents a signed two's complement integer that is <n> bits long.
        f32 = Represents a single-precision floating point value (32 bits long).
        f64 = Represents a double-precision floating point value (64 bits long).
        x<n> = Represents a hex string (lower case) that is <n> bits long.
        X<n> = Represents a hex string (upper case) that is <n> bits long.
        b<n> = Represents a bin string that is <n> bits long.
        B<n> = Represents a bytes object that is <n> bits long. If the Endian-swap-all setting is enabled, the byte order will be reversed.
        C<n> = Equivalent to B<n> except that if the Endian-swap-all setting is enabled, the byte order will not be reversed. This does not decode the binary object into a string.
            Endianess refers to the numerical interpretation of values that consist of multiple bytes.
            A Little-Endian system treats the first byte as being least significant, and the last byte as being most significant.
            A Big-Endian system treats the first byte as being most significant, and the last byte as being least significant.
            By default all parsing in bitarchitect is Big-Endian. 
            Additionally, bitarchitect interprets the bits within a byte as being ordered from most significant to least signifcant.
            The Endian swap functionality reverses the order of all bytes without changing the order of the bits within each byte.
            This can be called as an explicit command, or can be applied via a setting that automatically performs an endian swap every time a value token is extracted.
            The C<n> token class ignores the endian swap setting and will never do an endian swap.

    Unbounded value tokens:
        Extractor context:
            The following token classes consume the remainder of the bit stream into one large value. 
            Constraints:
                The current bit seek position must be on a byte boundary or an exception will be raised.
        Constructor context:
            The following token classes insert the given value from the data stream into the bit stream regardless of their length.
            Constraints:
                The current bit seek position must be on a byte boundary or an exception will be raised.
            Non-extractable constraints:
                The given value of the data stream must be the last item in the data stream.

        B$ = Represents an unbounded bytes object
        C$ = Same as B$ except does not perform endian swapping if the endian-swap-all setting is enabled.
        
    Basic Bit stream Modifier Operations:
        Extractor context:
            The following token classes manipulate bits ahead of the current bit seek position without moving the current bit seek position forward.
        Constructor context:
            The following token classes are performed in reverse order after all bits have been written to the buffer.

        r<n> = Reverse the next n bits without moving the seek position
        r$ = Reverses all bits between the current position and the end of the set of data.
        r<m>.<n> = Reverse the n bits that are offset forward from the current seek position by m bits. Does not move the seek position.
        r<m>.$ = Reverse the remaining bits that are offset forward from the current seek position by m bits. Does not move the seek position. Inserts the calculated value of n into the data structure during extraction mode. Uses the value of n in the data structure during construction mode.

        i<n> = Invert the next n bits without moving the seek position
        i$ = Inverts all bits between the current position and the end of the set of data.
        i<m>.<n> = Invert the n bits that are offset forward from the current seek position by m bits. Does not move the seek position
        i<m>.$ = Inverts the remaining bits that are offset forward from the current seek position by m bits. Does not move the seek position. Inserts the calculated value of n into the data structure during extraction mode. Uses the value of n in the data structure during construction mode.

        e<n> = Endian swap. n must be a multiple of 8. Equivalent to reversing all n bits and then individually reversing each byte. Does not move the seek position.
            Note that this operation just shifts bytes around, it does not reflect any knowledge of whether the information being manipulated is actually number or not.

    Settings:
        In the expressions defining the following tokens, <t|y|n> refers to any of the three letters "t", "y", or "n".
            "y" is interpreted as yes or True
            "n" is interpreted as no or False
            "t" is interpreted as toggle from the current value i.e. yes -> no and no -> yes

        R<t|y|n>  = Reverse-all setting. When enabled, each read is preceded by a reversal for the same number of bits. e.g. u<n> is treated as r<n>u<n>
        I<t|y|n> = Invert-all setting. When enabled, each read is preceded by an inversion for the same number of bits. e.g. u<n> is treated as i<n>u<n>
        E<t|y|n> = Endian-swap all-setting. When enabled, each read is preceded by an endian swap. A read that is not a multiple of 8 bits will generate an exception. 
            Note that the Endianswap will normally reverse bytes every individual token extraction, with the exception of the C<n> token. 
            If, for example, you are extracting a string of 100 bytes with a single token, e.g. B800, 
            then those bytes will be reversed if the Endian-swap all setting is enabled. This may not be desired. 
            Only numbers are typically viewed as having endianness so that with something like u32, reversing the four bytes is desired.
            Little-endian applications would view a string of 100 bytes as corresponding to {B8}100 i.e. extracting 100 separate tokens where an endian-swap on a single byte has no effect.
            The downside of this is in bitarchitect is that the extracted data stream will have 100 separate single-character byte data items.
            The compromise is to use the C<n> token which will not perform Endian swapping regardless of the endian-swap-all setting.

    Constants:
        Extraction context:
            The following token classes move the bit seek position forward and may raise an Exception if a given assertion is not met. They do not produce any values in the data stream.
        Construction context:
            The following token classes write bits as specified.

        z<n> = Represents a sequence of zeros n bits long. Raises an exception if the extracted bits are not all zeros.
        o<n> = Represents a sequence of ones n bits long. Raises an exception if the extracted bits are not all ones.
        n<n> = The next n bits are don't cares that are skipped in extracting and will not raise any exceptions. In construction mode, this is equivlaent to z<n>.

    Sublisting (data structure hierarchy/nesting)
        In extraction mode, the following tokens determine the structure of the data structure and the structure of the record returned when maker() is called within a blueprint function.
        In construction mode, the tokens have no effect other than structuring the record returned when maker() is called within a blueprint function.
        [ = Start collecting items in a new sublist
        ] = End the current sublist

        See the maker sublist() method for an alternative via a python context manager

    Labels assignment:
        #"<label>" = Associate the previously extracted/constructed value with the label specified between the double quotes. Label names can consist of any characters besides the double quote character.
        !#"<label>"=<python_expr>; = Evaluate the python expression and associate it with the label. The label may not contain a double quote character. The python expression may not contain a semi-colon. If the semi-colon character is needed to be used in an expression, use an escape sequence (semi-colon is \\x3b). The expression should be a python literal, not refer to a variable.

    Assertions:
        =<python_expr>; = Assert the previously parsed value, decoded to final form (e.g. hex) is equal to the evaluation of the provided python expression. The python expression must not contain a semi-colon nor start with a pound sign (#). The expression should be a python literal, not refer to a variable.
        =#"<label>" = Assert the previously parsed value, decoded to final form (e.g. hex) is equal to the most recent value associated with the provided label

    Repetition:
        {<pattern>}<n> = Repeat the pattern n times
        {<pattern>}$ = Repeat until source stream is exhausted

    Comments:
        ##<any string> 

    Finite Pull:
        p<m>.<n> = Pulls the block of data offset that is forward by m bits and is length n to the current seek position. Equivalent to r<m+n> r<n> r<n>.<m>

        Pulls exchange the order of a selected region of bytes ahead of the seek position with the bytes between that region and the seek position. A pull with both offset and size explicitly specified is equivalent to three reversals:
            p<m>.<n> = r<m+n> r<n> r<n>.<m>
            The first reversal reverses m + n bits. 
            The result is that the n region is now ahead of the m region, but both regions are themselves reversed.
            The second reversal puts the n region in the correct order.
            The third reversal puts the m region in the correct order.
        Extraction context:
            The region of bits that is offset forward from the seek position by m bits, and is n bits long, is pulled to the current seek position. The m bits that were originally between the seek position and the start of the pulled region are placed after the bits that are being pulled.
            In this example, the seek position (denoted %) is at the end of the field labeled "s" below.
                +-----+--------+------+----------+
                |  s  %   m    |   n  |   e      |
                +-----+--------+------+----------+
            The fields "m" and "n" are <m> bits and <n> bits long respectively.
            The extraction operation p.<m>.<n> results in the following:
                +-----+------+--------+----------+
                |  s  %   n  |    m   |   e      |
                +-----+------+--------+----------+
        Construction context:
            Performs the same reversal operations as extraction but does these operations in reverse order i.e. r<n>.<m> r<n> r<m+n>
            p<m>.<n> can be thought of as the same as extraction but the m and n inputs have switched roles: it pulls a region of bits that is offset forward by n, and which is m bits long to the current seek position.
            In this example, the seek position (denoted %) is at the end of the field labeled "s" below.
                +-----+------+--------+----------+
                |  s  %   n  |    m   |   e      |
                +-----+------+--------+----------+
            The fields "m" and "n" are <m> bits and <n> bits long respectively.
            The construction operation p.<m>.<n> results in the following:
                +-----+--------+------+----------+
                |  s  %   m    |   n  |   e      |
                +-----+--------+------+----------+
        A pull is a modification operation that

    Unbounded Pull:
        p<m>.$ = Same as p<m>.<n> except that n corresponds to the remainder of the bit stream data following the m offset.
            Equivalent to calculating the length from the current position to the end, L, and setting n = L-m, then performing p<m>.<n>. 

            Extraction makes the top diagram become the bottom.
            Construction makes the bottom diagram become the top.
                +-----+--------+-----------------+
                |  s  %   m    |        e        |
                +-----+--------+-----------------+
                +-----+-----------------+--------+
                |  s  %         e       |    m   |
                +-----+-----------------+--------+
    Marker scan:
        In some cases, extractions require scanning the file for a particular byte pattern and parsing from that point on. The scan token must be initiated at a byte boundary.
        This is accounted for in bitarchitect by using markers.

        m^"<x>" = Initiate scan for marker. Marker must be located at a byte boundary. <x> is a hex literal that must correspond to a whole number of bytes. Usage of this token requires a matching consume marker token in the pattern as well for the blueprint to be constructible.
        m$"<x>" = Consume marker. Must be present once for every scan initiate.

        Extraction context:

            Suppose the bit stream diagramed here is being parsed:
                +-----+--------+-+------+
                |  s  %   m    |x|   n  |
                +-----+--------+-+------+

            Running m^"x" at this point will result in the following transformation:
                +-----+------+-+--------+
                |  s  %   n  |x|   m    |
                +-----+------+-+--------+
            This can be thought of as this:
                1) The bit stream is scanned from the current position until the <x> marker pattern is found.
                2) Everything after the marker pattern is pulled to the current seek position and before the marker pattern
                3) Everything that used to be before the marker pattern after the current seek position is moved after the marker.
            The marker must be consumed later in the stream with m$"<x>" or a non-constructable exception will be raised.
            This makes a sequence such as 'm^"FF" B!' a non-constructable sequence because the 'B!' token would consume the end markers.

        Construction context:
            In construction, the bit stream is at first fully constructed without any transformation operations applied.
            When the marker end token m$"<x>" is processed, that marker pattern is inserted into the bit stream.
            Transformation operations are evaluated in reverse to reorganize the bit stream into the final desired bit structure matching the format specification.
            Suppose the bit stream has been constructed and is in the process of being transformed according to the marker start directive.
            The bit stream looks like this:
                +-----+------+-+--------+
                |  s  %   n  |x|   m    |
                +-----+------+-+--------+

            The <m> sequence does not have the <x> pattern in it. If it did, redefine <m> to be everything to the right of the right-most marker pattern. 
            To execute the marker start directive:
                1) The bytestream is searched from right to left to look for the right-most occurrence of the <x> pattern.
                2) Everything to the right of the marker is swapped with everything to the left of the marker up to the bit seek position.

        See the maker marker() method for an alternative via a python context manager


    Absolute Jump:
        js<k>^<i> = Jump to an offset <k> after the start of the format specification. This jump is numerically labeled with label <i>.
        je<k>^<i> = Jump to an offset <k> before the end of the format specification. This jump is numerically labeled with label <i>.
        j$<i> = The end-jump marker associated with jump label <i> (explanation below).

        A jump is equivalent to an unbounded pull, except the offset provided is not interpreted as a bit stream buffer offset, but is instead an offset in terms of the bit stream format specification (i.e. the original bit stream for extraction, or the final bit stream for construction). 
        The provided offset in the jump token is called the format specification offset.
        This is translated into a buffer offset relative to the current seek position.
        Extraction context:
            In extraction context, this translation is based on applying all preceding modification operations to the target format specification position. In extraction context, all preceding modifications have been applied and are known.
            If the resulting buffer offset is positive, then the selected position is ahead in the buffer and is valid. If the resulting buffer offset is negative, then the selected position is a position that has already been extracted in extraction context. This would allow an extraction to consume the same bits multiple times would produce a data stream incompatible with the construction algorithm since the construction algorithm would not know which parameters need to overwrite the bits that previous parameters were used to write. Thus a negative buffer offset will result in a non-constructible exception.

        Construction context:
            In construction context, preceding modifications have not yet been applied and are applied in reverse order (meaning after the current jump is applied). Preceding modifications that depend on successfully transforming data according to subsequent modifications (such as markers or other jumps) cannot be evaluated in order to evaluate the current jump operation. A separate approach with additional information is required to make this operation constructible. This information cannot be part of the bit stream because format specifications are typically fixed by external organizations. It should not be part of the data stream because it introduces an data interdependency that is difficult to get right that every user of the blueprint for construction will need to deal with. The additional information must therefore come from the blueprint itself.
            The construction jump problem involves determining how to transform the bottom diagram below into the top diagram when neither e or m are known by providing additional information in the blueprint that is intuitively natural for the blueprint author to conceptualize as part of the extration process.
                +-----+--------+-----------------+
                |  s  %   m    |        e        |
                +-----+--------+-----------------+
                +-----+-----------------+--------+
                |  s  %         e       |    m   |
                +-----+-----------------+--------+
        The solution is for the blueprint author to apply the jump as normal in extraction, but to treat the boundary between "e" and "m" in the bottom diagram as having a special jump-related bit marker "x" that needs to be consumed with a special token. This token should be treated as if it really exists in the bit stream. It should be considered to have zero-length. If subject to transformations from reversals, pulls, markers, other jumps, etc, this zero-length marker stays attached to the real bit to its direct right.
                +-----+--------+-----------------+
                |  s  %   m    |        e        |
                +-----+--------+-----------------+
                +-----+----------------+-+--------+
                |  s  %         e      |x|    m   |
                +-----+----------------+-+--------+
        This end marker must be unambiguously associated with the current jump so that the end markers for two different jumps each be associated with the correct jump.
        The operation above in its simplest can be treated as:
            js<k>^0 u<e> j$0 u<m>
        It is fine for the jump marker to be translated to different areas, it just needs to be consumed when it is reached.

        See the maker jump() method for an alternative via a python context manager

    Relative Jumps:
        Relative jumps are similar to absolute jumps except that instead of offset <k> being from the absolute start or end of the format specification, this offset is interpreted from the current seek position translated to the corresponding current format specification position.

        jf<k>^<i> = Move forward in the format specification by <k> bits relative to the current seek position as evaluated from the format specification. Label this as jump <i>.
        jb<k>^<i> = Move backwards in the format specification by <k> bits relative to the current seek position as evaluated from the format specification. Label this as jump <i>.
        j$<i> = Jump marker terminator (same as for absolute jump)

        Extraction Context:
            The current buffer seek position is translated to a position in the format specification by applying all preceding reversal operations in reverse order. The offset <k> is either added or subtracted to this position, and the resulting offset is re-translated back to a buffer position and a relative buffer offset <m> is calculated. The subsequent processing is the same as for an absolute jump.
        Construction Context:
            The processing is identical to an absolute jump and relies soley on the blueprint author inserting the end jump marker correctly.

        See the maker jump() method for an alternative via a python context manager

    Counts:

"""
import re, ast, io, struct
from enum import Enum
from math import ceil
from .bits_io import SEEK_SET, SEEK_CUR, SEEK_END, uint_to_bytes, bytes_to_uint, BitsIO, reverse_bytes, invert_bytes
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
    CHAR = 9 #char object (same as bytes except ignores endian-swap-all setting)

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
    elif encoding == Encoding.BYTS or encoding == Encoding.CHAR:
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
    >>> from .formats import to_hex
    >>> to_hex(struct.pack('>f',math.pi))
    b'40490fdb'
    >>> '%08x' % uint_encode(math.pi,32,Encoding.SPFP)
    '40490fdb'
    >>> import struct, math
    >>> from .formats import to_hex
    >>> to_hex(struct.pack('>d',math.pi))
    b'400921fb54442d18'
    >>> '%08x' % uint_encode(math.pi,64,Encoding.DPFP)
    '400921fb54442d18'
    >>> uint_encode('110010100101',32,Encoding.BINS)
    3237
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
        return bytes_to_uint(struct.pack('>f',value))[0]
    elif encoding == Encoding.DPFP:
        result = bytes_to_uint(struct.pack('>d',value))[0]
        return result
    elif encoding == Encoding.LHEX or encoding == Encoding.UHEX:
        return int(value,16)
    elif encoding == Encoding.BINS:
        return int(value,2)
    elif encoding == Encoding.BYTS or encoding == Encoding.CHAR:
        return bytes_to_uint(value)[0]

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
