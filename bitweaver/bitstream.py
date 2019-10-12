import io
import codecs
from math import log, floor, ceil

def byte_encode(bytes_obj,codec):
    """
    codec =
        binstring : b'\\xa0' -> b'10100000'
        hex       : b'\\xff' -> b'FF' 
        base64    : b'\\xc2' -> b'wg==\\n'  
        bz2       : uncompressed -> compressed
        quopri    : b'\\xab' -> b'=AB'
        uu        : b'\\x92' -> b'begin 666 <data>\\n!D@  \\n \\nend\\n'
        zip       : uncompressed -> compressed
        zlib      : uncompressed -> compressed

    >>> byte_decode(b'1111000010100101','binstring')
    b'\xf0\xa5'
    >>> byte_encode(_,'binstring')
    b'1111000010100101'
    """
    return codecs.encode(bytes_obj,codec)
def byte_decode(bytes_obj,codec):
    """
    codec =
        binstring : b'10100000' -> b'\\xa0'
        hex       : b'FF' -> b'\\xff' 
        base64    : b'wg==\\n' -> b'\\xc2'
        bz2       : compressed -> uncompressed
        quopri    : b'=AB' -> b'\\xab'
        uu        : b'begin 666 <data>\\n!D@  \\n \\nend\\n' -> b'\\x92'
        zip       : compressed -> uncompressed
        zlib      : compressed -> uncompressed
    """
    return codecs.decode(bytes_obj,codec)

def binstring_decode(binstring,errors=None):
    byte_data = []
    if len(binstring) % 8 != 0:
        raise Exception('binstring input length must be a multiple of 8: length = %d' % len(binstring))
    for i in range(0,len(binstring),8):
        #bs = binstring[i:i+8].ljust(8,b'0')
        bs = binstring[i:i+8]
        byte_data.append(int(bs,2))
    return (bytes(byte_data),len(byte_data)*8)

def binstring_encode(bytes_data,errors=None):
    """
    >>> b = binstring_encode('hello world')
    >>> b
    (b'0110100001100101011011000110110001101111001000000111011101101111011100100110110001100100', 11)
    >>> binstring_decode(b[0])
    (b'hello world', 88)
    """
    if isinstance(bytes_data,str):
        bytes_data = bytes_data.encode()
    s_data = []
    for value in bytes_data:
        s_data.append(bin(value)[2:].encode().zfill(8))
    return (b''.join(s_data),len(s_data))
class StreamReader_binstring(codecs.StreamReader):
    def __init__(self,stream,errors='strict'):
        #super(StreamReader_binstring,self).__init__(stream,errors)
        self.stream = stream
    def read(self,size=None,chars=None,firstline=None):
        if chars is not None:
            size = chars*8
            return binstring_decode(self.stream.read(size))
    def reset(self):
        self.stream.flush()
class StreamWriter_binstring(codecs.StreamWriter):
    def __init__(self,stream,errors='strict'):
        #super(StreamWriter_binstring,self).__init__(stream,errors)
        self.stream = stream
    def write(self,b):
        self.stream.write(binstring_encode(b))
    def reset(self):
        self.stream.flush()


def codec_search_function(codec_name):
    """
    >>> codecs.decode(b'1111000010100101','binstring')
    b'\\xf0\\xa5'
    >>> codecs.encode(_,'binstring')
    b'1111000010100101'
    """
    if codec_name == 'binstring' or codec_name == 'binstring_codec':
        return codecs.CodecInfo(encode=binstring_encode,decode=binstring_decode,streamwriter=StreamWriter_binstring,streamreader=StreamReader_binstring)
codecs.register(codec_search_function)

def bytes_to_uint(byte_data,lstrip=0,rstrip=0,reverse=False,invert=False):
    """
    >>> bytes_to_uint(b'hello world')
    (126207244316550804821666916, 88)
    """
    byte_data = list(byte_data)
    num_bits = len(byte_data)*8-lstrip-rstrip
    n = len(byte_data)
    if invert:
        byte_data = [invert_byte_table[value] for value in byte_data]
    if lstrip != 0:
        byte_data[0] = rmask_byte(8-lstrip,byte_data[0])
    if rstrip != 0:
        byte_data[-1] = lmask_byte(8-rstrip,byte_data[-1])
    if reverse:
        byte_data =[reverse_byte_table[value] for value in byte_data[::-1]]
    result = sum((b<<(8*(n-p-1))) for p,b in enumerate(byte_data))
    if not reverse:
        return (result >> rstrip,num_bits)
    else:
        return (result >> lstrip,num_bits)

