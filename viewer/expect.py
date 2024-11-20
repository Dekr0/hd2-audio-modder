import json
import struct


class MemoryStream:
    '''
    Modified from https://github.com/kboykboy2/io_scene_helldivers2 with permission from kboykboy
    '''
    def __init__(self, Data=b"", io_mode = "read"):
        self.location = 0
        self.data = bytearray(Data)
        self.io_mode = io_mode
        self.endian = "<"

    def open(self, Data, io_mode = "read"): # Open Stream
        self.data = bytearray(Data)
        self.io_mode = io_mode

    def set_read_mode(self):
        self.io_mode = "read"

    def set_write_mode(self):
        self.io_mode = "write"

    def is_reading(self):
        return self.io_mode == "read"

    def is_writing(self):
        return self.io_mode == "write"

    def seek(self, location): # Go To Position In Stream
        self.location = location
        if self.location > len(self.data):
            missing_bytes = self.location - len(self.data)
            self.data += bytearray(missing_bytes)

    def tell(self): # Get Position In Stream
        return self.location

    def read(self, length=-1): # read Bytes From Stream
        if length == -1:
            length = len(self.data) - self.location
        if self.location + length > len(self.data):
            raise Exception("reading past end of stream")

        newData = self.data[self.location:self.location+length]
        self.location += length
        return bytearray(newData)

    def write(self, bytes): # Write Bytes To Stream
        length = len(bytes)
        if self.location + length > len(self.data):
            missing_bytes = (self.location + length) - len(self.data)
            self.data += bytearray(missing_bytes)
        self.data[self.location:self.location+length] = bytearray(bytes)
        self.location += length

    def read_format(self, format, size):
        format = self.endian+format
        return struct.unpack(format, self.read(size))[0]
        
    def bytes(self, value, size = -1):
        if size == -1:
            size = len(value)
        if len(value) != size:
            value = bytearray(size)

        if self.is_reading():
            return bytearray(self.read(size))
        elif self.is_writing():
            self.write(value)
            return bytearray(value)
        return value
        
    def int8_read(self):
        return self.read_format('b', 1)

    def uint8_read(self):
        return self.read_format('B', 1)

    def int16_read(self):
        return self.read_format('h', 2)

    def uint16_read(self):
        return self.read_format('H', 2)

    def int32_read(self):
        return self.read_format('i', 4)

    def uint32_read(self):
        return self.read_format('I', 4)

    def int64_read(self):
        return self.read_format('q', 8)

    def uint64_read(self):
        return self.read_format('Q', 8)


class TocHeader:

    def __init__(self):
        pass
        
    def from_memory_stream(self, stream):
        self.file_id             = stream.uint64_read()
        self.type_id             = stream.uint64_read()
        self.toc_data_offset     = stream.uint64_read()
        self.stream_file_offset  = stream.uint64_read()
        self.gpu_resource_offset = stream.uint64_read()
        self.unknown1            = stream.uint64_read() #seems to contain duplicate entry index
        self.unknown2            = stream.uint64_read()
        self.toc_data_size       = stream.uint32_read()
        self.stream_size         = stream.uint32_read()
        self.gpu_resource_size   = stream.uint32_read()
        self.unknown3            = stream.uint32_read()
        self.unknown4            = stream.uint32_read()
        self.entry_index         = stream.uint32_read()


class TocHeaderEncoder(json.JSONEncoder):

    def default(self, o):
        if isinstance(o, TocHeader):
            return {
                "FileID": o.file_id,
                "TypeID": o.type_id,
                "ToCDataOffset": o.toc_data_offset,
                "StreamFileOffset": o.stream_file_offset,
                "GPUResourceOffset": o.gpu_resource_offset,
                "Unknown1": o.unknown1,
                "Unknown2": o.unknown2,
                "ToCDataSize": o.toc_data_size,
                "StreamSize": o.stream_size,
                "GPUResourceSize": o.gpu_resource_size,
                "Unknown3": o.unknown3,
                "Unknown4": o.unknown4,
                "EntryIndex": o.entry_index
            }
        return super().default(o)


def pad_to_16_byte_align(data):
    b = bytearray(data)
    l = len(b)
    new_len = ceil(l/16)*16
    return b + bytearray(new_len-l)
    

def _16_byte_align(addr):
    return ceil(addr/16)*16
    

def bytes_to_long(bytes):
    assert len(bytes) == 8
    return sum((b << (k * 8) for k, b in enumerate(bytes)))


def murmur64_hash(data, seed = 0):

    m = 0xc6a4a7935bd1e995
    r = 47

    MASK = 2 ** 64 - 1

    data_as_bytes = bytearray(data)

    h = seed ^ ((m * len(data_as_bytes)) & MASK)

    off = int(len(data_as_bytes)/8)*8
    for ll in range(0, off, 8):
        k = bytes_to_long(data_as_bytes[ll:ll + 8])
        k = (k * m) & MASK
        k = k ^ ((k >> r) & MASK)
        k = (k * m) & MASK
        h = (h ^ k)
        h = (h * m) & MASK

    l = len(data_as_bytes) & 7

    if l >= 7:
        h = (h ^ (data_as_bytes[off+6] << 48))

    if l >= 6:
        h = (h ^ (data_as_bytes[off+5] << 40))

    if l >= 5:
        h = (h ^ (data_as_bytes[off+4] << 32))

    if l >= 4:
        h = (h ^ (data_as_bytes[off+3] << 24))

    if l >= 3:
        h = (h ^ (data_as_bytes[off+2] << 16))

    if l >= 2:
        h = (h ^ (data_as_bytes[off+1] << 8))

    if l >= 1:
        h = (h ^ data_as_bytes[off])
        h = (h * m) & MASK

    h = h ^ ((h >> r) & MASK)
    h = (h * m) & MASK
    h = h ^ ((h >> r) & MASK)

    return h


if __name__ == "__main__":
    testing_ToCs = [
        "2e24ba9dd702da5c",
        "68e80476c1c602f5",
    ]

    for t in testing_ToCs:
        data = b""
        toc = {}

        with open(t, "rb") as f:
            data = f.read()

        m = MemoryStream(data)

        toc["Magic"] = m.uint32_read()
        toc["NumTypes"] = m.uint32_read()
        toc["NumFiles"] = m.uint32_read()
        toc["Unknown"] = m.uint32_read()
        toc["Unk4Data"] = [int(b) for b in m.read(56)]
        toc["ToCEntries"] = {}

        m.seek(m.tell() + 32 * toc["NumTypes"])

        toc_start = m.tell()

        for n in range(toc["NumFiles"]):
            m.seek(toc_start + n * 80)
            header = TocHeader()
            header.from_memory_stream(m)
            if header.file_id not in toc["ToCEntries"]:
                toc["ToCEntries"][header.file_id] = header
            else:
                err = {
                    "Error": "ToC File with duplicate file ID",
                    "DuplicatedFileId": header.file_id,
                    "ParserContext": {
                        "ToC File": t,
                        "AtFile": n,
                        "NumsFiles": toc["NumFiles"]
                    }
                }
                err_msg = json.dumps(err)
                print(err_msg)

        with open(f"{t}_ToC.json", "w") as f:
            json.dump(toc, f, cls=TocHeaderEncoder)

