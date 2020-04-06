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
    import pdb; pdb.set_trace()
    tool('[') #start collecting in a sublist for everything related to EOCD
    eocd_offset, = tool('m"504b0506" #"eocd_offset"') #scan for EOCD marker 'PK\05\06'
    eocd_size, = tool('p%d.! #"eocd_size"' % eocd_offset) #pull everything after the EOCD marker to the front - this is the EOCD record
    
    #parse the EOCD
    eocd_record(tool)

    tool(']') #end sublist containing EOCD inf      
    



def eocd_record(tool):
    """
    Parses the EOCD record. Assumes the signature has already been removed (first 4 bytes).

    When finished, must have extracted and labeled the central directory offset and size in labels cd_offset and cd_size respectively.
    """
    tool('''
        {u16}4 ##4 disk-related params of 16 bits each 
        u32 #"cd_size"
        u32 #"cd_offset" 
        u16 #"eocd_comment_len"
    ''')
    comment_len = tool['eocd_comment_len']
    tool('B%d #"eocd_comment"' % (comment_len*8))

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
        #with tempfile.TemporaryDirectory() as tdir:
        if 1:
            tdir = '.'
            #create an example zip file
            zipfilepath = os.path.join(tdir,'test.zip')
            if not os.path.exists(zipfilepath):
                with zipfile.ZipFile(zipfilepath,mode='w',compression=zipfile.ZIP_DEFLATED) as zf:
                    with zf.open('file1.txt',mode='w') as f:
                        f.write(b'green eggs and ham')
                    with zf.open('file2.txt',mode='w') as f:
                        f.write(b'sam i am')
            with open(zipfilepath,'rb') as f:
                bitarchitect.extract(zip_file,f)

if __name__ == '__main__':
    import logarhythm
    logarhythm.set_auto_debug(True)
    TestZipBlueprint().test_zip_extract()
    #unittest.main()

