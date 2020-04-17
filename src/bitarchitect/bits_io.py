"""
The purpose of this module is to provide a file-like object called BitsIO that behaves like
BytesIO except that reads, writes, seeks, and other common methods operator at the bit level instead of the byte level.
"""

import io
from enum import Enum
from .bit_utils import *

SEEK_SET = io.SEEK_SET
SEEK_CUR = io.SEEK_CUR
SEEK_END = io.SEEK_END

class ByteSourceType(Enum):
    BUFFER = 1
    SOURCE = 2

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
    def __init__(self,byte_source=None,byte_source_type = ByteSourceType.BUFFER):
        """
        """
        self.original_byte_source = byte_source
        self.byte_source_type = byte_source_type
        if byte_source_type == ByteSourceType.BUFFER:
            if byte_source is None:
                self.byte_source = io.BytesIO()
            elif isinstance(byte_source,(bytes,bytearray,memoryview)):
                self.byte_source = io.BytesIO(byte_source)
            elif isinstance(byte_source,(io.BufferedIOBase,io.BufferedRandom,io.BufferedReader,io.BytesIO)):
                if hasattr(byte_source,'mode'):
                    if not 'b' in byte_source.mode:
                        raise Exception('File-like object provided to BitsIO must be opened in binary mode i.e. must have "b": mode = %s' % byte_source.mode)
                pos = byte_source.tell()
                byte_source.seek(0)
                self.byte_source = io.BytesIO(byte_source.read())
                self.byte_source.seek(pos)
                byte_source.seek(pos)
            else:
                raise Exception('Incompatible byte_source: %s' % repr(byte_source))

        elif byte_source_type == ByteSourceType.SOURCE:
            self.byte_source = byte_source

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
        bytes_data = self.byte_source.read(num_bytes)
        value,num_bits = bytes_to_uint(bytes_data,lstrip,rstrip,reverse,invert)
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
        bytes_data = uint_to_bytes(value,n,loffset,first_byte,last_byte,reverse,invert)
        self.byte_source.write(bytes_data)
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