def uint_to_bytes(uint,num_bits=None,loffset=0,lvalue=0,rvalue=0,reverse=False,invert=False):
    """

        num_bits = How many bits are within the uint. If not specified, assume it is the minimum number of bits required to represent the uint.

        Result will be left-justified up to loffset

    >>> uint_to_bytes(126207244316550804821666916,88)
    b'hello world'
    """
    if not isinstance(uint,int):
        raise Exception('Input uint must be an integer, not %s' % repr(type(uint)))
    if uint < 0:
        raise Exception('Input uint must be non-negative: %s' % repr(uint))
    min_bits = min_bits_uint(uint)
    if loffset >= 8:
        raise Exception('loffset must be between 0 and 7 inclusive')
    if num_bits is not None and min_bits > abs(num_bits):
        #this should ensure that the uint does not contain 1s that go beyond what num_bits says it should
        raise Exception('Input uint must be storable in at most num_bits (%d) number of bits, but requires %d bits' % (num_bits,min_bits))
    if num_bits is None:
        num_bits = min_bits
    num_bytes = int(ceil(num_bits/8)) #number of bytes required to the number
    extra_bits = num_bytes*8 - num_bits #number of extra MSBs if no shifting were to be done - these MSBs should be 0 due to constraint above
    if not reverse:
        #Need to left-justify the data, we should shift left by the extra_bits amount, but leave loffset number of bits in the front
        roffset = extra_bits - loffset #extra bits will be padded on right side (minus loffset adjustment)
        if loffset > extra_bits:
            #add extra byte to ensure loffset shift does not truncate LSBs
            num_bytes += 1
            roffset += 8
        uint <<= (roffset)
    else:
        #Data needs to be right-justified so that after reversal, it will be left-justified.
        #loffset will need to be inserted on the right side so that after reversal it will be on the left side
        uint <<= loffset
        roffset = extra_bits - loffset
        if loffset > extra_bits:
            num_bytes += 1
            roffset += 8
    byte_data = []
    for byte_i in range(num_bytes):
        uint,value = divmod(uint,256)
        byte_data.append(value)
    if reverse:
        byte_data =[reverse_byte_table[value] for value in byte_data[::-1]]
    if invert:
        byte_data = [invert_byte_table[value] for value in byte_data]
    if loffset > 0:
        first_byte_rmask = 8-loffset
        byte_data[-1] = rmask_byte(first_byte_rmask,byte_data[-1]) | lmask_byte(loffset,lvalue)
    
    if roffset > 0:
        last_byte_lmask = 8-roffset
        byte_data[0] = lmask_byte(last_byte_lmask,byte_data[0]) | rmask_byte(roffset,rvalue)
    return bytes(byte_data[::-1])

def min_bits_uint(value):
    """
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
    return int(floor(1+log(value,2))) if value > 0 else 0

def invert_uint(uint,num_bits=None):
    """

    >>> invert_uint(0,3) # 000 -> 111
    7
    >>> invert_uint(12,4) # 1100 -> 0011
    3
    >>> invert_uint(-1,3)
    Traceback (most recent call last):
      File "<console>", line 1, in <module>
      File "/home/mtm/interspace/bitforge/bitforge/bitstream.py", line 102, in invert_uint
        raise Exception('input must be non-negative: %s' % repr(value))
    Exception: input must be non-negative: -1

    >>> invert_uint('0',3)
    Traceback (most recent call last):
      File "<console>", line 1, in <module>
      File "/home/mtm/interspace/bitforge/bitforge/bitstream.py", line 107, in invert_uint
        raise Exception('input must be an integer, not %s' % repr(type(value)))
    Exception: input must be an integer, not <class 'str'>

    >>> invert_uint(200,4)
    Traceback (most recent call last):
      File "<console>", line 1, in <module>
      File "/home/mtm/interspace/bitforge/bitforge/bitstream.py", line 129, in invert_uint
        raise Exception('Input uint must be storable in at most num_bits (%d) number of bits, but requires %d bits' % (num_bits,min_bits_uint(uint)))
    Exception: Input uint must be storable in at most num_bits (4) number of bits, but requires 8 bits

    """
    if not isinstance(uint,int):
        raise Exception('input must be an integer, not %s' % repr(type(uint)))
    if uint < 0:
        raise Exception('input must be non-negative: %s' % repr(uint))
    if min_bits_uint(uint) > num_bits:
        raise Exception('Input uint must be storable in at most num_bits (%d) number of bits, but requires %d bits' % (num_bits,min_bits_uint(uint)))
    if num_bits is None:
        num_bits = min_bits_uint(uint)
    return uint ^ ((1<<num_bits)-1)


def reverse_uint(uint,num_bits=None):
    """
    >>> reverse_uint(3,8)
    192
    >>> bin(192)
    '0b11000000'
    >>> reverse_uint(-1,4)
    Traceback (most recent call last):
      File "<console>", line 1, in <module>
      File "/home/mtm/interspace/bitforge/bitforge/bitstream.py", line 155, in reverse_uint
        raise Exception('input must be non-negative: %s' % repr(uint))
    Exception: input must be non-negative: -1
    >>> reverse_uint([],1)
    Traceback (most recent call last):
      File "<console>", line 1, in <module>
      File "/home/mtm/interspace/bitforge/bitforge/bitstream.py", line 153, in reverse_uint
        raise Exception('input must be an integer, not %s' % repr(type(uint)))
    Exception: input must be an integer, not <class 'list'>
    >>> reverse_uint(100000000000,2)
    Traceback (most recent call last):
      File "<console>", line 1, in <module>
      File "/home/mtm/interspace/bitforge/bitforge/bitstream.py", line 157, in reverse_uint
        raise Exception('Input uint must be storable in at most num_bits (%d) number of bits, but requires %d bits' % (num_bits,min_bits_uint(uint)))
    Exception: Input uint must be storable in at most num_bits (2) number of bits, but requires 37 bits
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

