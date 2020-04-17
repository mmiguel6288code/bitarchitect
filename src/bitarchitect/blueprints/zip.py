"""
This module provides blueprint functions for zip files.
See zip file structure definition here:
        https://en.m.wikipedia.org/wiki/Zip_(file_format)
"""
import unittest,sys, os.path, zlib
from collections import OrderedDict
import logarhythm
sys.path.append(os.path.abspath('../..'))
import bitarchitect


logger = logarhythm.getLogger('blueprints.zip')
logger.format = logarhythm.build_format(time=None,level=False)
def zip_file(maker):
    """
    This blueprint parses a zip file. This is not performance optimized, but has value in zip file inspection.

    Structure:
        0: EOCD
        1: Central Directory
        2: Files
    """
    maker('Ey ##turn on endian-swap for everything')

    #parse the EOCD
    eocd_record(maker)

    #get central directory offset and size (each in bytes)
    cd_offset = maker["cd_offset"]
    cd_size = maker["cd_size"]
    file_data = central_directory(maker,cd_offset,cd_size)

    #parse file entries
    file_entries(maker,file_data,cd_offset)
    return file_data

def eocd_record(maker):
    """
    Parses the EOCD record. Assumes the signature has already been removed (first 4 bytes).

    When finished, must have extracted and labeled the central directory offset and size in labels cd_offset and cd_size respectively.
    """
    logger.debug('Parsing EOCD record')
    maker('[') #start collecting in a sublist for everything related to EOCD
    #the following rows have a comma after the assignment to use tuple assigment (equivalent to storing the first and only item within the returned list/tuple
    maker('''
        m"06054b50" ##scan and "jump" to EOCD marker 'PK\\x05\\x06'
        {u16}4 ##4 disk-related params of 16 bits each 
        u32 #"cd_size"
        u32 #"cd_offset" 
        u16 #"eocd_comment_len"
    ''')
    comment_len = maker["eocd_comment_len"]
    maker('B%d #"eocd_comment"]' % (comment_len*8))

def central_directory(maker,cd_offset,cd_size):
    """
    Parses the central directory entries excluding the EOCD record
    """
    logger.debug('Parsing Central Directory')
    maker('[') #start collecting in a sublist for central directory entries

    maker('js%d' % (cd_offset*8)) #jump to start of central directory
    cd_start_pos = maker.tell_buffer()
    cd_size_bits = cd_size*8
    file_data = OrderedDict()
    num = 0
    while maker.tell_buffer() - cd_start_pos < cd_size_bits:
        num += 1
        logger.debug('CD entry %d' % num)
        cd_entry_pos_orig = maker.tell_stream() #file entry positions are specified relative to central directory entries
        maker('[ ##sub-sub-list for central directory entry')
        record = maker('''
            m"02014b50" ##scan and "jump" to file entry marker 'PK\x02\x01'
            {u16}6 ##6 entries 2 bytes each
            {u32}3 ##3 entries 4 bytes each
            {u16}5 ##5 entries 2 bytes each
            {u32}2 ##2 entries 4 bytes each
        ''')
        maker(']') #could have placed [ and ] inside middle call to maker, but then the following line would have to be n,m,k = record[0][10:13], which seems more confusing
        n,m,k = record[10:13]
        filename,extra_field,file_comment = maker('C%d C%d C%d' % (n*8, m*8, k*8))
        file_data[filename] = [cd_entry_pos_orig,record,extra_field,file_comment]

    maker(']') #end sublist for central directory entries
    return file_data

