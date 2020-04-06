"""
The purpose of this module is to provide a file-like object called BitsIO that behaves like
BytesIO except that reads, writes, seeks, and other common methods operator at the bit level instead of the byte level.
"""

import io
from math import log, floor, ceil
def min_bits_uint(uint):
    """
    This function calculates the minimum number of bits needed to represent a given unsigned integer value.

    >>> min_bits_uint(100)
    7
    >>> min_bits_uint(254)
    8
    >>> min_bits_uint(255)
    8
    >>> min_bits_uint(256)
    9
    >>> min_bits_uint(257)
    9
    """
    return int(floor(1+log(uint,2))) if uint > 0 else 0

def invert_uint(uint,num_bits=None):
    """
    This function takes an unsigned integer and inverts all of its bits.
    num_bits is number of bits to assume are present in the unsigned integer.
    If num_bits is not specified, the minimum number of bits needed to represent the unsigned integer is assumed.
    If num_bits is specified, it must be greater than the minimum number of bits needed to represent the unsigned integer.

    >>> invert_uint(0,3) # 000 -> 111
    7
    >>> invert_uint(12,4) # 1100 -> 0011
    3
    """
    if not isinstance(uint,int):
        raise Exception('input must be an integer, not %s' % repr(type(uint)))
    if uint < 0:
        raise Exception('input must be non-negative: %s' % repr(uint))
    if min_bits_uint(uint) > num_bits:
        raise Exception('Input uint must be storable in at most num_bits (%d) number of bits, but requires %d bits' % (num_bits,min_bits_uint(uint)))
    min_bits = min_bits_uint(uint)
    if num_bits is not None and num_bits < min_bits:
        raise Exception('num_bits set to %d but %d bits are needed to represent %d' % (num_bits,min_bits,uint))
    if num_bits is None:
        num_bits = min_bits 
    return uint ^ ((1<<num_bits)-1)


def reverse_uint(uint,num_bits=None):
    """
    This function takes an unsigned integer and reverses all of its bits.
    num_bits is number of bits to assume are present in the unsigned integer.
    If num_bits is not specified, the minimum number of bits needed to represent the unsigned integer is assumed.
    If num_bits is specified, it must be greater than the minimum number of bits needed to represent the unsigned integer.
    >>> reverse_uint(3,8)
    192
    >>> bin(192)
    '0b11000000'
    """
    if not isinstance(uint,int):
        raise Exception('input must be an integer, not %s' % repr(type(uint)))
    if uint < 0:
        raise Exception('input must be non-negative: %s' % repr(uint))
    if min_bits_uint(uint) > num_bits:
        raise Exception('Input uint must be storable in at most num_bits (%d) number of bits, but requires %d bits' % (num_bits,min_bits_uint(uint)))
    result = 0
    extracted_bits = 0
    while (num_bits is not None and extracted_bits < num_bits) or uint != 0:
        uint,rem = divmod(uint,2)
        result = (result<<1) | rem
        extracted_bits += 1
    return result
"""
These tables are precalculated to be used in the functions within this module
"""
reverse_byte_table = {value:reverse_uint(value,8) for value in range(256)}
invert_byte_table = {value:invert_uint(value,8) for value in range(256)}
def reverse_bytes(b):
    return b''.join([reverse_byte_table[x] for x in b[::-1]])
def invert_bytes(b):
    return b''.join([invert_byte_table[x] for x in b])

SEEK_SET = io.SEEK_SET
SEEK_CUR = io.SEEK_CUR
SEEK_END = io.SEEK_END
def ones_block(length,lshift=0):
    return ((1<<length)-1)<<lshift

def lmask_byte(num_mask_bits,value):
    """
    This function applies a left-justified mask of a specified number of bits to an unsigned integer representing a single byte value.
    >>> lmask_byte(3,list(b'\\xff')[0])
    224
    >>> bin(224)
    '0b11100000'
    """
    return (((1<<(num_mask_bits))-1)<<(8-num_mask_bits)) & value

def rmask_byte(num_mask_bits,value):
    """
    This function applies a right-justified mask of a specified number of bits to an unsigned integer representing a single byte value.
    >>> rmask_byte(3,list(b'\\xff')[0])
    7
    >>> bin(7)
    '0b111'
    """
    return ((1<<(num_mask_bits))-1) & value



