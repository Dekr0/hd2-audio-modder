import numpy
import os
import pyaudio
import subprocess
import struct
import wave
import xml.etree.ElementTree as etree

from itertools import takewhile
from math import ceil

from backend.const import *
from backend.env import *
from backend.xlocale import *
from log import logger


# constants
# global variables
language = 0
num_segments = 0


def language_lookup(lang_string):
    try:
        return LANGUAGE_MAPPING[lang_string]
    except:
        return int(lang_string)
    

def strip_patch_index(filename):
    split = filename.split(".")
    for n in range(len(split)):
        if "patch_" in split[n]:
            del split[n]
            break
    filename = ".".join(split)
    return filename
    

def list_files_recursive(path="."):
    files = []
    if os.path.isfile(path):
        return [path]
    else:
        for entry in os.listdir(path):
            full_path = os.path.join(path, entry)
            if os.path.isdir(full_path):
                files.extend(list_files_recursive(full_path))
            else:
                files.append(full_path)
        return files


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
        
    def advance(self, offset):
        self.location += offset
        if self.location < 0:
            self.location = 0
        if self.location > len(self.data):
            missing_bytes = self.location - len(self.data)
            self.data += bytearray(missing_bytes)

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


class Subscriber:
    def __init__(self):
        pass
        
    def update(self, content):
        pass
        
    def raise_modified(self):
        pass
        
    def lower_modified(self):
        pass

        
class AudioSource:

    def __init__(self):
        self.data = b""
        self.size = 0
        self.resource_id = 0
        self.short_id = 0
        self.modified = False
        self.data_OLD = b""
        self.subscribers = set()
        self.stream_type = 0
        self.track_info = None
        
    def set_data(self, data, notify_subscribers=True, set_modified=True):
        if not self.modified and set_modified:
            self.data_OLD = self.data
        self.data = data
        self.size = len(self.data)
        if notify_subscribers:
            for item in self.subscribers:
                item.update(self)
                if not self.modified:
                    item.raise_modified()
        if set_modified:
            self.modified = True
            
    def get_id(self):
        if self.stream_type == BANK:
            return self.get_short_id()
        else:
            return self.get_resource_id()
            
    def is_modified(self):
        return self.modified
            
    def set_track_info(self, track_info,  notify_subscribers=True, set_modified=True):
        if not self.modified and set_modified:
            self.track_info_old = self.track_info
        self.track_info = track_info
        if notify_subscribers:
            for item in self.subscribers:
                item.update(self)
                if not self.modified:
                    item.raise_modified()
        if set_modified:
            self.modified = True
            
    def get_track_info(self):
        return self.track_info
        
    def get_data(self):
        return self.data
        
    def get_resource_id(self):
        return self.resource_id
        
    def get_short_id(self):
        return self.short_id
        
    def revert_modifications(self, notify_subscribers=True):
        if self.track_info is not None:
            self.track_info.revert_modifications()
        if self.modified:
            self.modified = False
            if self.data_OLD != b"":
                self.data = self.data_OLD
                self.data_OLD = b""
            self.size = len(self.data)
            if notify_subscribers:
                for item in self.subscribers:
                    item.lower_modified()
                    item.update(self)

                
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
        
    def get_data(self):
        return (struct.pack("<QQQQQQQIIIIII",
            self.file_id,
            self.type_id,
            self.toc_data_offset,
            self.stream_file_offset,
            self.gpu_resource_offset,
            self.unknown1,
            self.unknown2,
            self.toc_data_size,
            self.stream_size,
            self.gpu_resource_size,
            self.unknown3,
            self.unknown4,
            self.entry_index))

                
class WwiseDep:

    def __init__(self):
        self.data = ""
        
    def from_memory_stream(self, stream):
        self.offset = stream.tell()
        self.tag = stream.uint32_read()
        self.data_size = stream.uint32_read()
        self.data = stream.read(self.data_size).decode('utf-8')
        
    def get_data(self):
        return (self.tag.to_bytes(4, byteorder='little')
                + self.data_size.to_bytes(4, byteorder='little')
                + self.data.encode('utf-8'))

                
class DidxEntry:
    def __init__(self):
        self.id = self.offset = self.size = 0
        
    @classmethod
    def from_bytes(cls, bytes):
        e = DidxEntry()
        e.id, e.offset, e.size = struct.unpack("<III", bytes)
        return e
        
    def get_data(self):
        return struct.pack("<III", self.id, self.offset, self.size)

        
class MediaIndex:

    def __init__(self):
        self.entries = {}
        self.data = {}
        
    def load(self, didxChunk, dataChunk):
        for n in range(int(len(didxChunk)/12)):
            entry = DidxEntry.from_bytes(didxChunk[12*n : 12*(n+1)])
            self.entries[entry.id] = entry
            self.data[entry.id] = dataChunk[entry.offset:entry.offset+entry.size]
        
    def get_data(self):
        arr = [x.get_data() for x in self.entries.values()]
        data_arr = self.data.values()
        return b"".join(arr) + b"".join(data_arr)
                

class HircEntry:
    
    def __init__(self):
        self.size = self.hierarchy_type = self.hierarchy_id = self.misc = 0
        self.sources = []
        self.track_info = []
        self.soundbank = None
    
    @classmethod
    def from_memory_stream(cls, stream):
        entry = HircEntry()
        entry.hierarchy_type = stream.uint8_read()
        entry.size = stream.uint32_read()
        entry.hierarchy_id = stream.uint32_read()
        entry.misc = stream.read(entry.size - 4)
        return entry
        
    def get_id(self):
        return self.hierarchy_id
        
    def raise_modified(self):
        self.soundbank.raise_modified()
        
    def lower_modified(self):
        self.soundbank.lower_modified()
        
    def get_data(self):
        return self.hierarchy_type.to_bytes(1, byteorder="little") + self.size.to_bytes(4, byteorder="little") + self.hierarchy_id.to_bytes(4, byteorder="little") + self.misc

        
class MusicRandomSequence(HircEntry):
    
    def __init__(self):
        super().__init__()
    
    @classmethod
    def from_memory_stream(cls, stream):
        entry = MusicRandomSequence()
        entry.hierarchy_type = stream.uint8_read()
        entry.size = stream.uint32_read()
        entry.hierarchy_id = stream.uint32_read()
        return entry
        
    def get_data(self):
        pass

        
class RandomSequenceContainer(HircEntry):
    def __init__(self):
        super().__init__()
        self.unused_sections = []
        self.contents = []
        
    @classmethod
    def from_memory_stream(cls, stream):
        entry = RandomSequenceContainer()
        entry.hierarchy_type = stream.uint8_read()
        entry.size = stream.uint32_read()
        start_position = stream.tell()
        entry.hierarchy_id = stream.uint32_read()

        # ---------------------------------------
        section_start = stream.tell()
        stream.advance(1)
        n = stream.uint8_read() #num fx
        if n == 0:
            stream.advance(12)
        else:
            stream.advance(7*n + 13)
        stream.advance(5*stream.uint8_read()) #number of props
        stream.advance(9*stream.uint8_read()) #number of props (again)
        if stream.uint8_read() & 0b0000_0010: #positioning bit vector
            if stream.uint8_read() & 0b0100_0000: # relative pathing bit vector
                stream.advance(5)
                stream.advance(16*stream.uint32_read())
                stream.advance(20*stream.uint32_read())
        if stream.uint8_read() & 0b0000_1000: #I forget what this is for
            stream.advance(26)
        else:
           stream.advance(10)
        stream.advance(3*stream.uint8_read()) #num state props
        for _ in range(stream.uint8_read()): #num state groups
            stream.advance(5)
            stream.advance(8*stream.uint8_read())
        for _ in range(stream.uint16_read()):  # num RTPC
            stream.advance(12)
            stream.advance(stream.uint16_read()*12)
        section_end = stream.tell()
        # ---------------------------------------

        stream.seek(section_start)
        entry.unused_sections.append(stream.read(section_end-section_start+24))

        for _ in range(stream.uint32_read()): #number of children (tracks)
            entry.contents.append(stream.uint32_read())

        entry.unused_sections.append(stream.read(entry.size - (stream.tell()-start_position)))
        return entry
        
    def get_data(self):
        return (
            b"".join([
                struct.pack("<BII", self.hierarchy_type, self.size, self.hierarchy_id),
                self.unused_sections[0],
                len(self.contents).to_bytes(4, byteorder="little"),
                b"".join([x.to_bytes(4, byteorder="little") for x in self.contents]),
                self.unused_sections[1]
            ])
        )

    
