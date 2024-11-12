from audio_modder import STREAM, WWISE_STREAM, MemoryStream, TocHeader, AudioSource, WwiseStream

import structio

import ctypes
import gc
import time

class NewToCHeader:

    def __init__(self, stream):
        self.file_id             = stream.read_uint64()
        self.type_id             = stream.read_uint64()
        self.toc_data_offset     = stream.read_uint64()
        self.stream_file_offset  = stream.read_uint64()
        self.gpu_resource_offset = stream.read_uint64()
        self.unknown1            = stream.read_uint64()
        self.unknown2            = stream.read_uint64()
        self.toc_data_size       = stream.read_uint32()
        self.stream_size         = stream.read_uint32()
        self.gpu_resource_size   = stream.read_uint32()
        self.unknown3            = stream.read_uint32()
        self.unknown4            = stream.read_uint32()
        self.entry_index         = stream.read_uint32()

    def test(self, ToC: TocHeader):
        assert(ToC != None)

        self.file_id = ToC.file_id
        self.type_id = ToC.type_id
        self.toc_data_offset = ToC.toc_data_offset
        self.stream_file_offset = ToC.stream_file_offset
        self.gpu_resource_offset = ToC.gpu_resource_offset
        self.unknown1 = ToC.unknown1
        self.unknown2 = ToC.unknown2
        self.toc_data_size = ToC.toc_data_size
        self.stream_size = ToC.stream_size
        self.gpu_resource_size = ToC.gpu_resource_size
        self.unknown3 = ToC.unknown3
        self.unknown4 = ToC.unknown4
        self.entry_index = ToC.entry_index

def test_uint8():
    with open("test_archive", "rb") as f:
        test = structio.MemoryStream(f.read())
        f.seek(0)
        expect = MemoryStream(f.read())

        while test.tell() < test.len():
            assert(test.read_uint8() == expect.read_uint8())
            
def test_int8():
    with open("test_archive", "rb") as f:
        test = structio.MemoryStream(f.read())
        f.seek(0)
        expect = MemoryStream(f.read())

        while test.tell() < test.len():
            assert(test.read_int8() == expect.read_int8())

def test_uint16():
    with open("test_archive", "rb") as f:
        test = structio.MemoryStream(f.read())
        f.seek(0)
        expect = MemoryStream(f.read())

        while test.tell() + 2 <= test.len():
            assert(test.read_uint16() == expect.read_int16())

def test_int16():
    with open("test_archive", "rb") as f:
        test = structio.MemoryStream(f.read())
        f.seek(0)
        expect = MemoryStream(f.read())

        while test.tell() + 2 <= test.len():
            assert(test.read_int16() == expect.read_int16())

def test_uint32():
    with open("test_archive", "rb") as f:
        test = structio.MemoryStream(f.read())
        f.seek(0)
        expect = MemoryStream(f.read())

        while test.tell() + 4 <= test.len():
            assert(test.read_uint32() == expect.read_uint32())

def test_int32():
    with open("test_archive", "rb") as f:
        test = structio.MemoryStream(f.read())
        f.seek(0)
        expect = MemoryStream(f.read())

        while test.tell() + 4 <= test.len():
            assert(test.read_int32() == expect.read_int32())

def test_uint64():
    with open("test_archive", "rb") as f:
        test = structio.MemoryStream(f.read())
        f.seek(0)
        expect = MemoryStream(f.read())

        while test.tell() + 8 <= test.len():
            assert(test.read_uint64() == expect.read_uint64())

def test_int64():
    with open("test_archive", "rb") as f:
        test = structio.MemoryStream(f.read())
        f.seek(0)
        expect = MemoryStream(f.read())

        while test.tell() + 8 <= test.len():
            assert(test.read_int64() == expect.read_int64())

def wallclock_test():
    data: bytes = b""
    with open("test_archive", "rb") as f:
        data = f.read()

    # warm up cache line
    for i in range(10):
        for j in data:
            j += 1

    start = time.time()
    m = structio.MemoryStream(data)
    while m.tell() + 4 <= m.len():
        _ = m.read_int32()
    end = time.time() - start
    print(end)

    m = None
    gc.collect()

    # warm up cache line
    for i in range(10):
        for j in data:
            j += 1
    start = time.time()
    m = MemoryStream(data)
    while m.tell() + 4 <= len(m.data):
        _ = m.read_int32()
    end = time.time() - start

    print(end)