def bytes_to_uint(byte_data,lstrip=0,rstrip=0,reverse=False,invert=False):
    """
    This function takes a bytes object and converts it into a single unsigned integer. It assumes a Big Endian interpretation (first byte is more significant than last byte).
    
    If lstrip is set to a positive integer less than or equal to the number of bits within the bytes object, then that many MSBs will be zeroed out in the first byte. This applies to bits in the original byte stream, i.e. before a reversal is done if reverse is set to True.

    If rstrip is set to a positive integer less than or equal to the number of bits within the bytes object, then that many LSBs will be zeroed out in the last byte. This applies to bits in the original byte stream, i.e. before a reversal is done if reverse is set to True.

    If reverse is set to True, then an unsigned integer with the reversed binary representation will be returned (MSB of entire int becomes LSB).

    If invert is set to True, then every bit of the unsigned integer will be inverted.

    >>> bytes_to_uint(b'hello world')
    (126207244316550804821666916, 88)
    """
    num_bits = len(byte_data)*8-lstrip-rstrip
    n = len(byte_data)
    if invert:
        #flip the value of all bytes
        byte_data = [invert_byte_table[value] for value in byte_data]
    if lstrip > 0:
        if lstrip <= len(byte_data)*8:
            lstrip_bytes,lstrip = divmod(lstrip,8)
            byte_data = byte_data[lstrip_bytes:] #remove bytes from the front
            if len(byte_data) > 0:
                byte_data[0] = rmask_byte(8-lstrip,byte_data[0]) #strip off bits in the first byte
        else:
            raise Exception('lstrip value of %d exceeded number of bits in bytes object (%d)' % (lstrip,len(bytes_data*8)))

    elif lstrip < 0:
        raise Exception('lstrip (%d) must be non-negative' % lstrip)

    if rstrip > 0:
        if rstrip <= len(bytes_data)*8:
            rstrip_bytes, rstrip = divmod(rstrip, 8)
            byte_data = byte_data[:-rstrip_bytes] #remove bytes from the end
            if len(bytes_data) > 0:
                byte_data[-1] = lmask_byte(8-rstrip,byte_data[-1]) #strip of bits in the last byte
        else:
            raise Exception('rstrip value of %d exceeded number of bits in bytes object (%d)' % (rstrip,len(bytes_data*8)))
    elif rstrip < 0:
        raise Exception('rstrip (%d) must be non-negative')
    
    if reverse:
        #reverse the order across bytes and reverse the order of bits within bytes
        byte_data =[reverse_byte_table[value] for value in byte_data[::-1]]
    result = sum((b<<(8*(n-p-1))) for p,b in enumerate(byte_data))
    if not reverse:
        return (result >> rstrip,num_bits)
    else:
        return (result >> lstrip,num_bits)