class MusicSegment(HircEntry):

    def __init__(self):
        super().__init__()
        self.tracks = []
        self.duration = 0
        self.entry_marker = None
        self.exit_marker = None
        self.unused_sections = []
        self.markers = []
        self.modified = False
    
    @classmethod
    def from_memory_stream(cls, stream):
        entry = MusicSegment()
        entry.hierarchy_type = stream.uint8_read()
        entry.size = stream.uint32_read()
        entry.hierarchy_id = stream.uint32_read()
        entry.unused_sections.append(stream.read(15))
        n = stream.uint8_read() #number of props
        stream.seek(stream.tell()-1)
        entry.unused_sections.append(stream.read(5*n + 1))
        n = stream.uint8_read() #number of props (again)
        stream.seek(stream.tell()-1)
        entry.unused_sections.append(stream.read(5*n + 1 + 12 + 4)) #the 4 is the count of state props, state chunks, and RTPC, which are currently always 0
        n = stream.uint32_read() #number of children (tracks)
        for _ in range(n):
            entry.tracks.append(stream.uint32_read())
        entry.unused_sections.append(stream.read(23)) #meter info
        n = stream.uint32_read() #number of stingers
        stream.seek(stream.tell()-4)
        entry.unused_sections.append(stream.read(24*n + 4))
        entry.duration = struct.unpack("<d", stream.read(8))[0]
        n = stream.uint32_read() #number of markers
        for i in range(n):
            id = stream.uint32_read()
            position = struct.unpack("<d", stream.read(8))[0]
            name = []
            temp = b"1"
            while temp != b"\x00":
                temp = stream.read(1)
                name.append(temp)
            name = b"".join(name)
            marker = [id, position, name]
            entry.markers.append(marker)
            if i == 0:
                entry.entry_marker = marker
            elif i == n-1:
                entry.exit_marker = marker
        return entry
        
    def set_data(self, duration=None, entry_marker=None, exit_marker=None):
        if not self.modified:
            self.duration_old = self.duration
            self.entry_marker_old = self.entry_marker[1]
            self.exit_marker_old = self.exit_marker[1]
            self.raise_modified()
        if duration is not None: self.duration = duration
        if entry_marker is not None: self.entry_marker[1] = entry_marker
        if exit_marker is not None: self.exit_marker[1] = exit_marker
        self.modified = True
        
    def revert_modifications(self):
        if self.modified:
            self.lower_modified()
            self.entry_marker[1] = self.entry_marker_old
            self.exit_marker[1] = self.exit_marker_old
            self.duration = self.duration_old
            self.modified = False
        
    def get_data(self):
        return (
            b"".join([
                struct.pack("<BII", self.hierarchy_type, self.size, self.hierarchy_id),
                self.unused_sections[0],
                self.unused_sections[1],
                self.unused_sections[2],
                len(self.tracks).to_bytes(4, byteorder="little"),
                b"".join([x.to_bytes(4, byteorder="little") for x in self.tracks]),
                self.unused_sections[3],
                self.unused_sections[4],
                struct.pack("<d", self.duration),
                len(self.markers).to_bytes(4, byteorder="little"),
                b"".join([b"".join([x[0].to_bytes(4, byteorder="little"), struct.pack("<d", x[1]), x[2]]) for x in self.markers])
            ])
        )

        
class HircEntryFactory:
    
    @classmethod
    def from_memory_stream(cls, stream):
        hierarchy_type = stream.uint8_read()
        stream.seek(stream.tell()-1)
        if hierarchy_type == 2: #sound
            return Sound.from_memory_stream(stream)
        elif hierarchy_type == 11: #music track
            return MusicTrack.from_memory_stream(stream)
        elif hierarchy_type == 0x0A: #music segment
            return MusicSegment.from_memory_stream(stream)
        elif hierarchy_type == 0x05: #random sequence container
            return RandomSequenceContainer.from_memory_stream(stream)
        else:
            return HircEntry.from_memory_stream(stream)

        
class HircReader:
    
    def __init__(self, soundbank = None):
        self.entries = {}
        self.soundbank = soundbank
        
    def load(self, hierarchy_data):
        self.entries.clear()
        reader = MemoryStream()
        reader.write(hierarchy_data)
        reader.seek(0)
        num_items = reader.uint32_read()
        for item in range(num_items):
            entry = HircEntryFactory.from_memory_stream(reader)
            entry.soundbank = self.soundbank
            self.entries[entry.get_id()] = entry
            
    def get_data(self):
        arr = [entry.get_data() for entry in self.entries.values()]
        return len(arr).to_bytes(4, byteorder="little") + b"".join(arr)

            
class BankParser:
    
    def __init__(self):
        self.chunks = {}
        
    def load(self, bank_data):
        self.chunks.clear()
        reader = MemoryStream()
        reader.write(bank_data)
        reader.seek(0)
        while True:
            tag = ""
            try:
                tag = reader.read(4).decode('utf-8')
            except:
                break
            size = reader.uint32_read()
            self.chunks[tag] = reader.read(size)
            
    def GetChunk(self, chunk_tag):
        try:
            return self.chunks[chunk_tag]
        except:
            return None

            
class BankSourceStruct:

    def __init__(self):
        self.plugin_id = 0
        self.stream_type = self.source_id = self.mem_size = self.bit_flags = 0
        
    @classmethod
    def from_bytes(cls, bytes):
        b = BankSourceStruct()
        b.plugin_id, b.stream_type, b.source_id, b.mem_size, b.bit_flags = struct.unpack("<IBIIB", bytes)
        return b
        
    def get_data(self):
        return struct.pack("<IBIIB", self.plugin_id, self.stream_type, self.source_id, self.mem_size, self.bit_flags)

        
class TrackInfoStruct:
    
    def __init__(self):
        self.track_id = self.source_id = self.event_id = self.play_at = self.begin_trim_offset = self.end_trim_offset = self.source_duration = 0
        self.play_at_old = self.begin_trim_offset_old = self.end_trim_offset_old = self.source_duration_old = 0
        self.modified = False
        self.soundbanks = set()
        
    @classmethod
    def from_bytes(cls, bytes):
        t = TrackInfoStruct()
        t.track_id, t.source_id, t.event_id, t.play_at, t.begin_trim_offset, t.end_trim_offset, t.source_duration = struct.unpack("<IIIdddd", bytes)
        return t
        
    def get_id(self):
        if self.source_id != 0:
            return self.source_id
        else:
            return self.event_id
            
    def is_modified(self):
        return self.modified
            
    def set_data(self, play_at=None, begin_trim_offset=None, end_trim_offset=None, source_duration=None):
        if not self.modified:
            self.play_at_old = self.play_at
            self.begin_trim_offset_old = self.begin_trim_offset
            self.end_trim_offset_old = self.end_trim_offset
            self.source_duration_old = self.source_duration
            self.raise_modified()
        if play_at is not None: self.play_at = play_at
        if begin_trim_offset is not None: self.begin_trim_offset = begin_trim_offset
        if end_trim_offset is not None: self.end_trim_offset = end_trim_offset
        if source_duration is not None: self.source_duration = source_duration
        self.modified = True
        
    def revert_modifications(self):
        if self.modified:
            self.lower_modified()
            self.play_at = self.play_at_old
            self.begin_trim_offset = self.begin_trim_offset_old
            self.end_trim_offset = self.end_trim_offset_old
            self.source_duration = self.source_duration_old
            self.modified = False
            
    def raise_modified(self):
        for bank in self.soundbanks:
            bank.raise_modified()
        
    def lower_modified(self):
        for bank in self.soundbanks:
            bank.lower_modified()
        
    def get_data(self):
        return struct.pack("<IIIdddd", self.track_id, self.source_id, self.event_id, self.play_at, self.begin_trim_offset, self.end_trim_offset, self.source_duration)

            
