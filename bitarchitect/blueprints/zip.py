"""
This module provides blueprint functions for zip files.
See zip file structure definition here:
        https://en.m.wikipedia.org/wiki/Zip_(file_format)
"""
import unittest,sys, os.path
sys.path.append(os.path.abspath('../..'))
import bitarchitect

def zip_file(tool):
    """
    This blueprint parses a zip file. This is not performance optimized, but has value in zip file inspection.
    """
    tool('r! Ry') #reverse all bits in the file, set reverse_all flag = True

    #reverse scan until find the EOCD signature
    word = None
    eocd_words = []
    while word != b'\x50\x4b\x05\x06': #endian swap compared to what is listed on wikipedia
        word = tool('B32') #grab 32 bits as Bytes
        import pdb; pdb.set_trace()
        eocd_words.append(word)


    signature = tool('e32 x32') #endian swap and extract as hex
    if signature == '04034b50': #local file header
        has_data_descriptor = zip_file_entry(tool)
        descriptor = tool('x32{4}')
        if descriptor[0] == '504b0708': #optional signature present or CRC happens to match signature by chance
            if descriptor[3]:
                ...
        else:
            ...

    elif signature == '08074b50': #data descriptor header
        ...
    elif signature == '02014b50': #central directory file header
        ...
    elif signature == '06054b50': #end of central directory record
        ...

def zip_file_entry(tool):
    version,gpbf,cmpr_meth,modtime,moddate,crc,cmp_sz,unc_sz,name_len,extra_len = tool('u16 b16 {u16}3 x32 {u32}2 {u16}2')
    filename = tool('B%d #"filename"' % name_len*8)
    num_chunks = extra_len*8/32
    extras = tool('[{[u16 u16]}%d]' % num_chunks)
    compressed_data = tool('B%d #"compressed_data"' % cmp_sz)
    has_data_descriptor = gpbf[-4] == b'1'
    return has_data_descriptor

class TestZipBlueprint(unittest.TestCase):
    def test_zip_extract(self):
        import zipfile, tempfile, os.path
        with tempfile.TemporaryDirectory() as tdir:
            #create an example zip file
            with zipfile.ZipFile(os.path.join(tdir,'test.zip'),mode='w',compression=zipfile.ZIP_DEFLATED) as zf:
                with zf.open('file1.txt',mode='w') as f:
                    f.write(b'green eggs and ham')
                with zf.open('file2.txt',mode='w') as f:
                    f.write(b'sam i am')
            #open zip file
            with open(os.path.join(tdir,'test.zip'),'rb+') as f:
                result = bitarchitect.extract(zip_file,f)

if __name__ == '__main__':
    TestZipBlueprint().test_zip_extract()
    unittest.main()

