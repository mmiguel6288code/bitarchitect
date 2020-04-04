"""
This module provides blueprint functions for zip files.
See zip file structure definition here:
        https://en.m.wikipedia.org/wiki/Zip_(file_format)
"""

def zip(tool):
    signature = tool('e32 x32') #endian swap and extract as hex
    if signature == '04034b50': #local header
    elif signature == '08074b50': #data descriptor header
def zip_local_header(tool):
    """
    """
    signature = tool('e32 x32') #endian swap and extract as hex
    if signature != '04034b50':
        raise Exception('Not a valid zip file')
    version,gpbf,cmpr_meth,modtime,moddate,crc,cmp_sz,unc_sz,name_len,extra_len = tool('{u16}5 x32 {u32}2 {u16}2')

    filename = tool('B%d' % name_len*8)
    num_chunks = extra_len*8/32
    extras = tool('[{[u16 u16]}%d]' % num_chunks)