class MusicTrack(HircEntry):
    
    def __init__(self):
        super().__init__()
        self.bit_flags = 0
        
    @classmethod
    def from_memory_stream(cls, stream):
        entry = MusicTrack()
        entry.hierarchy_type = stream.uint8_read()
        entry.size = stream.uint32_read()
        start_position = stream.tell()
        entry.hierarchy_id = stream.uint32_read()
        entry.bit_flags = stream.uint8_read()
        num_sources = stream.uint32_read()
        for _ in range(num_sources):
            source = BankSourceStruct.from_bytes(stream.read(14))
            entry.sources.append(source)
        num_track_info = stream.uint32_read()
        for _ in range(num_track_info):
            track = TrackInfoStruct.from_bytes(stream.read(44))
            entry.track_info.append(track)
        entry.misc = stream.read(entry.size - (stream.tell()-start_position))
        return entry

    def get_data(self):
        b = b"".join([source.get_data() for source in self.sources])
        t = b"".join([track.get_data() for track in self.track_info])
        return struct.pack("<BIIBI", self.hierarchy_type, self.size, self.hierarchy_id, self.bit_flags, len(self.sources)) + b + len(self.track_info).to_bytes(4, byteorder="little") + t + self.misc

    
class Sound(HircEntry):
    
    def __init__(self):
        super().__init__()
    
    @classmethod
    def from_memory_stream(cls, stream):
        entry = Sound()
        entry.hierarchy_type = stream.uint8_read()
        entry.size = stream.uint32_read()
        entry.hierarchy_id = stream.uint32_read()
        entry.sources.append(BankSourceStruct.from_bytes(stream.read(14)))
        entry.misc = stream.read(entry.size - 18)
        return entry

    def get_data(self):
        return struct.pack(f"<BII14s{len(self.misc)}s", self.hierarchy_type, self.size, self.hierarchy_id, self.sources[0].get_data(), self.misc)

        
class WwiseBank(Subscriber):
    
    def __init__(self):
        self.data = b""
        self.bank_header = b""
        self.toc_data_header = b""
        self.bank_misc_data = b""
        self.modified = False
        self.toc_header = None
        self.dep = None
        self.modified_count = 0
        self.hierarchy = None
        self.content = []
        
    def add_content(self, content):
        content.subscribers.add(self)
        if content.track_info is not None:
            content.track_info.soundbanks.add(self)
        self.content.append(content)
        
    def remove_content(self, content):
        try:
            content.subscribers.remove(self)
        except:
            pass
            
        try:
            self.content.remove(content)
        except:
            pass
            
        try:
            content.track_info.soundbanks.remove(self)
        except:
            pass
  
    def get_content(self):
        return self.content
        
    def raise_modified(self):
        self.modified = True
        self.modified_count += 1
        
    def lower_modified(self):
        if self.modified:
            self.modified_count -= 1
            if self.modified_count == 0:
                self.modified = False
        
    def get_name(self):
        return self.dep.data
        
    def get_id(self):
        try:
            return self.toc_header.file_id
        except:
            return 0
            
    def get_type_id(self):
        try:
            return self.toc_header.type_id
        except:
            return 0
            
    def get_data(self):
        return self.data
            
    def generate(self, audio_sources, eventTrackInfo):
        data = bytearray()
        data += self.bank_header
        
        didx_section = b""
        data_section = b""
        offset = 0
        
        #regenerate soundbank from the hierarchy information
        max_progress = 0
        for entry in self.hierarchy.entries.values():
            if entry.hierarchy_type == SOUND:
                max_progress += 1
            elif entry.hierarchy_type == MUSIC_TRACK:
                max_progress += len(entry.sources)
                    
        didx_array = []
        data_array = []
        
        added_sources = set()
        
        for entry in self.hierarchy.entries.values():
            for index, info in enumerate(entry.track_info):
                if info.event_id != 0:
                    entry.track_info[index] = eventTrackInfo[info.event_id]
            for source in entry.sources:
                if source.plugin_id == VORBIS:
                    try:
                        audio = audio_sources[source.source_id]
                    except KeyError:
                        continue
                    try:
                        count = 0
                        for info in entry.track_info:
                            if info.source_id == source.source_id:
                                break
                            count += 1
                        if audio.get_track_info() is not None: #is this needed?
                            entry.track_info[count] = audio.get_track_info()
                    except: #exception because there may be no original track info struct
                        pass
                    if source.stream_type == PREFETCH_STREAM and source.source_id not in added_sources:
                        data_array.append(audio.get_data()[:source.mem_size])
                        didx_array.append(struct.pack("<III", source.source_id, offset, source.mem_size))
                        offset += source.mem_size
                        added_sources.add(source.source_id)
                    elif source.stream_type == BANK and source.source_id not in added_sources:
                        data_array.append(audio.get_data())
                        didx_array.append(struct.pack("<III", source.source_id, offset, audio.size))
                        offset += audio.size
                        added_sources.add(source.source_id)
                elif source.plugin_id == REV_AUDIO:
                    try:
                        custom_fx_entry = self.hierarchy.entries[source.source_id]
                        fx_data = custom_fx_entry.get_data()
                        plugin_param_size = int.from_bytes(fx_data[13:17], byteorder="little")
                        media_index_id = int.from_bytes(fx_data[19+plugin_param_size:23+plugin_param_size], byteorder="little")
                        audio = audio_sources[media_index_id]
                    except KeyError:
                        continue
                    if source.stream_type == BANK and source.source_id not in added_sources:
                        data_array.append(audio.get_data())
                        didx_array.append(struct.pack("<III", media_index_id, offset, audio.size))
                        offset += audio.size
                        added_sources.add(media_index_id)
        if len(didx_array) > 0:
            data += "DIDX".encode('utf-8') + (12*len(didx_array)).to_bytes(4, byteorder="little")
            data += b"".join(didx_array)
            data += "DATA".encode('utf-8') + sum([len(x) for x in data_array]).to_bytes(4, byteorder="little")
            data += b"".join(data_array)
            
        hierarchy_section = self.hierarchy.get_data()
        data += "HIRC".encode('utf-8') + len(hierarchy_section).to_bytes(4, byteorder="little")
        data += hierarchy_section
        data += self.bank_misc_data
        self.toc_header.toc_data_size = len(data) + len(self.toc_data_header)
        self.toc_data_header[4:8] = len(data).to_bytes(4, byteorder="little")
        self.data = data
                     
    def get_entry_index(self):
        try:
            return self.toc_header.entry_index
        except:
            return 0
        

class WwiseStream(Subscriber):

    def __init__(self):
        self.content = None
        self.modified = False
        self.toc_header = None
        self.TocData = bytearray()
        
    def set_content(self, content):
        try:
            self.content.subscribers.remove(self)
        except:
            pass
        self.content = content
        content.subscribers.add(self)
        
    def update(self, content):
        self.toc_header.stream_size = content.size
        self.TocData[8:12] = content.size.to_bytes(4, byteorder='little')
        
    def raise_modified(self):
        self.modified = True
        
    def lower_modified(self):
        self.modified = False
        
    def get_id(self):
        try:
            return self.toc_header.file_id
        except:
            return 0
        
    def get_type_id(self):
        try:
            return self.toc_header.type_id
        except:
            return 0
            
    def get_entry_index(self):
        try:
            return self.toc_header.entry_index
        except:
            return 0
            
    def get_data(self):
        return self.content.get_data()