reverse_byte_table = {value:reverse_uint(value,8) for value in range(256)}
invert_byte_table = {value:invert_uint(value,8) for value in range(256)}

def lmask_byte(num_mask_bits,value):
    """
    >>> lmask_byte(3,list(b'\\xff')[0])
    224
    >>> bin(224)
    '0b11100000'
    """
    return (((1<<(num_mask_bits))-1)<<(8-num_mask_bits)) & value

def rmask_byte(num_mask_bits,value):
    """
    >>> rmask_byte(3,list(b'\\xff')[0])
    7
    >>> bin(7)
    '0b111'
    """
    return ((1<<(num_mask_bits))-1) & value

class BitStream(object):
    """

    Three stages:
        1) Original stream, which may be encoded
        2) Decoded byte stream
        3) Bits

    At the bit level, I would like to be able to:
        seek
        tell
        read
        write
    
    Bit position is translateable to decoded byte position via dec_pos_bytes,rem_bits = divmod(pos_bits,8)

    Relating decoded bye position to encoded byte position can be more difficult.
    Human-readable encodings like binstring, hex, or base64 have a single decoded byte corresponding to more than one encoded bytes
    Compression encodings have possibly more decoded bytes corresponding to fewer encoding bytes

    Predicting this relationship is difficult. For performance reasons, it is better to decode large chunks of data at a time.

    Bit position = Byte position + remainder bits
    Stream position = Byte position

    >>> b = byte_decode(b'101110010100101110101101','binstring')
    >>> bs = BitStream(b)
    >>> bs.pos_bits
    0
    >>> bs.readbits(6)
    (46, 6)
    >>> bin(46)
    '0b101110'
    >>> bs.pos_bits
    6
    >>> bs.readbits(3)
    (2, 3)
    >>> bs.pos_bits
    9
    >>> bs.readbits(4)
    (9, 4)
    >>> bs.pos_bits
    13
    >>> bs.readbits(-4)
    (9, 4)
    >>> len(b)
    3
    >>> bs.seek(0)
    0
    >>> min_bits_uint(bs.readbits()[0])
    24
    >>> bs.seek(0)
    0
    >>> bs.writebits(4,12)
    >>> bs.readbits(-4)
    (3, 4)
    >>> bs.seek(4)
    >>> bs.writebits(-4,10)
    >>> bs.readbits(4)
    (5, 4)
    """

    @classmethod
    def from_byte_source(klass,byte_source):
        return klass(byte_source)
    @classmethod
    def from_file_source(klass,path,mode):
        if not 'b' in mode:
            mode += 'b'
        byte_source = open(path,mode=mode)
        return klass(byte_source)

    def __init__(self,byte_source):
        if isinstance(byte_source,bytes):
            self.byte_source = io.BytesIO(byte_source)
        elif isinstance(byte_source,(io.BufferedIOBase,io.BufferedRandom,io.BytesIO)):
            self.byte_source = byte_source
        else:
            raise Exception('Invalid object for BitsIO byte_source: %s' % repr(type(byte_source)))
        self.pos_bits = self.byte_source.tell()*8
    def close(self):
        self.byte_source.close()
    def closed(self):
        return self.byte_source.closed()

    def __enter__(self):
        pass

    def __exit__(self,exc_type,exc_value,exc_traceback):
       self.close() 

    def flush(self):
        return self.byte_source.flush()

    def isatty(self):
        return self.byte_source.isatty()

    def readable(self):
        return self.byte_source.readable()

    def at_eof_byte(self):
        """
        If True, subsequent reads should return empty bytes objects
        """
        if hasattr(self.byte_source,'get_buffer'):
            size_bytes = len(self.byte_source.get_buffer())
            pos_bytes,remainder_bits = divmod(self.pos_bits,8)
            if remainder_bits > 0:
                pos_bytes += 1
            return pos_bytes >= size_bytes
        elif hasattr(self.byte_source,'peek'):
            return len(self.byte_source.peek(1)) == 0
        elif hasattr(self.byte_source,'read') and hasattr(self.byte_source,'seek'):
            tell = self.byte_source.tell()
            result = len(self.byte_source.read(1)) == 0
            self.byte_source.seek(tell)
            return result
        else:
            raise Exception('Byte source does not support a way of determining if at EOF or not')

    def seek(self,offset_bits,whence=io.SEEK_SET):
        offset_bytes, remainder_bits = divmod(offset_bits,8)
        self.byte_source.seek(offset_bytes,whence)
        seek_result_bytes  = self.byte_source.tell()
        self.pos_bits = seek_result_bytes*8
        if seek_result_bytes == offset_bytes and not self.at_eof_byte():
            self.pos_bits += remainder_bits
        return self.pos_bits
        
    def seekable(self):
        return self.byte_source.seekable()

    def tell(self):
        return self.pos_bits

    def writable(self):
        return self.byte_source.writable()

    def truncate(self,size_bits):
        pos = self.pos_bits
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
        pos = self.tell()
        end = self.seek(0,io.SEEK_END)
        self.seek(pos)
        return end
    def readbits(self,n=None):
        if n is None:
            n = len(self) - self.tell()
        if not isinstance(n,int):
            raise Exception('input n must be int, not %s' % repr(type(n)))
        if n == 0:
            return 0
        start_pos = self.pos_bits
        end_pos = self.pos_bits + n
        start_byte_pos,start_remainder_bits = divmod(start_pos,8)
        end_byte_pos,end_remainder_bits = divmod(end_pos,8)
        offset_bytes = end_byte_pos - start_byte_pos
        invert = False
        if n > 0:
            num_bytes = offset_bytes
            if end_remainder_bits > 0:
                num_bytes += 1
                rstrip = 8 - end_remainder_bits
            else:
                rstrip = 0
            reverse = False
            lstrip = start_remainder_bits
        elif n < 0:
            num_bytes = -offset_bytes
            if start_remainder_bits > 0:
                num_bytes += 1
                rstrip = 8 - start_remainder_bits
            else:
                rstrip = 0
            self.byte_source.seek(offset_bytes,io.SEEK_CUR)
            reverse = True
            lstrip = end_remainder_bits
        else:
            raise Exception('Provided value not comparable to zero: %s' % repr(n))
        byte_data = self.byte_source.read(num_bytes)
        value,num_bits = bytes_to_uint(byte_data,lstrip,rstrip,reverse,invert)
        self.seek(end_pos)

        assert(abs(n)==num_bits)

        return value,num_bits

    def writebits(self,n,value):
        if not isinstance(n,int):
            raise Exception('input n must be int, not %s' % repr(type(n)))
        if n == 0:
            return
        start_pos = self.pos_bits
        end_pos = self.pos_bits + n
        start_byte_pos,start_remainder_bits = divmod(start_pos,8)
        end_byte_pos,end_remainder_bits = divmod(end_pos,8)
        offset_bytes = end_byte_pos - start_byte_pos
        invert = False
        if n > 0:
            first_byte_pos = start_byte_pos
            loffset = start_remainder_bits
            last_byte_pos = end_byte_pos
            reverse = False
        else:
            first_byte_pos = end_byte_pos
            last_byte_pos = start_byte_pos
            loffset = end_remainder_bits
            self.byte_source.seek(end_byte_pos)
            reverse = True
        if loffset > 0:
            first_byte =  list(self.byte_source.read(1))[0]
        else:
            first_byte = 0
        last_byte_lmask = ((loffset + n)%8)
        roffset = 8 - last_byte_lmask
        if roffset > 0:
            self.byte_source.seek(last_byte_pos)
            last_byte = list(self.byte_source.read(1))[0]
        else:
            last_byte = 0
        self.byte_source.seek(first_byte_pos)
        byte_data = uint_to_bytes(value,n,loffset,first_byte,last_byte,reverse,invert)
        self.byte_source.write(byte_data)
        self.seek(end_pos)
