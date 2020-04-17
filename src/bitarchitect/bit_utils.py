"""
This module provides utility functions for working with bits with focus on the following representations:
    1. Bytes object
    2. (unsigned integer value, number of bits)

"""
import base64, math, io, struct
from math import log, floor, ceil
from enum import Enum
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
    """
    Reverses the bytes provided
    """
    return b''.join([reverse_byte_table[x] for x in b[::-1]])
def invert_bytes(b):
    """
    Inverts the bytes provided
    """
    return b''.join([invert_byte_table[x] for x in b])


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



def bytes_to_uint(bytes_data,lstrip=0,rstrip=0,reverse=False,invert=False):
    """
    This function takes a bytes object and converts it into a single unsigned integer. It assumes a Big Endian interpretation (first byte is more significant than last byte).
    
    If lstrip is set to a positive integer less than or equal to the number of bits within the bytes object, then that many MSBs will be zeroed out in the first byte. This applies to bits in the original byte stream, i.e. before a reversal is done if reverse is set to True.

    If rstrip is set to a positive integer less than or equal to the number of bits within the bytes object, then that many LSBs will be zeroed out in the last byte. This applies to bits in the original byte stream, i.e. before a reversal is done if reverse is set to True.

    If reverse is set to True, then an unsigned integer with the reversed binary representation will be returned (MSB of entire int becomes LSB).

    If invert is set to True, then every bit of the unsigned integer will be inverted.

    >>> bytes_to_uint(b'hello world')
    (126207244316550804821666916, 88)
    """
    bytes_data = bytearray(bytes_data)
    num_bits = len(bytes_data)*8-lstrip-rstrip
    n = len(bytes_data)
    if invert:
        #flip the value of all bytes
        bytes_data = [invert_byte_table[value] for value in bytes_data]
    if lstrip > 0:
        if lstrip <= len(bytes_data)*8:
            lstrip_bytes,lstrip = divmod(lstrip,8)
            bytes_data = bytes_data[lstrip_bytes:] #remove bytes from the front
            if len(bytes_data) > 0:
                bytes_data[0] = rmask_byte(8-lstrip,bytes_data[0]) #strip off bits in the first byte
        else:
            raise Exception('lstrip value of %d exceeded number of bits in bytes object (%d)' % (lstrip,len(bytes_data*8)))

    elif lstrip < 0:
        raise Exception('lstrip (%d) must be non-negative' % lstrip)

    if rstrip > 0:
        if rstrip <= len(bytes_data)*8:
            rstrip_bytes, rstrip = divmod(rstrip, 8)
            bytes_data = bytes_data[:-rstrip_bytes] #remove bytes from the end
            if len(bytes_data) > 0:
                bytes_data[-1] = lmask_byte(8-rstrip,bytes_data[-1]) #strip of bits in the last byte
        else:
            raise Exception('rstrip value of %d exceeded number of bits in bytes object (%d)' % (rstrip,len(bytes_data*8)))
    elif rstrip < 0:
        raise Exception('rstrip (%d) must be non-negative')
    
    if reverse:
        #reverse the order across bytes and reverse the order of bits within bytes
        bytes_data =[reverse_byte_table[value] for value in bytes_data[::-1]]
    result = sum((b<<(8*(n-p-1))) for p,b in enumerate(bytes_data))
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
    bytes_data = []
    for byte_i in range(num_bytes):
        uint,value = divmod(uint,256)
        bytes_data.append(value)
    #perform reversal if requested
    if reverse:
        bytes_data =[reverse_byte_table[value] for value in bytes_data[::-1]]
    #perform inversion if requested
    if invert:
        bytes_data = [invert_byte_table[value] for value in bytes_data]

    #replace the loffset MSBs of the byte that will ultimately be the first byte (but is currently the last byte) with the MSBs from lvalue
    if loffset > 0:
        first_byte_rmask = 8-loffset
        bytes_data[-1] = rmask_byte(first_byte_rmask,bytes_data[-1]) | lmask_byte(loffset,lvalue)
    
    #replace the roffset LSBs of the byte that will ultimately be the last byte (but is currently the first byte) with the LSBs from rvalue
    if roffset > 0:
        last_byte_lmask = 8-roffset
        bytes_data[0] = lmask_byte(last_byte_lmask,bytes_data[0]) | rmask_byte(roffset,rvalue)

    #reverse the bytes
    return bytes(bytes_data[::-1])
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
    >>> from .bit_utils import to_hex
    >>> to_hex(struct.pack('>f',math.pi))
    b'40490fdb'
    >>> '%08x' % uint_encode(math.pi,32,Encoding.SPFP)
    '40490fdb'
    >>> import struct, math
    >>> from .bit_utils import to_hex
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