class StringEntry:

    def __init__(self):
        self.text = ""
        self.text_old = ""
        self.string_id = 0
        self.modified = False
        
    def get_id(self):
        return self.string_id
        
    def get_text(self):
        return self.text
        
    def set_text(self, text):
        if not self.modified:
            self.text_old = self.text
        self.modified = True
        self.text = text
        
    def revert_modifications(self):
        if self.modified:
            self.text = self.text_old
            self.modified = False

        
class TextBank:
    
    def __init__(self):
        self.toc_header = None
        self.data = b''
        self.string_ids = []
        self.language = 0
        self.modified = False
        
    def set_data(self, data):
        self.string_ids.clear()
        num_entries = int.from_bytes(data[8:12], byteorder='little')
        id_section_start = 16
        offset_section_start = id_section_start + 4 * num_entries
        data_section_start = offset_section_start + 4 * num_entries
        ids = data[id_section_start:offset_section_start]
        offsets = data[offset_section_start:data_section_start]
        for n in range(num_entries):
            string_id = int.from_bytes(ids[4*n:+4*(n+1)], byteorder="little")
            self.string_ids.append(string_id)
            
    def update(self):
        pass
        
    def get_data(self):
        return self.data
        
    def GetLanguage(self):
        return self.language
        
    def is_modified(self):
        return self.modified
        
    def generate(self, string_entries):
        entries = string_entries[self.language]
        stream = MemoryStream()
        stream.write(b'\xae\xf3\x85\x3e\x01\x00\x00\x00')
        stream.write(len(self.string_ids).to_bytes(4, byteorder="little"))
        stream.write(self.language.to_bytes(4, byteorder="little"))
        offset = 16 + 8*len(self.string_ids)
        for i in self.string_ids:
            stream.write(entries[i].get_id().to_bytes(4, byteorder="little"))
        for i in self.string_ids:
            stream.write(offset.to_bytes(4, byteorder="little"))
            initial_position = stream.tell()
            stream.seek(offset)
            text_bytes = entries[i].text.encode('utf-8') + b'\x00'
            stream.write(text_bytes)
            offset += len(text_bytes)
            stream.seek(initial_position)
        self.data = stream.data
        self.toc_header.toc_data_size = len(self.data)
        
    def Rebuild(self, string_id, offset_difference):
        pass
        
    def get_id(self):
        try:
            return self.toc_header.file_id
        except:
            return 0
        
    def get_type_id(self):
        try:
            return self.toc_header.type_id
        except:
            return 0
            
    def get_entry_index(self):
        try:
            return self.toc_header.entry_index
        except:
            return 0