def explore_memory_stream():
    m = MemoryStream()
    
    m.write(b",.|ms)")
    
    m.seek(6)
     
    m.seek(4)
    print(m.tell())
    
    print(m.read(1))
    
    m.seek(4)
    
    m.write(b"abcdefhijkl")
    
    print(m.tell())
    print(len(m.data))
    
    m.seek(4)
    print(m.read(len(b"abcdefhijkl")))
    
    print(m.tell())
    
    m.seek(m.tell() - 1)
    
    print(m.read(1))

def test_write():
    expect = MemoryStream()
    result = structio.MemoryStream(b"")

    expect.write(b",.|ms)")
    result.write(b",.|ms)")
    
    assert(len(expect.data) == result.len())
    assert(expect.tell() == result.tell())

    expect.seek(4)
    result.seek(4)
    assert(expect.read(1) == result.read(1))

    expect.seek(4)
    result.seek(4)

    expect.write(b"abcdefhijkl")
    result.write(b"abcdefhijkl")

    assert(len(expect.data) == result.len())
    assert(expect.tell() == result.tell())

    expect.seek(4)
    result.seek(4)

    assert(expect.tell() == result.tell())

    assert(
            expect.read(len(b"abcdefhijkl")) == 
            bytearray(result.read(len(b"abcdefhijkl"))))

def integration_test():
    data = b""
    with open("test_archive", "rb") as f:
        data = f.read()

    expect = MemoryStream(data)
    result = structio.MemoryStream(data)

    magic: int = result.read_uint32()
    assert(expect.read_uint32() == magic)

    num_types: int = result.read_uint32()
    assert(expect.read_uint32() == num_types)

    # num_files
    num_files: int = result.read_uint32()
    assert(expect.read_uint32() == num_files)

    # unknwon
    unknown: int = result.read_uint32()
    assert(expect.read_uint32() == unknown)

    # unknonw4
    unknonw4: bytearray = result.read(56)
    assert(expect.read(56) == unknonw4)

    result.seek(result.tell() + 32 * num_types)
    expect.seek(expect.tell() + 32 * num_types)

    assert(result.tell() == expect.tell())

    result_start = result.tell()
    expect_start = expect.tell()

    assert(result_start == expect_start)

    for n in range(num_files):
        result.seek(result_start + n * 80)
        expect.seek(expect_start + n * 80)

        result_ToC= NewToCHeader(result)

        expect_ToC = TocHeader()
        expect_ToC.from_memory_stream(expect)

        assert(result.tell() == expect.tell())

        result_ToC.test(expect_ToC)
        if result_ToC.type_id == WWISE_STREAM:
            audio = AudioSource()
            audio.stream_type = STREAM

            entry = WwiseStream(expect_ToC)

            result.seek(result_ToC.toc_data_offset)
            expect.seek(expect_ToC.toc_data_offset)

            assert(result.tell() == expect.tell())

            ToCData = result.read(result_ToC.toc_data_size)
            assert(ToCData == expect.read(expect_ToC.toc_data_size))

            entry.TocData = ToCData
        
def integration_wallclock_test():
    data = b""
    with open("test_archive", "rb") as f:
        data = f.read()

    # warm up cache line
    for _ in range(10):
        for j in data:
            j += 1

    start = time.time()

    m = structio.MemoryStream(ctypes.create_string_buffer(data))

    m.read_uint32()

    num_types: int = m.read_uint32()
    num_files: int = m.read_uint32()

    m.read_uint32()
    m.read(56)

    m.seek(m.tell() + 32 * num_types)

    result_start = m.tell()

    for n in range(num_files):
        m.seek(result_start + n * 80)
        NewToCHeader(m)

    end = time.time() - start
    
    print(end)

    m = None

    # warm up cache line
    for _ in range(10):
        for j in data:
            j += 1

    start = time.time()

    m = MemoryStream(data)

    m.read_uint32()

    num_types: int = m.read_uint32()
    num_files: int = m.read_uint32()

    m.read_uint32()
    m.read(56)

    m.seek(m.tell() + 32 * num_types)

    result_start = m.tell()

    for n in range(num_files):
        m.seek(result_start + n * 80)
        NewToCHeader(m)

    end = time.time() - start
    
    print(end)

# wallclock_test()
# test_uint8()
# test_int8()
# test_uint16()
# test_int16()
# test_uint32()
# test_int32()
# test_uint64()
# test_int64()

# test_write()
integration_test()
# for _ in range(10):
#     integration_wallclock_test()