def uint_to_bytes(uint,num_bits=None,loffset=0,lvalue=0,rvalue=0,reverse=False,invert=False):
    """
        This function takes an unsigned integer and converts it into a bytes object.

        num_bits = How many LSBs are extracted from the unsigned integer to construct the byte stream. If not specified, assume it is the minimum number of bits required to fully represent the unsigned integer. Setting num_bits to any number less than this minimum value will result in an exception being generated.

        The result is right-justified within the specified num_bits, but by default, the result num_bits themselves will be left-justified within the overall bytes object. A value of 7 with num_bits=3 would produce a the byte 11100000 or \\xE0. A value of 7 with num_bits=4 would produce the byte 01110000 or \\x70.

        The result is right-shifted within the bytes object by a number of bits equal to loffset which must be between 0 and 7 inclusive.

        If the result is right-shifted, the MSBs of the single byte value provided in lvalue will be used to fill the area that was shifted.

        If the result is not a perfect multiple of 8-bits, the final byte of the bytes object will be filled with the LSBs of the single byte value provided in rvalue.

        Setting reverse to True will reverse the order of all bytes and all bits within each byte.

        Setting inverse to True will invert every bit.

    >>> uint_to_bytes(126207244316550804821666916,88)
    b'hello world'
    """
    if not isinstance(uint,int):
        raise Exception('Input uint must be an integer, not %s' % repr(type(uint)))
    if uint < 0:
        raise Exception('Input uint must be non-negative: %s' % repr(uint))
    if loffset >= 8 or loffset < 0:
        raise Exception('loffset must be between 0 and 7 inclusive')
    if lvalue < 0 or lvalue > 255:
        raise Exception('lvalue must be between 0 and 255 inclusive')
    if rvalue < 0 or rvalue > 255:
        raise Exception('rvalue must be between 0 and 255 inclusive')
    
    min_bits = min_bits_uint(uint)
    if num_bits is not None and min_bits > abs(num_bits):
        #this should ensure that the uint does not contain 1s that go beyond what num_bits says it should
        raise Exception('Input uint must be storable in at most num_bits (%d) number of bits, but requires %d bits' % (num_bits,min_bits))
    if num_bits is None:
        num_bits = min_bits
    num_bytes = int(ceil(num_bits/8)) #number of bytes required to represent the number
    extra_bits = num_bytes*8 - num_bits #number of extra bits if no shifting were to be done - these bits should be 0 due to constraint that num_bits is greater than or equal to min_bits

    #Extracting bits from a number involves the modulo and division operations.
    #LSBs are naturally extracted before MSBs.
    #This results in the byte values being constructed in reverse order i.e. first byte contains LSBs
    #The result is reversed at the end of this function to produce the bytes in the correct order (MSB first)

    if not reverse:
        #roffset is the extra number of LSBs added to uint to make it the right number of total bits
        roffset = extra_bits - loffset #extra bits will be padded on right side (minus loffset adjustment)
        
        #check if the shift due to loffset pushes the result into having an extra byte
        if roffset < 0:
            num_bytes += 1
            roffset += 8
        uint <<= (roffset)
    else:
        #Due to reversal, the LSB of uint will be the MSB of the final result
        #loffset is the amount of MSB padding on the final result, so it may be inserted as an LSB shift against the initial uint
        uint <<= loffset
        roffset = extra_bits - loffset

        #check if the shift due to loffset pushes the result into having an extra byte
        if roffset < 0:
            num_bytes += 1
            roffset += 8

    #extract byte data from uint
    byte_data = []
    for byte_i in range(num_bytes):
        uint,value = divmod(uint,256)
        byte_data.append(value)
    #perform reversal if requested
    if reverse:
        byte_data =[reverse_byte_table[value] for value in byte_data[::-1]]
    #perform inversion if requested
    if invert:
        byte_data = [invert_byte_table[value] for value in byte_data]

    #replace the loffset MSBs of the byte that will ultimately be the first byte (but is currently the last byte) with the MSBs from lvalue
    if loffset > 0:
        first_byte_rmask = 8-loffset
        byte_data[-1] = rmask_byte(first_byte_rmask,byte_data[-1]) | lmask_byte(loffset,lvalue)
    
    #replace the roffset LSBs of the byte that will ultimately be the last byte (but is currently the first byte) with the LSBs from rvalue
    if roffset > 0:
        last_byte_lmask = 8-roffset
        byte_data[0] = lmask_byte(last_byte_lmask,byte_data[0]) | rmask_byte(roffset,rvalue)

    #reverse the bytes
    return bytearray(byte_data[::-1])