class FileReader:
    
    def __init__(self):
        self.wwise_streams = {}
        self.wwise_banks = {}
        self.audio_sources = {}
        self.text_banks = {}
        self.music_track_events = {}
        self.string_entries = {}
        self.music_segments = {}
        
    def from_file(self, path):
        self.name = os.path.basename(path)
        self.path = path
        toc_file = MemoryStream()
        with open(path, 'r+b') as f:
            toc_file = MemoryStream(f.read())

        stream_file = MemoryStream()
        if os.path.isfile(path+".stream"):
            with open(path+".stream", 'r+b') as f:
                stream_file = MemoryStream(f.read())
        self.load(toc_file, stream_file)
        
    def to_file(self, path):
        toc_file = MemoryStream()
        stream_file = MemoryStream()
        self.num_files = len(self.wwise_streams) + 2*len(self.wwise_banks) + len(self.text_banks)
        self.num_types = 0
        if len(self.wwise_streams) > 0: self.num_types += 1
        if len(self.wwise_banks) > 0: self.num_types += 2
        if len(self.text_banks) > 0: self.num_types += 1
        
        toc_file.write(self.magic.to_bytes(4, byteorder="little"))
        
        toc_file.write(self.num_types.to_bytes(4, byteorder="little"))
        toc_file.write(self.num_files.to_bytes(4, byteorder="little"))
        toc_file.write(self.unknown.to_bytes(4, byteorder="little"))
        toc_file.write(self.unk4Data)
        
        if len(self.wwise_streams) > 0:
            unk = 0
            toc_file.write(unk.to_bytes(8, byteorder='little'))
            unk = WWISE_STREAM
            toc_file.write(unk.to_bytes(8, byteorder='little'))
            unk = len(self.wwise_streams)
            toc_file.write(unk.to_bytes(8, byteorder='little'))
            unk = 16
            toc_file.write(unk.to_bytes(4, byteorder='little'))
            unk = 64
            toc_file.write(unk.to_bytes(4, byteorder='little'))
            
        if len(self.wwise_banks) > 0:
            unk = 0
            toc_file.write(unk.to_bytes(8, byteorder='little'))
            unk = WWISE_BANK
            toc_file.write(unk.to_bytes(8, byteorder='little'))
            unk = len(self.wwise_banks)
            toc_file.write(unk.to_bytes(8, byteorder='little'))
            unk = 16
            toc_file.write(unk.to_bytes(4, byteorder='little'))
            unk = 64
            toc_file.write(unk.to_bytes(4, byteorder='little'))
            
            #deps
            unk = 0
            toc_file.write(unk.to_bytes(8, byteorder='little'))
            unk = WWISE_DEP
            toc_file.write(unk.to_bytes(8, byteorder='little'))
            unk = len(self.wwise_banks)
            toc_file.write(unk.to_bytes(8, byteorder='little'))
            unk = 16
            toc_file.write(unk.to_bytes(4, byteorder='little'))
            unk = 64
            toc_file.write(unk.to_bytes(4, byteorder='little'))
            
        if len(self.text_banks) > 0:
            unk = 0
            toc_file.write(unk.to_bytes(8, byteorder='little'))
            unk = STRING
            toc_file.write(unk.to_bytes(8, byteorder='little'))
            unk = len(self.text_banks)
            toc_file.write(unk.to_bytes(8, byteorder='little'))
            unk = 16
            toc_file.write(unk.to_bytes(4, byteorder='little'))
            unk = 64
            toc_file.write(unk.to_bytes(4, byteorder='little'))
        
        file_position = toc_file.tell()
        for key in self.wwise_streams.keys():
            toc_file.seek(file_position)
            file_position += 80
            stream = self.wwise_streams[key]
            toc_file.write(stream.toc_header.get_data())
            toc_file.seek(stream.toc_header.toc_data_offset)
            toc_file.write(pad_to_16_byte_align(stream.TocData))
            stream_file.seek(stream.toc_header.stream_file_offset)
            stream_file.write(pad_to_16_byte_align(stream.content.get_data()))
            
        for key in self.wwise_banks.keys():
            toc_file.seek(file_position)
            file_position += 80
            bank = self.wwise_banks[key]
            toc_file.write(bank.toc_header.get_data())
            toc_file.seek(bank.toc_header.toc_data_offset)
            toc_file.write(pad_to_16_byte_align(bank.toc_data_header + bank.get_data()))
            
        for key in self.wwise_banks.keys():
            toc_file.seek(file_position)
            file_position += 80
            bank = self.wwise_banks[key]
            toc_file.write(bank.dep.toc_header.get_data())
            toc_file.seek(bank.dep.toc_header.toc_data_offset)
            toc_file.write(pad_to_16_byte_align(bank.dep.get_data()))
            
        for key in self.text_banks.keys():
            toc_file.seek(file_position)
            file_position += 80
            entry = self.text_banks[key]
            toc_file.write(entry.toc_header.get_data())
            toc_file.seek(entry.toc_header.toc_data_offset)
            toc_file.write(pad_to_16_byte_align(entry.get_data()))
            
        with open(os.path.join(path, self.name), 'w+b') as f:
            f.write(toc_file.data)
            
        if len(stream_file.data) > 0:
            with open(os.path.join(path, self.name+".stream"), 'w+b') as f:
                f.write(stream_file.data)

    def rebuild_headers(self):
        self.num_types = 0
        if len(self.wwise_streams) > 0: self.num_types += 1
        if len(self.wwise_banks) > 0: self.num_types += 2
        if len(self.text_banks) > 0: self.num_types += 1
        self.num_files = len(self.wwise_streams) + 2*len(self.wwise_banks) + len(self.text_banks)
        stream_file_offset = 0
        toc_file_offset = 80 + self.num_types * 32 + 80 * self.num_files
        for key, value in self.wwise_streams.items():
            value.toc_header.stream_file_offset = stream_file_offset
            value.toc_header.toc_data_offset = toc_file_offset
            stream_file_offset += _16_byte_align(value.toc_header.stream_size)
            toc_file_offset += _16_byte_align(value.toc_header.toc_data_size)
        
        for key, value in self.wwise_banks.items():
            value.generate(self.audio_sources, self.music_track_events)
            
            value.toc_header.toc_data_offset = toc_file_offset
            toc_file_offset += _16_byte_align(value.toc_header.toc_data_size)
            
        for key, value in self.wwise_banks.items():
            value.dep.toc_header.toc_data_offset = toc_file_offset
            toc_file_offset += _16_byte_align(value.toc_header.toc_data_size)
            
        for key, value in self.text_banks.items():
            value.generate(string_entries=self.string_entries)
            value.toc_header.toc_data_offset = toc_file_offset
            toc_file_offset += _16_byte_align(value.toc_header.toc_data_size)
        
    def load(self, toc_file, stream_file):
        self.wwise_streams.clear()
        self.wwise_banks.clear()
        self.audio_sources.clear()
        self.text_banks.clear()
        self.music_track_events.clear()
        self.string_entries.clear()
        self.music_segments.clear()
        
        media_index = MediaIndex()
        
        self.magic      = toc_file.uint32_read()
        if self.magic != 4026531857: return False

        self.num_types   = toc_file.uint32_read()
        self.num_files   = toc_file.uint32_read()
        self.unknown    = toc_file.uint32_read()
        self.unk4Data   = toc_file.read(56)
        toc_file.seek(toc_file.tell() + 32 * self.num_types)
        toc_start = toc_file.tell()
        for n in range(self.num_files):
            toc_file.seek(toc_start + n*80)
            toc_header = TocHeader()
            toc_header.from_memory_stream(toc_file)
            entry = None
            if toc_header.type_id == WWISE_STREAM:
                audio = AudioSource()
                audio.stream_type = STREAM
                entry = WwiseStream()
                entry.toc_header = toc_header
                toc_file.seek(toc_header.toc_data_offset)
                entry.TocData = toc_file.read(toc_header.toc_data_size)
                stream_file.seek(toc_header.stream_file_offset)
                audio.set_data(stream_file.read(toc_header.stream_size), notify_subscribers=False, set_modified=False)
                audio.resource_id = toc_header.file_id
                entry.set_content(audio)
                self.wwise_streams[entry.get_id()] = entry
            elif toc_header.type_id == WWISE_BANK:
                entry = WwiseBank()
                entry.toc_header = toc_header
                toc_data_offset = toc_header.toc_data_offset
                toc_data_size = toc_header.toc_data_size
                toc_file.seek(toc_data_offset)
                entry.toc_data_header = toc_file.read(16)
                bank = BankParser()
                bank.load(toc_file.read(toc_header.toc_data_size-16))
                entry.bank_header = "BKHD".encode('utf-8') + len(bank.chunks["BKHD"]).to_bytes(4, byteorder="little") + bank.chunks["BKHD"]
                
                hirc = HircReader(soundbank=entry)
                try:
                    hirc.load(bank.chunks['HIRC'])
                except KeyError:
                    pass
                entry.hierarchy = hirc
                #Add all bank sources to the source list
                if "DIDX" in bank.chunks.keys():
                    bank_id = entry.toc_header.file_id
                    media_index.load(bank.chunks["DIDX"], bank.chunks["DATA"])
                
                entry.bank_misc_data = b''
                for chunk in bank.chunks.keys():
                    if chunk not in ["BKHD", "DATA", "DIDX", "HIRC"]:
                        entry.bank_misc_data = entry.bank_misc_data + chunk.encode('utf-8') + len(bank.chunks[chunk]).to_bytes(4, byteorder='little') + bank.chunks[chunk]
                        
                self.wwise_banks[entry.get_id()] = entry
            elif toc_header.type_id == WWISE_DEP: #wwise dep
                dep = WwiseDep()
                dep.toc_header = toc_header
                toc_file.seek(toc_header.toc_data_offset)
                dep.from_memory_stream(toc_file)
                try:
                    self.wwise_banks[toc_header.file_id].dep = dep
                except KeyError:
                    pass
            elif toc_header.type_id == STRING: #string_entry
                toc_file.seek(toc_header.toc_data_offset)
                data = toc_file.read(toc_header.toc_data_size)
                num_entries = int.from_bytes(data[8:12], byteorder='little')
                language = int.from_bytes(data[12:16], byteorder='little')
                if language not in self.string_entries:
                    self.string_entries[language] = {}
                id_section_start = 16
                offset_section_start = id_section_start + 4 * num_entries
                data_section_start = offset_section_start + 4 * num_entries
                ids = data[id_section_start:offset_section_start]
                offsets = data[offset_section_start:data_section_start]
                text_bank = TextBank()
                text_bank.toc_header = toc_header
                text_bank.language = language
                for n in range(num_entries):
                    entry = StringEntry()
                    string_id = int.from_bytes(ids[4*n:+4*(n+1)], byteorder="little")
                    text_bank.string_ids.append(string_id)
                    string_offset = int.from_bytes(offsets[4*n:4*(n+1)], byteorder="little")
                    entry.string_id = string_id
                    stopIndex = string_offset + 1
                    while data[stopIndex] != 0:
                        stopIndex += 1
                    entry.text = data[string_offset:stopIndex].decode('utf-8')
                    self.string_entries[language][string_id] = entry
                self.text_banks[text_bank.get_id()] = text_bank
        
        # ---------- Backwards compatibility checks ----------
        for bank in self.wwise_banks.values():
            if bank.dep == None: #can be None because older versions didn't save the dep along with the bank
                if not self.load_deps():
                    print("Failed to load")
                    self.wwise_streams.clear()
                    self.wwise_banks.clear()
                    self.text_banks.clear()
                    self.audio_sources.clear()
                    return
                break
        
        if len(self.wwise_banks) == 0 and len(self.wwise_streams) > 0: #0 if patch was only for streams
            if not self.load_banks():
                print("Failed to load")
                self.wwise_streams.clear()
                self.wwise_banks.clear()
                self.text_banks.clear()
                self.audio_sources.clear()
                return
        # ---------- End backwards compatibility checks ----------
        
        # Create all AudioSource objects
        for bank in self.wwise_banks.values():
            for entry in bank.hierarchy.entries.values():
                for source in entry.sources:
                    if source.plugin_id == VORBIS and source.stream_type == BANK and source.source_id not in self.audio_sources:
                        try:
                            audio = AudioSource()
                            audio.stream_type = BANK
                            audio.short_id = source.source_id
                            audio.set_data(media_index.data[source.source_id], set_modified=False, notify_subscribers=False)
                            self.audio_sources[source.source_id] = audio
                        except KeyError:
                            pass
                    elif source.plugin_id == VORBIS and source.stream_type in [STREAM, PREFETCH_STREAM] and source.source_id not in self.audio_sources:
                        try:
                            stream_resource_id = murmur64_hash((os.path.dirname(bank.dep.data) + "/" + str(source.source_id)).encode('utf-8'))
                            audio = self.wwise_streams[stream_resource_id].content
                            audio.short_id = source.source_id
                            self.audio_sources[source.source_id] = audio
                        except KeyError:
                            pass
                    elif source.plugin_id == REV_AUDIO and source.stream_type == BANK and source.source_id not in self.audio_sources:
                        try:
                            custom_fx = bank.hierarchy.entries[source.source_id]
                            data = custom_fx.get_data()
                            plugin_param_size = int.from_bytes(data[13:17], byteorder="little")
                            media_index_id = int.from_bytes(data[19+plugin_param_size:23+plugin_param_size], byteorder="little")
                            audio = AudioSource()
                            audio.stream_type = BANK
                            audio.short_id = media_index_id
                            audio.set_data(media_index.data[media_index_id], set_modified=False, notify_subscribers=False)
                            self.audio_sources[media_index_id] = audio
                        except KeyError:
                            pass
                for info in entry.track_info:
                    if info.event_id != 0:
                        self.music_track_events[info.event_id] = info
                if isinstance(entry, MusicSegment):
                    self.music_segments[entry.get_id()] = entry

        #construct list of audio sources in each bank
        #add track_info to audio sources?
        for bank in self.wwise_banks.values():
            for entry in bank.hierarchy.entries.values():
                for info in entry.track_info:
                    try:
                        if info.source_id != 0:
                            self.audio_sources[info.source_id].set_track_info(info, notify_subscribers=False, set_modified=False)
                    except:
                        continue
                for source in entry.sources:
                    try:
                        if source.plugin_id == VORBIS and self.audio_sources[source.source_id] not in bank.get_content(): #may be missing streamed audio if the patch didn't change it
                            bank.add_content(self.audio_sources[source.source_id])
                    except:
                        continue
                
        
    """
    Rework this so that it doesn't involve any types of UI relative logic
    """
    def load_deps(self):
        pass
        
    """
    Rework this so that it doesn't involve any types of UI relative logic
    """
    def load_banks(self):
        pass
        

