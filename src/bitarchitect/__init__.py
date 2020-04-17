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
import importlib
from .bit_utils import *
from .bits_io import *
from .pattern import *
from .maker import *
blueprints = importlib.import_module('bitarchitect.blueprints')

__version__ = '0.0.1'