from_b64 = base64.b64decode
from_b32 = base64.b32decode
from_b16 = base64.b16decode
def from_b8(b):
    if len(b) % 4 != 0:
        raise Exception('Octal b8 encoded strings must be a multiple of 4 bytes. Check that the "=" padding characters at the end are correct.')
    b = b.rstrip(b'=')
    ascii_base = ord('0')
    offset = 0
    val = 0
    result = []
    for o in b:
        val = (val << 3) + (o-ascii_base)
        offset += 3
        if offset >= 8:
            over = offset - 8
            result.append(val >> over)
            val = val & ((1<<over)-1)
            offset = over
    return bytes(result)

def from_b2(b):
    """
    >>> from_b2(b'101')
    b'\xa0'
    """
    if isinstance(b,str):
        b = bytes(b)
    ascii_base = ord('0')
    val = 0
    result = []
    for i,v in enumerate(b):
        val = (val << 1) + (v-ascii_base)
        if i % 8 == 7:
            result.append(val)
            val = 0
    if i % 8 < 7:
        val = (val<<(7-i))
        result.append(val)
    return bytes(result)
    
from_hex = lambda s: from_b16(s if isinstance(s,bytes) else bytes(s),True)
from_oct = from_b8
from_bin = from_b2

to_b64 = base64.b64encode
to_b32 = base64.b32encode
to_b16 = base64.b16encode
def to_b8(b):
    result = []
    phase = 0
    leftover=0
    ascii_base = ord('0')
    for y in b:
        if phase == 0:
            result.append(ascii_base + (y >> 5))
            result.append(ascii_base + ((y >> 2) & 7))
            leftover = y & 3
            phase = 2
        elif phase == 2:
            result.append(ascii_base +(leftover << 1) + (y>>7))
            result.append(ascii_base + ((y>>4)&7))
            result.append(ascii_base + ((y>>1)&7))
            leftover = y & 1
            phase = 1
        elif phase == 1:
            result.append(ascii_base + (leftover << 2) + (y >> 6))
            result.append(ascii_base + ((y>>3)&7))
            result.append(ascii_base + (y&7))
            leftover=0
            phase = 0
    if phase != 0:
        pad = ord('=')
        if phase == 1:
            result.append(ascii_base + (leftover << 2))
            result.extend([pad,pad])
        elif phase == 2:
            result.append(ascii_base +(leftover << 1))
            result.append(pad)
    return bytes(result)
def to_b2(b):
    ascii_base = ord('0')
    result = []
    for y in b:
        bd = []
        yr = y
        for i in range(8):
            yr,yb = divmod(yr,2)
            bd.append(ascii_base +yb)
        result.extend(bd[::-1])
    return bytes(result)

def to_hex(b):
    return to_b16(b).lower()
def to_HEX(b):
    return to_b16(b).upper()
to_oct = to_b8
to_bin = to_b2

def from_uint(uint,num_bits):
    return uint_decode(uint,num_bits,Encoding.BYTS)
def to_uint(b):
    return uint_encode(b,len(b)*8,Encoding.BYTS)

def from_sint(sint,num_bits):
    return uint_decode(uint_encode(sint,num_bits,Encoding.SINT),num_bits,Encoding.BYTS)
def to_sint(b):
    num_bits = len(b)*8
    return uint_encode(uint_decode(b,num_bits,Encoding.BYTS),num_bits,Encoding.SINT)