class BitsIO(object):

    """
    This class imitates a normal bytes file reader but works on the level of individual bits (not bytes).

    seek() and tell() correspond to a bit position (assume Big Endian interpretation).

    read() and write() correspond to reading/writing sequences of bits.

    Reading returns an unsigned integer corresponding to the value of the specified number of bits beginning at the current seek position. Reading moves the seek position forward by the specified number of bits. 
    
    The peek() method is the same as read() except that it does not move the seek position forward. Note that if the underlying byte source object does not directly support peeking, this will be equivalent to performing a tell(), reading, and seeking back to the tell() point.

    Writing takes an unsigned integer and writes its value according to the number of specified bits into the stream at the current seek position.

    >>> b = BitsIO(b'hello world')
    >>> b.read(8)
    (104, 8)
    >>> chr(104)
    'h'
    >>> bin(104)
    '0b1101000'
    >>> b.seek(-4,SEEK_CUR)
    4
    >>> b.tell()
    4
    >>> b.write(0,1) #write a zero value of size 1 bit
    >>> bytes(b)
    b'`ello world'
    >>> bin(ord('`'))
    '0b1100000'
    >>> bin(ord('h'))
    '0b1101000'
    """
    def __init__(self,byte_source=None):
        """
        This class may be initialized with either a bytes object or a file-like object.

        If initialized with a bytes object, the bytes object will be wrapped in a BytesIO object to make a mutable copy. The mode property of the BitsIO object will be set to "rb+" and the seek position will be 0.

        If initialized with a file-like object, the file object should be opened in binary mode. The mode property will be set to the mode of the file object if it exists, otherwise it will be "rb+". The seek position will correspond to the first bit (MSB) of the current byte of the file-like object.
        """
        self.original_byte_source = byte_source
        #if provided None, create an empty BytesIO object
        if byte_source is None:
            self.byte_source = io.BytesIO()
            self.mode = 'rb+'
        #if provided a bytes object, wrap it in a BytesIO object to make a mutable copy
        if isinstance(byte_source,(bytes,bytearray,memoryview)):
            self.byte_source = io.BytesIO(byte_source)
            self.mode = 'rb+'
        elif isinstance(byte_source,(io.BufferedIOBase,io.BufferedRandom,io.BufferedReader,io.BytesIO)):
            if hasattr(byte_source,'mode'):
                if not 'b' in byte_source.mode:
                    raise Exception('File-like object provided to BitsIO must be opened in binary mode i.e. must have "b": mode = %s' % byte_source.mode)
                if not '+' in byte_source.mode:
                    pos = byte_source.tell()
                    byte_source.seek(0)
                    self.byte_source = io.BytesIO(byte_source.read())
                    self.byte_source.seek(pos)
                    byte_source.seek(pos)
                    self.mode = 'rb+'
                else:
                    self.byte_source = byte_source
                    self.mode = byte_source.mode
            else:
                self.mode = 'rb+'
        else:
            raise Exception('Invalid object for BitsIO byte_source: %s' % repr(type(byte_source)))
        self.bit_seek_pos = self.byte_source.tell()*8
    def close(self):
        """
        Pass through function to encapsulated file/IO close() method
        """
        del self.mode
        self.byte_source.close()
    def closed(self):
        """
        Pass through function to encapsulated file/IO closed() method
        """
        return self.byte_source.closed()
    def __enter__(self):
        """
        No special behavior is performed when entering this object as a context manager.
        The object will be closed however when the context is ended.
        """
        pass
    def __exit__(self,exc_type,exc_value,exc_traceback):
        """
        The object is closed when it is used as a context manager and the context ends.
        """
        self.close() 

    def flush(self):
        """
        Pass through function to encapsulated file/IO flush() method
        """
        return self.byte_source.flush()

    def isatty(self):
        """
        Pass through function to encapsulated file/IO isatty() method
        """
        return self.byte_source.isatty()

    def readable(self):
        """
        Pass through function to encapsulated file/IO isatty() method
        """
        return self.byte_source.readable()


    def at_eof(self):
        """
        If True, then the seek pointer is at the end of the file.
        If a file-like object has X bytes, this corresponds to the seek pointer being at bit 8*X.
        
        """
        if hasattr(self.byte_source,'get_buffer'):
            size_bytes = len(self.byte_source.get_buffer())
            return (self.bit_seek_pos//8) >= size_bytes
        elif hasattr(self.byte_source,'peek'):
            return len(self.byte_source.peek(1)) == 0
        elif hasattr(self.byte_source,'read') and hasattr(self.byte_source,'seek') and hasattr(self.byte_source,'tell'):
            tell = self.byte_source.tell()
            result = len(self.byte_source.read(1)) == 0
            self.byte_source.seek(tell)
            return result
        else:
            raise Exception('Byte source does not support a way of determining if at EOF or not')

    def seek(self,offset_bits,whence=SEEK_SET):
        """
        Seeks to a bit position.

        The whence parameter can be set to one of the following three values (defined in this module):
            SEEK_SET = Seek to an offset relative to the beginning (0 is the first bit)
            SEEK_CUR = Seek to an offset relative to the current position (0 is the current bit)
            SEEK_END = Seek to an offset relative to the end (0 is the last bit)
        
        offset_bits can be negative to seek to positions earlier than the reference.
        Seeking to a position before the start of the file may generate an exception.

        """

        #divmod handles positive and negative offsets correctly
        offset_bytes, remainder_bits = divmod(offset_bits,8)
        self.byte_source.seek(offset_bytes,whence)
        self.bit_seek_pos = self.byte_source.tell()*8 + remainder_bits
        return self.bit_seek_pos
        
    def seekable(self):
        """
        Pass through function to encapsulated file/IO seekable() method
        """
        return self.byte_source.seekable()

    def tell(self):
        """
        Returns the current bit seek position (not byte)
        """
        return self.bit_seek_pos

    def writable(self):
        """
        Pass through function to encapsulated file/IO writeable() method
        """
        return self.byte_source.writable()

    def truncate(self,size_bits):
        """
        Truncates the file according to the number of bits (rounded up to the nearest multiple of 8).
        If there are LSBs in the last byte that go beyond the setting of size_bits, those bits will be set to zero.

        The seek position is not changed by this operation.
        """
        pos = self.bit_seek_pos
        size_bytes, remainder_bits = divmod(size_bits,8)
        if remainder_bits > 0:
            effective_size_bytes = size_bytes + 1
        else:
            effective_size_bytes = size_bytes
        new_size_bytes = self.byte_source.truncate(effective_size_bytes)
        if remainder_bits > 0:
            self.byte_source.seek(-1,io.SEEK_END)
            byte_value = list(self.byte_source.read(1))
            self.byte_source.seek(-1,io.SEEK_END)
            masked_byte_value = lmask_byte(remainder_bits,byte_value)
            self.byte_source.write(bytes([masked_byte_value]))
        self.seek(pos)

    def __len__(self):
        """
        Returns the total number of bits in the underlying object.
        """
        pos = self.tell()
        end = self.seek(0,io.SEEK_END)
        self.seek(pos)
        return end

    def read(self,n=None,reverse=False,invert=False):
        """
        Reads the specified number of bits from the current seek position.
        If n is negative, read backwards from the current seek position (reversing the bits).
        If num_bits is not specified, the remainder of the bytes content is read into a single unsigned integer.

        Returns the unsigned integer value of the bits read, as well as the absolute number of bits read.
        """

        if n is None:
            n = len(self) - self.tell()
        if not isinstance(n,int):
            raise Exception('input n must be int, not %s' % repr(type(n)))
        if n == 0:
            return 0,0
        start_pos = self.bit_seek_pos
        end_pos = self.bit_seek_pos + n
        start_byte_pos,start_remainder_bits = divmod(start_pos,8)
        end_byte_pos,end_remainder_bits = divmod(end_pos,8)
        offset_bytes = end_byte_pos - start_byte_pos
        if n > 0: #read forwards
            num_bytes = offset_bytes
            if end_remainder_bits > 0:
                num_bytes += 1
                rstrip = 8 - end_remainder_bits
            else:
                rstrip = 0
            lstrip = start_remainder_bits
        elif n < 0: #read backwards
            num_bytes = -offset_bytes
            if start_remainder_bits > 0:
                num_bytes += 1
                rstrip = 8 - start_remainder_bits
            else:
                rstrip = 0
            self.byte_source.seek(offset_bytes,io.SEEK_CUR)
            reverse = not reverse
            lstrip = end_remainder_bits
        else:
            raise Exception('Provided value not comparable to zero: %s' % repr(n))
        byte_data = self.byte_source.read(num_bytes)
        value,num_bits = bytes_to_uint(byte_data,lstrip,rstrip,reverse,invert)
        self.seek(end_pos)
        return value,num_bits

    def peek(self,n=None):
        """
        Same arguments and return value as read() except that the current seek position is not changed.
        """
        pos = self.bit_seek_pos
        value,num_bits = self.read(n)
        self.seek(pos)
        return value,num_bits

    def write(self,value,n=None,reverse=False,invert=False):
        """
        Writes an unsigned integer value as bits at the current seek position.
        Takes an unsigned integer as well as the number of bits.
        The unsigned integer value will be right-justified within the specified number of bits.
        The specified number of bits will be left-justified within the bytes object starting at the current bit seek position.

        If n is negative, the value will be written in reverse backwards from the current seek position.
        """
        if not isinstance(n,int):
            raise Exception('input n must be int, not %s' % repr(type(n)))
        if n == 0:
            return
        start_pos = self.bit_seek_pos
        end_pos = self.bit_seek_pos + n
        start_byte_pos,start_remainder_bits = divmod(start_pos,8)
        end_byte_pos,end_remainder_bits = divmod(end_pos,8)
        offset_bytes = end_byte_pos - start_byte_pos
        if n > 0:
            first_byte_pos = start_byte_pos
            loffset = start_remainder_bits
            last_byte_pos = end_byte_pos
        else:
            first_byte_pos = end_byte_pos
            last_byte_pos = start_byte_pos
            loffset = end_remainder_bits
            self.byte_source.seek(end_byte_pos)
            reverse = not reverse
        if loffset > 0:
            first_byte =  list(self.byte_source.read(1))[0]
        else:
            first_byte = 0
        last_byte_lmask = ((loffset + n)%8)
        roffset = (8 - last_byte_lmask)%8
        if roffset > 0:
            self.byte_source.seek(last_byte_pos)
            last_byte = list(self.byte_source.read(1))[0]
        else:
            last_byte = 0
        self.byte_source.seek(first_byte_pos)
        byte_data = uint_to_bytes(value,n,loffset,first_byte,last_byte,reverse,invert)
        self.byte_source.write(byte_data)
        self.seek(end_pos)
    def reverse(self,n=None):
        """
        Reverses the next n bits in the byes object without changing the current seek position.
        If n is not specified, then reverse all bits from the current position to the end.
        """
        start_pos = self.tell()
        value,num_bits = self.read(n)
        value = reverse_uint(value,num_bits)
        self.seek(start_pos)
        self.write(value,num_bits)
        self.seek(start_pos)
    def invert(self,n=None):
        """
        Inverts the next n bits in the byes object without changing the current seek position.
        If n is not specified, then invert all bits from the current position to the end.
        """
        start_pos = self.tell()
        value,num_bits = self.read(n)
        value = invert_uint(value,num_bits)
        self.seek(start_pos)
        self.write(value,num_bits)
        self.seek(start_pos)
    def __bytes__(self):
        if hasattr(self.byte_source,'getbuffer'):
            return bytes(self.byte_source.getbuffer())
        else:
            pos = self.tell()
            self.seek(0)
            result = self.byte_source.read()
            self.seek(pos)
            return result
    def read_bytes(self,n=None,reverse=False,invert=False):
        """
        Reads the remaining bytes of the file as a bytes object

        To account for the situation where the current seek position is in the  middle of the byte, the unsigned integer representation of the remaining bits in that byte as well as the number of bits are also returned in addition to the remaining bytes data.
        Returns (bytes_data,first_byte_value,first_byte_bits)
        """
        rmask = 8-(self.bit_seek_pos % 8)
        self.byte_source.seek(self.seek_bit_pos//8)
        if n is None:
            rest = self.byte_source.read()
        else:
            rest = self.byte_source.read(n)
        first_value = rmask_byte(rmask,rest[0])
        self.seek(0,io.SEEK_END)
        return (first_value,rmask,rest[1:])
    def write_bytes(self,bytes_data,first_byte_value=None,first_byte_bits=None):
        """
        Writes bytes.
        To account for the situation of the current seek position being in the middle of a byte, the integer value of that first value and the number of bits can be supplied. The number of bits, if provided, will be validated against the current seek position.

        If the first_byte_value is not provided, it is assumed to be zero.
        """
        rmask = 8-(self.bit_seek_pos % 8)
        if first_byte_bits is not None and first_byte_bits != rmask:
            raise Exception('write_bytes inputs designate that %d bits are expected in the current byte, however only %d bits are left in the current byte based on bit seek position' % (first_byte_bits,rmask))

        if first_byte_value is None:
            first_byte_value = 0
        self.write(first_byte_value,first_byte_bits)
        self.byte_source.write(bytes_data)
        self.seek(0,io.SEEK_END)
        
    def find(self,sub):
        """
        Finds a byte substring relative to the current seek position
        """
        pos = self.tell()
        if pos % 8 != 0:
            raise Exception('find() method requires bit position to be a multiple of 8')
        byte_pos = pos//8
        if hasattr(self.byte_source,'getbuffer'):
            data = bytes(self.byte_source.getbuffer())[byte_pos:]
        else:
            data = self.byte_source.read()
            self.byte_source.seek(byte_pos)
        byte_offset = data.find(sub)
        bit_offset = byte_offset*8
        return bit_offset