class SoundHandler:
    
    def __init__(self):
        self.audio_process = None
        self.wave_object = None
        self.audio_id = -1
        self.audio = pyaudio.PyAudio()
        
    def kill_sound(self):
        if self.audio_process is not None:
            if self.callback is not None:
                self.callback()
                self.callback = None
            self.audio_process.close()
            self.wave_file.close()
            try:
                os.remove(self.audio_file)
            except:
                pass
            self.audio_process = None
        
    def play_audio(self, sound_id, sound_data, callback=None):
        if not os.path.exists(VGMSTREAM):
            return
        self.kill_sound()
        self.callback = callback
        if self.audio_id == sound_id:
            self.audio_id = -1
            return
        filename = f"temp{sound_id}"
        if not os.path.isfile(f"{filename}.wav"):
            with open(f'{os.path.join(TMP, filename)}.wem', 'wb') as f:
                f.write(sound_data)
            process = subprocess.run([VGMSTREAM, "-o", f"{os.path.join(TMP, filename)}.wav", f"{os.path.join(TMP, filename)}.wem"], stdout=subprocess.DEVNULL)
            os.remove(f"{os.path.join(TMP, filename)}.wem")
            if process.returncode != 0:
                logger.error(f"Encountered error when converting {sound_id}.wem for playback")
                self.callback = None
                return
            
        self.audio_id = sound_id
        self.wave_file = wave.open(f"{os.path.join(TMP, filename)}.wav")
        self.audio_file = f"{os.path.join(TMP, filename)}.wav"
        self.frame_count = 0
        self.max_frames = self.wave_file.getnframes()
        
        def read_stream(input_data, frame_count, time_info, status):
            self.frame_count += frame_count
            if self.frame_count > self.max_frames:
                if self.callback is not None:
                    self.callback()
                    self.callback = None
                self.audio_id = -1
                self.wave_file.close()
                try:
                    os.remove(self.audio_file)
                except:
                    pass
                return (None, pyaudio.paComplete)
            data = self.wave_file.readframes(frame_count)
            if self.wave_file.getnchannels() > 2:
                data = self.downmix_to_stereo(data, self.wave_file.getnchannels(), self.wave_file.getsampwidth(), frame_count)
            return (data, pyaudio.paContinue)

        self.audio_process = self.audio.open(format=self.audio.get_format_from_width(self.wave_file.getsampwidth()),
                channels = min(self.wave_file.getnchannels(), 2),
                rate=self.wave_file.getframerate(),
                output=True,
                stream_callback=read_stream)
        self.audio_file = f"{os.path.join(TMP, filename)}.wav"
        
    def downmix_to_stereo(self, data, channels, channel_width, frame_count):
        if channel_width == 2:
            arr = numpy.frombuffer(data, dtype=numpy.int16)
            stereo_array = numpy.zeros(shape=(frame_count, 2), dtype=numpy.int16)
        elif channel_width == 1:
            arr = numpy.frombuffer(data, dtype=numpy.int8)
            stereo_array = numpy.zeros(shape=(frame_count, 2), dtype=numpy.int8)
        elif channel_width == 4:
            arr = numpy.frombuffer(data, dtype=numpy.int32)
            stereo_array = numpy.zeros(shape=(frame_count, 2), dtype=numpy.int32)
        arr = arr.reshape((frame_count, channels))
        
        if channels == 4:
            for index, frame in enumerate(arr):
                stereo_array[index][0] = int(0.42265 * frame[0] + 0.366025 * frame[2] + 0.211325 * frame[3])
                stereo_array[index][1] = int(0.42265 * frame[1] + 0.366025 * frame[3] + 0.211325 * frame[2])
        
            return stereo_array.tobytes()
                
        if channels == 6:
            for index, frame in enumerate(arr):
                stereo_array[index][0] = int(0.374107*frame[1] + 0.529067*frame[0] + 0.458186*frame[3] + 0.264534*frame[4] + 0.374107*frame[5])
                stereo_array[index][1] = int(0.374107*frame[1] + 0.529067*frame[2] + 0.458186*frame[4] + 0.264534*frame[3] + 0.374107*frame[5])
        
            return stereo_array.tobytes()
        
        #if not 4 or 6 channel, default to taking the L and R channels rather than mixing
        for index, frame in enumerate(arr):
            stereo_array[index][0] = frame[0]
            stereo_array[index][1] = frame[1]
        
        return stereo_array.tobytes()
     