def file_entries(maker,file_data,cd_offset):
    """
        x: file entry
            0: Local Header
            1: Data Descriptor
            2: Data
    """
    logger.debug('Parsing file entries')
    maker('[') #start collecting in a sublist for file entries
    #parse each file
    file_items = list(file_data.items())
    for file_no,(filename,file_record) in enumerate(file_items):
        logger.debug('File entry %d' % (file_no+1))
        maker('[') #start collecting in a subsublist for an individual file entry
        cd_entry_pos_orig = file_record[0]
        relative_offset = file_record[1][16]
        #file_entry_pos_orig = cd_entry_pos_orig - relative_offset*8 #wikipedia image is confusing... thought it was this
        file_entry_pos_orig = relative_offset*8

        if file_no +1< len(file_items):
            next_cd_entry_pos_orig = file_items[file_no+1][1][0]
            next_relative_offset = file_items[file_no+1][1][1][16]
            #file_end_orig = next_cd_entry_pos_orig - next_relative_offset*8
            file_end_orig = next_relative_offset*8
        else:
            file_end_orig = cd_offset*8

        file_entry_size = (file_end_orig - file_entry_pos_orig)//8


        maker('js%d' % (file_entry_pos_orig)) #jump to start of file entry


        #parse local header
        record1 = maker('''
            [
            B32 = b'\x04\x03\x4b\x50'; ##signature
            {u16}5 ## 5 entries 2 bytes each
            {u32}3
            u16#"filename_len"u16#"extra_field_len"
        ''') 
            #record1 will be surrounded by a list due to the leading [
        n,m = (maker["filename_len"],maker["extra_field_len"])
        record2 = maker('''
            C%dC%d
            ]
        ''' % (n*8,m*8))
            #record2 will be surrounded by a list due to the trailing ]
            
        local_header_size = 30 + n + m

        #combine the two records
        record = record1[0] + record2[0]
        general_purpose_flag = record[2]

        has_data_descriptor, = bitarchitect.extract_data('n12u1',bitarchitect.from_uint(general_purpose_flag,16))
        #could have also extracted the general purpose flag as a bit string, or extracted this individual bit from the beginning

        maker('[') #create subsubsublist regardless if descriptor is present or not
        if has_data_descriptor:
            descriptor = maker('''
            x32
            u32
            u32
            ''')
            if descriptor[0] == '08074b50':
                #looks like a signature
                #could still be CRC just happening to match signature

                #assume there is no signature and check
                descriptor_size = 12
                compressed_size = descriptor[1]
                if file_entry_size == local_header_size + descriptor_size + compressed_size:
                    #probably there is no signature and crc just happened to match signature
                    crc = bitarchitect.from_hex(descriptor[0])
                else:
                    #there probably is a signature
                    descriptor_size = 16
                    descriptor.append(maker('u32')[0])
                    compressed_size = descriptor[2]
                    if file_entry_size == local_header_size + descriptor_size + compressed_size:
                        crc = bitarchitect.from_uint(descriptor[1],32)
                    else:
                        raise Exception('Data descriptor sizes not lining up as expected')
            else:
                #there was no signature
                descriptor_size = 12
                compressed_size = descriptor[1]
                if file_entry_size == local_header_size + descriptor_size + compressed_size:
                    crc = bitarchitect.from_hex(descriptor[0])
                else:
                    raise Exception('Data descriptor sizes not lining up as expected')
        else:
            compressed_size = record[7]
            descriptor_size = 0
            if file_entry_size == local_header_size + descriptor_size + compressed_size:
                #probably interpreting things right
                crc = bitarchitect.from_uint(record[6],32)
                pass
            else:
                raise Exception('File entry sizes not lining up as expected')

        maker(']') #end subsubsublist for descriptor
        compressed_data, = maker('C%d' % (compressed_size*8)) #get compressed data
        compressed_data = b'\x78\x9c' + compressed_data #add zlib header
        file_data[filename].append(compressed_data)
        uncompressed_data = zlib.decompressobj().decompress(compressed_data)
        file_data[filename].append(uncompressed_data)
        maker(']') #end subsublist
    maker(']') #end sublist for file entries

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
                maker,file_data = bitarchitect.extract(zip_file,f)
            for filename,file_record in file_data.items():
                print(filename,repr(file_record[-1]))
            print(maker.data_obj)
            modified = [(item if item != b'file1.txt' else b'file3.txt') for item in maker.data_flat]

            modzipfilepath = os.path.join(tdir,'modtest.zip')
            with open(modzipfilepath,'wb') as f:
                maker,file_data = bitarchitect.construct(zip_file,modified)
                f.write(bytes(maker))
            with zipfile.ZipFile(modzipfilepath,mode='r') as zf:
                print(zf.namelist())

if __name__ == '__main__':
    import logarhythm
    logarhythm.set_auto_debug(True)
    #logger.level = logarhythm.DEBUG
    #logarhythm.getLogger('parse_pattern').level = logarhythm.DEBUG
    #logarhythm.getLogger('Extractor').level = logarhythm.DEBUG
    #logarhythm.getLogger('Constructor').level = logarhythm.DEBUG

    TestZipBlueprint().test_zip_extract()
    #unittest.main()

