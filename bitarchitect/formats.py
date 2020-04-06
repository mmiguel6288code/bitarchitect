"""
The purpose of this  module is to provide some convenience functions for translating between common binary formats.

This provides functions to go from each format to Base 256 (normal bytes) and back.

The following are the common binary formats supported:
    Base 256 (b256) "Bytes" 8 bits
        This format is the standard bytes format where all 8 bits in a byte contain meaningful information.

    Base 64 (b64) "Base64" 6 bits
        Each encoded byte contains 6 bits worth of information. The 64 possible symbols are encoded using printable ASCII characters (uppercase letters, lower case letters, digits, puncuation).

    Base 32 (b32) "Base32" 5 bits 
        Each encoded byte contains 5 bits worth of information. The 32 possible symbols are encoded using printable ASCII characters (upper case letters, digits).

    Base 16 (b16) "Hexadecimal/Hex" 4 bits
        Each encoded byte contains 4 bits worth of information. The 16 possible symbols are the digits 0-9 and the letters A through F.

    Base 8 (b8) "Octal" 3 bits
        Each encoded byte contains 3 bits worth of information. The 8 possible symbols are the digits 0-7.

    Base 2 (b2) "Binary String" 1 bit
        Each encoded byte contains 1 bit worth of information. The 2 possible symbols are the digits 0 and 1.

>>> to_b64(b'hello world')
b'aGVsbG8gd29ybGQ='
>>> from_b64(_)
b'hello world'
>>> to_b32(b'hello world')
b'NBSWY3DPEB3W64TMMQ======'
>>> from_b32(_)
b'hello world'
>>> to_b16(b'hello world')
b'68656C6C6F20776F726C64'
>>> from_b16(_)
b'hello world'
>>> to_b8(b'hello world')
b'320625543306744035667562330620=='
>>> from_b8(_)
b'hello world'
>>> to_b2(b'hello world')
b'0110100001100101011011000110110001101111001000000111011101101111011100100110110001100100'
>>> from_b2(_)
b'hello world'
"""
import base64, math 
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
    ascii_base = ord('0')
    val = 0
    result = []
    for i,v in enumerate(b):
        val = (val << 1) + (v-ascii_base)
        if i % 8 == 7:
            result.append(val)
            val = 0
    return bytes(result)
    
from_hex = lambda s: from_b16(s,True)
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