class FileHandler:

    def __init__(self):
        self.file_reader = FileReader()
        
    def revert_all(self):
        for audio in self.file_reader.audio_sources.values():
            audio.revert_modifications()
        for language in self.file_reader.string_entries.values():
            for string in language.values():
                string.revert_modifications()
        for track_info in self.file_reader.music_track_events.values():
            track_info.revert_modifications()
        for music_segment in self.file_reader.music_segments.values():
            music_segment.revert_modifications()
        
    def revert_audio(self, file_id):
        audio = self.get_audio_by_id(file_id)
        audio.revert_modifications()
        
    def dump_as_wem(self, output_file: str, file_id: int):
        pass
        
    def dump_as_wav(self, file_id: int, output_file: str, muted: bool = False):
        """
        @exception
        - OSError
        - CalledProcessError
        """
        save_path = os.path.splitext(output_file)[0]

        if muted:
            subprocess.run([
                FFMPEG, 
                "-f", "lavfi", 
                "-i", "anullsrc=r=48000:cl=stereo",
                "-t", "1", # TO-DO, this should match up with actual duration
                "-c:a", "pcm_s16le",
                f"{save_path}.wav"],
                stdout=subprocess.DEVNULL
            ).check_returncode()

            return

        with open(f"{save_path}.wem", 'wb') as f:
            f.write(self.get_audio_by_id(file_id).get_data())

        subprocess.run(
            [VGMSTREAM, "-o", f"{save_path}.wav", f"{save_path}.wem"], 
            stdout=subprocess.DEVNULL
        ).check_returncode()
        
        os.remove(f"{save_path}.wem")
        
    def dump_multiple_as_wem(self, file_ids: list[int], folder: str):
        """
        @exception
        - OSError
        """
        if not os.path.exists(folder):
            raise OSError(f"Folder {folder} does not exist.")
        
        for file_id in file_ids:
            audio = self.get_audio_by_id(file_id)
            if audio == None:
                continue
            save_path = os.path.join(folder, f"{audio.get_id()}")
            try:
                with open(save_path+".wem", "wb") as f:
                    f.write(audio.get_data())
            except Exception as err:
                logger.error(f"Failed to wirte audio data of source {file_id} to "
                             f"disk. Reason: {err}.")
        
    def dump_multiple_as_wav(
            self, 
            folder: str,
            file_ids: list[str], 
            muted: bool = False,
            with_seq: bool = False):
        """
        @exception
        - OSError
        """

        if not os.path.exists(folder):
            raise OSError(f"Folder {folder} does not exist.")


        for i, file_id in enumerate(file_ids, start=0):
            audio: int | None = self.get_audio_by_id(int(file_id))

            if audio is None: continue

            basename = str(audio.get_id())
            if with_seq:
                basename = f"{i:02d}" + "_" + basename
            save_path = os.path.join(folder, basename)

            if muted:
                process = subprocess.run([
                    FFMPEG, 
                    "-f", "lavfi", 
                    "-i", "anullsrc=r=48000:cl=stereo",
                    "-t", "1", # TO-DO, this should match up with actual duration
                    "-c:a", "pcm_s16le",
                    f"{save_path}.wav"],
                    stdout=subprocess.DEVNULL
                )
                if process.returncode != 0:
                    logger.error(f"FFMPEG failed to create a silent track. "
                                 f"Reason: return code {process.returncode}.")
            else:
                with open(save_path + ".wem", "wb") as f:
                    f.write(audio.get_data())
                process = subprocess.run(
                    [VGMSTREAM, "-o", f"{save_path}.wav", f"{save_path}.wem"],
                    stdout=subprocess.DEVNULL,
                )
                if process.returncode != 0:
                    logger.error(f"Encountered error when converting {basename}.wem to .wav")
                os.remove(f"{save_path}.wem")

    def dump_all_as_wem(self, folder: str):
        """
        @exception
        - OSError
        """
        if not os.path.exists(folder):
            raise OSError(f"Folder {folder} does not exist.")
        
        for bank in self.file_reader.wwise_banks.values():
            subfolder = os.path.join(folder, os.path.basename(bank.dep.data.replace('\x00', '')))

            guard = True
            try:
                if not os.path.exists(subfolder):
                    os.mkdir(subfolder)
            except OSError as err:
                guard = False
                logger.error(f"Failed to create folder {subfolder}. Reason: {err}.")
            if not guard:
                continue

            for audio in bank.get_content():
                save_path = os.path.join(subfolder, f"{audio.get_id()}")

                try:
                    with open(save_path + ".wem", "wb") as f:
                        f.write(audio.get_data())
                except Exception as err:
                    guard = False
                    logger.error(f"Failed to write audio data of source {audio} into "
                                 f"the disk. Reason: {err}.")
                    
    
    def dump_all_as_wav(self, folder: str):
        """
        @exception
        - OSError
        """
        if not os.path.exists(folder):
            raise OSError(f"Folder {folder} does not exist.")

        for bank in self.file_reader.wwise_banks.values():
            subfolder = os.path.join(folder, os.path.basename(bank.dep.data.replace('\x00', '')))
            guard = True
            try:
                if not os.path.exists(subfolder):
                    os.mkdir(subfolder)
            except OSError as err:
                logger.error(f"Failed to create folder {subfolder}. Reason: {err}.")
                guard = False
            if not guard:
                continue

            for audio in bank.get_content():
                save_path = os.path.join(subfolder, f"{audio.get_id()}")

                guard = True
                try:
                    with open(save_path + ".wem", "wb") as f:
                        f.write(audio.get_data())
                except Exception as err:
                    guard = False
                    logger.error(f"Failed to write audio data of source {audio} into "
                                 f"the disk. Reason: {err}.")
                if not guard:
                    continue

                process = subprocess.run([VGMSTREAM, "-o", f"{save_path}.wav", f"{save_path}.wem"], stdout=subprocess.DEVNULL)
                if process.returncode != 0:
                    logger.error(f"Encountered error when converting {os.path.basename(save_path)}.wem to .wav")
                os.remove(f"{save_path}.wem")
        
    def get_number_prefix(self, n):
        """
        @exception
        - TypeError, ValueError
        """
        return int(''.join(takewhile(str.isdigit, n or "")))
        
    def save_archive_file(self, folder: str):
        """
        @exception
        - OSError
        """
        if not os.path.exists(folder):
            raise OSError(f"Folder {folder} does not exist")

        self.file_reader.rebuild_headers()
        self.file_reader.to_file(folder)
            
    """
    The below functions should raise exceptions or return errors instead of 
    slienting out the exception.
    """
    def get_audio_by_id(self, file_id):
        try:
            return self.file_reader.audio_sources[file_id] #short_id
        except KeyError:
            pass
        for source in self.file_reader.audio_sources.values(): #resource_id
            if source.resource_id == file_id:
                return source
                
    """
    The below functions should raise exceptions or return errors instead of 
    slienting out the exception.
    """
    def get_event_by_id(self, event_id):
        try:
            return self.file_reader.music_track_events[event_id]
        except:
            pass
            
    def get_string_by_id(self, string_id):
        try:
            return self.file_reader.string_entries[language][string_id]
        except:
            pass
        
    def get_music_segment_by_id(self, segment_id):
        try:
            return self.file_reader.music_segments[segment_id]
        except:
            pass
    """
    End
    """
        
    def get_wwise_streams(self):
        return self.file_reader.wwise_streams
        
    def get_wwise_banks(self):
        return self.file_reader.wwise_banks
        
    def get_audio(self):
        return self.file_reader.audio_sources
        
    def get_strings(self):
        return self.file_reader.string_entries
        
    def load_archive_file(self, archive_file: str):
        """
        @exception
        - OSError
        - Exception raised from FileReader().from_file()
        """
        if not os.path.exists(archive_file):
            raise OSError(f"Archive file {archive_file} does not exist.")

        if os.path.splitext(archive_file)[1] in (".stream", ".gpu_resources"):
            archive_file = os.path.splitext(archive_file)[0]
        if not os.path.exists(archive_file):
            raise OSError(f"Archive file {archive_file} does not exist.")

        self.file_reader.from_file(archive_file)
            
    def load_patch(self, patch_file: str): #TO-DO: only import if DIFFERENT from original audio; makes it possible to import different mods that change the same soundbank
        """
        @exception
        - OSError
        - Exception arise from FileReader.from_file
        """
        if not os.path.exists(patch_file):
            raise OSError(f"Patch file {patch_file} does not exist.")

        patch_file_reader = FileReader()
        if os.path.splitext(patch_file)[1] in (".stream", ".gpu_resources"):
            patch_file = os.path.splitext(patch_file)[0]
        if not os.path.exists(patch_file):
            raise OSError(f"Patch file {patch_file} does not exist.")

        patch_file_reader.from_file(patch_file)
            
        for bank in patch_file_reader.wwise_banks.values(): #something is a bit wrong here
            #load audio content from the patch
            for new_audio in bank.get_content():
                old_audio = self.get_audio_by_id(new_audio.get_short_id())
                if old_audio is not None:
                    if (not old_audio.modified and new_audio.get_data() != old_audio.get_data()
                        or old_audio.modified and new_audio.get_data() != old_audio.data_OLD):
                        old_audio.set_data(new_audio.get_data())
                    if old_audio.get_track_info() is not None and new_audio.get_track_info() is not None:
                        old_info = old_audio.get_track_info()
                        new_info = new_audio.get_track_info()
                        if (
                            (
                                not old_info.modified 
                                and (
                                    old_info.play_at != new_info.play_at
                                    or old_info.begin_trim_offset != new_info.begin_trim_offset
                                    or old_info.end_trim_offset != new_info.end_trim_offset
                                    or old_info.source_duration != new_info.source_duration
                                )
                            )
                            or
                            (
                                old_info.modified
                                and (
                                    old_info.play_at_old != new_info.play_at
                                    or old_info.begin_trim_offset_old != new_info.begin_trim_offset
                                    or old_info.end_trim_offset_old != new_info.end_trim_offset
                                    or old_info.source_duration_old != new_info.source_duration
                                )
                            )
                        ):
                            old_audio.get_track_info().set_data(play_at=new_info.play_at, begin_trim_offset=new_info.begin_trim_offset, end_trim_offset=new_info.end_trim_offset, source_duration=new_info.source_duration)

        for key, music_segment in patch_file_reader.music_segments.items():
            try:
                old_music_segment = self.file_reader.music_segments[key]
            except:
                continue
            if (
                (
                    not old_music_segment.modified
                    and (
                        music_segment.entry_marker[1] != old_music_segment.entry_marker[1]
                        or music_segment.exit_marker[1] != old_music_segment.exit_marker[1]
                        or music_segment.duration != old_music_segment.duration
                    )
                )
                or
                (
                    old_music_segment.modified
                    and (
                        music_segment.entry_marker[1] != old_music_segment.entry_marker_old
                        or music_segment.exit_marker[1] != old_music_segment.exit_marker_old
                        or music_segment.duration != old_music_segment.duration_old
                    )
                )
            ):
                old_music_segment.set_data(duration=music_segment.duration, entry_marker=music_segment.entry_marker[1], exit_marker=music_segment.exit_marker[1])

        for text_data in patch_file_reader.text_banks.values():
            for string_id in text_data.string_ids:
                new_text_data = patch_file_reader.string_entries[language][string_id]
                try:
                    old_text_data = self.file_reader.string_entries[language][string_id]
                except:
                    continue
                if (
                    (not old_text_data.modified and new_text_data.get_text() != old_text_data.get_text())
                    or (old_text_data.modified and new_text_data.get_text() != old_text_data.text_old)
                ):
                    old_text_data.set_text(new_text_data.get_text())

    def write_patch(self, folder: str):
        """
        @exception
        - OSError
        """
        if not os.path.exists(folder):
            raise OSError("Folder {folder} does not exist")

        patch_file_reader = FileReader()
        patch_file_reader.name = self.file_reader.name + ".patch_0"
        patch_file_reader.magic = self.file_reader.magic
        patch_file_reader.num_types = 0
        patch_file_reader.num_files = 0
        patch_file_reader.unknown = self.file_reader.unknown
        patch_file_reader.unk4Data = self.file_reader.unk4Data
        patch_file_reader.audio_sources = self.file_reader.audio_sources
        patch_file_reader.string_entries = self.file_reader.string_entries
        patch_file_reader.music_track_events = self.file_reader.music_track_events
        patch_file_reader.music_segments = self.file_reader.music_segments
        patch_file_reader.wwise_banks = {}
        patch_file_reader.wwise_streams = {}
        patch_file_reader.text_banks = {}
        
        for key, value in self.file_reader.wwise_streams.items():
            if value.content.modified:
                patch_file_reader.wwise_streams[key] = value
                
        for key, value in self.file_reader.wwise_banks.items():
            if value.modified:
                patch_file_reader.wwise_banks[key] = value
                
        for key, value in self.file_reader.text_banks.items():
            for string_id in value.string_ids:
                if self.file_reader.string_entries[value.language][string_id].modified:
                    patch_file_reader.text_banks[key] = value
                    break
     
        patch_file_reader.rebuild_headers()
        patch_file_reader.to_file(folder)

    def load_wems(self, wems: list[str], set_duration=True): 
        """
        @exception
        AssertionError
        """
        if len(wems) <= 0:
            return

        for wem in wems:
            basename = os.path.basename(wem)
            splits: list[str] = basename.split("_", 1)

            guard = True
            try:
                match splits:
                    case [prefix, name] if int(prefix) < 10000:
                        basename = name
            except (TypeError, ValueError) as err:
                logger.warning("Failed to convert the incoming prefix number."
                              f" Reason: {err}.")
            if not guard:
                continue

            guard = True
            file_id = -1
            try:
                file_id: int = self.get_number_prefix(basename)
            except (TypeError, ValueError) as err:
                guard = False
                logger.warning(f"Failed to get number prefix from {basename}. "
                               f"Reason: {err}")
            if not guard:
                continue

            audio: str | None = self.get_audio_by_id(file_id)
            if audio == None:
                continue

            with open(wem, 'rb') as f:
                audio.set_data(f.read())

            if not set_duration:
                continue

            guard = True
            process: subprocess.CompletedProcess[bytes] | None = None 
            try:
                process = subprocess.run([VGMSTREAM, "-m", wem], capture_output=True)
                process.check_returncode()
            except subprocess.CalledProcessError as err:
                logger.warning(f"Failed to print the metadata information of the"
                               " WEM file {wem}. Reason: {err}.")
            if not guard:
                continue

            if process == None:
                raise AssertionError()

            for line in process.stdout.decode("utf-8").split("\n"):
                if "sample rate" in line:
                    sample_rate = float(line[13:line.index("Hz")-1])
                if "stream total samples" in line:
                    total_samples = int(line[22:line.index("(")-1])
            len_ms = total_samples * 1000 / sample_rate
            if audio.get_track_info() is not None:
                audio.get_track_info().set_data(play_at=0, begin_trim_offset=0, end_trim_offset=0, source_duration=len_ms)
            # find music segment for Audio Source
            stop = False
            for segment in self.file_reader.music_segments.values():
                for track_id in segment.tracks:
                    track = segment.soundbank.hierarchy.entries[track_id]
                    for source in track.sources:
                        if source.source_id == audio.get_short_id():
                            segment.set_data(duration=len_ms, entry_marker=0, exit_marker=len_ms)
                            stop = True
                            break
                    if stop:
                        break
                if stop:
                    break
        
    def create_external_sources_list(self, sources: list[str]):
        root = etree.Element("ExternalSourcesList", attrib={
            "SchemaVersion": "1",
            "Root": __file__
        })
        file = etree.ElementTree(root)
        for source in sources:
            etree.SubElement(root, "Source", attrib={
                "Path": source,
                "Conversion": DEFAULT_CONVERSION_SETTING,
                "Destination": os.path.basename(source)
            })
        file.write(os.path.join(TMP, "external_sources.wsources"))
        
        return os.path.join(TMP, "external_sources.wsources")
        
        
    def load_wavs(self, wavs: list[str]):
        """
        @exception
        - CalledProcessError
        - NotImplementedError
        """
        if len(wavs) < 0:
            return

        source_list = self.create_external_sources_list(wavs)
        
        if SYSTEM in ["Windows", "Darwin"]:
            subprocess.run([
                WWISE_CLI,
                "migrate",
                DEFAULT_WWISE_PROJECT,
                "--quiet",
            ]).check_returncode()
        else:
            raise NotImplementedError("This operating system does not support "
                                      "this operation.")
        
        convert_dest = os.path.join(TMP, SYSTEM)
        if SYSTEM == "Darwin":
                subprocess.run([
                    WWISE_CLI,
                    "convert-external-source",
                    DEFAULT_WWISE_PROJECT,
                    "--platform", "Windows",
                    "--source-file",
                    source_list,
                    "--output",
                    TMP,
                ]).check_returncode()
        elif SYSTEM == "Windows":
            subprocess.run([
                WWISE_CLI,
                "convert-external-source",
                DEFAULT_WWISE_PROJECT,
                "--platform", "Windows",
                "--source-file",
                source_list,
                "--output",
                TMP,
            ]).check_returncode()
        else:
            raise NotImplementedError("This operating system does not support "
                                      "this operation.")

        wems = [os.path.join(convert_dest, x) for x in os.listdir(convert_dest)]
        
        self.load_wems(wems)
        
        for wem in wems:
            try:
                os.remove(wem)
            except OSError as err:
                logger.warning("Failed to remove temporary converted WEM file"
                              f" {wem}. Reason: {err}.")
                
        try:
            os.remove(source_list)
        except OSError as err:
            logger.warning("Failed to remove temporary conversion listing."
                          f"Reason: {err}.")
