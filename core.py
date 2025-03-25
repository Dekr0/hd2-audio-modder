from uuid import uuid4
import aiofiles
import asyncio
import functools
import numpy
import os
import pyaudio
import subprocess
import shutil
import struct
import wave
import copy
import random
import posixpath as xpath

from concurrent.futures import ProcessPoolExecutor, Future, as_completed
from typing import Callable, Coroutine, Literal, Union

import backend.mediautil as mediautil

from const import *
from env import *
from xlocale import *
from util import *
from wwise_hierarchy import *

from log import logger


# pre-computed data
UNK4DATA = bytes.fromhex(
    "CE09F5F400000000"
    "0C729F9E8872B8BD"
    "00A06B0200000000"
    "0079510000000000"
    "0000000000000000"
    "0000000000000000"
    "0000000000000000"
)
WWISE_STREAM_PREFIX = bytes.fromhex("D82F767800000000")
WWISE_BANK_PREFIX = bytes.fromhex("D82F7678")


class AudioSource:

    def __init__(self):
        self.data: bytearray | Literal[b""] = b""
        self.size: int = 0
        self.resource_id: int = 0
        self.short_id: int = 0
        self.modified: bool = False
        self.data_old: bytearray | Literal[b""] = b""
        self.parents: set[HircEntry | WwiseStream] = set()
        self.stream_type: int = 0
        
    def set_data(self, data: bytearray, notify_subscribers: bool = True, set_modified: bool = True):
        if not self.modified and set_modified:
            self.data_old = self.data
        self.data = data
        self.size = len(self.data)
        if notify_subscribers:
            for item in self.parents:
                if not self.modified:
                    item.raise_modified()
        if set_modified:
            self.modified = True
            
    def get_id(self) -> int:
        if self.stream_type == BANK:
            return self.get_short_id()
        else:
            return self.get_resource_id()
            
    def is_modified(self) -> bool:
        return self.modified

    def get_data(self) -> bytearray:
        return bytearray() if self.data == b"" else self.data 
        
    def get_resource_id(self) -> int:
        return self.resource_id
        
    def get_short_id(self) -> int:
        return self.short_id
        
    def revert_modifications(self, notify_subscribers: bool = True):
        if self.modified:
            self.modified = False
            if self.data_old != b"":
                self.data = self.data_old
                self.data_old = b""
            self.size = len(self.data)
            if notify_subscribers:
                for item in self.parents:
                    item.lower_modified()
                

class TocHeader:

    def __init__(self):
        self.file_id = self.type_id = self.toc_data_offset = self.stream_file_offset = self.gpu_resource_offset = 0
        self.unknown1 = self.unknown2 = self.toc_data_size = self.stream_size = self.gpu_resource_size = 0
        self.unknown3 = 16
        self.unknown4 = 64
        self.entry_index = 0
        
    def from_memory_stream(self, stream: MemoryStream):
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
        
    def get_data(self) -> bytes:
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
        self.data: str = ""
        
    def from_memory_stream(self, stream: MemoryStream):
        self.offset = stream.tell()
        self.tag = stream.uint32_read()
        self.data_size = stream.uint32_read()
        self.data = stream.read(self.data_size).decode('utf-8')
        
    def get_data(self) -> bytes:
        return (self.tag.to_bytes(4, byteorder='little')
                + self.data_size.to_bytes(4, byteorder='little')
                + self.data.encode('utf-8'))
                

class DidxEntry:
    def __init__(self):
        self.id = self.offset = self.size = 0
        
    @classmethod
    def from_bytes(cls, bytes: bytes | bytearray):
        e = DidxEntry()
        e.id, e.offset, e.size = struct.unpack("<III", bytes)
        return e
        
    def get_data(self) -> bytes:
        return struct.pack("<III", self.id, self.offset, self.size)
        

class MediaIndex:

    def __init__(self):
        self.entries = {}
        self.data = {}
        
    def load(self, didxChunk: bytes | bytearray, dataChunk: bytes | bytearray):
        for n in range(int(len(didxChunk)/12)):
            entry = DidxEntry.from_bytes(didxChunk[12*n : 12*(n+1)])
            self.entries[entry.id] = entry
            self.data[entry.id] = dataChunk[entry.offset:entry.offset+entry.size]
        
    def get_data(self) -> bytes:
        arr = [x.get_data() for x in self.entries.values()]
        data_arr = self.data.values()
        return b"".join(arr) + b"".join(data_arr)
                         

class BankParser:
    
    def __init__(self):
        self.chunks = {}
        
    def load(self, bank_data: bytes | bytearray):
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
            
    def GetChunk(self, chunk_tag: str) -> bytearray:
        try:
            return self.chunks[chunk_tag]
        except:
            return bytearray()


class WwiseBank:
    
    def __init__(self):
        self.bank_header: bytes = b""
        self.bank_misc_data: bytes = b""
        self.modified: bool = False
        self.dep: WwiseDep | None = None
        self.modified_count: int = 0
        self.hierarchy: WwiseHierarchy | None = None
        self.content: list[AudioSource] = []
        self.file_id: int = 0
        
    def import_hierarchy(self, new_hierarchy: WwiseHierarchy):
        if self.hierarchy == None:
            raise RuntimeError(
                "No wwise hierarchy is assigned to this instance of "
                "WwiseHierarchy"
            )
        self.hierarchy.import_hierarchy(new_hierarchy)
        
    def add_content(self, content: AudioSource):
        self.content.append(content)
        
    def remove_content(self, content: AudioSource):
        try:
            self.content.remove(content)
        except:
            pass
            
    def get_content(self) -> list[AudioSource]:
        return self.content
        
    def raise_modified(self):
        self.modified = True
        self.modified_count += 1
        
    def lower_modified(self):
        if self.modified:
            self.modified_count -= 1
            if self.modified_count == 0:
                self.modified = False
        
    def get_name(self) -> str:
        if self.dep == None:
            raise AssertionError(
                "No WwiseDep instance is attached to this instance of WwiseBank"
            )

        return self.dep.data
        
    def get_id(self) -> int:
        try:
            return self.file_id
        except:
            return 0
            
    def generate(self, audio_sources) -> bytearray:
        if self.hierarchy == None:
            raise AssertionError(
                f"No WwiseHierarchy is attach to WwiseBank {self.file_id}"
            )

        data = bytearray()
        data += self.bank_header
        offset = 0
        
        #regenerate soundbank from the hierarchy information
        
        didx_array = []
        data_array = []
        
        added_sources = set()

        entries: list[Sound | MusicTrack] = list(self.hierarchy.get_sounds().values())
        entries = list(self.hierarchy.get_music_tracks().values())
        for entry in entries:
            for source in entry.sources:
                if source.plugin_id == VORBIS:
                    try:
                        audio = audio_sources[source.source_id]
                    except KeyError as _:
                        continue
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
        return data
        

class WwiseStream:

    def __init__(self):
        self.audio_source: AudioSource | None = None
        self.modified: bool = False
        self.file_id: int = 0
        
    def set_source(self, audio_source: AudioSource):
        if self.audio_source != None:
            self.audio_source.parents.remove(self)
        self.audio_source = audio_source
        audio_source.parents.add(self)
        
    def raise_modified(self):
        self.modified = True
        
    def lower_modified(self):
        self.modified = False
        
    def get_id(self) -> int:
        try:
            return self.file_id
        except:
            return 0
            
    def get_data(self) -> bytearray | bytes:
        if self.audio_source == None:
            raise AssertionError(
                f"No audio source is attached to WwiseStream {self.file_id}"
            )
        return self.audio_source.get_data()


class StringEntry:

    def __init__(self):
        self.text = ""
        self.text_old = ""
        self.string_id = 0
        self.modified = False
        self.parent: TextBank | None = None
        
    def get_id(self) -> int:
        return self.string_id
        
    def get_text(self) -> str:
        return self.text
        
    def set_text(self, text: str):
        if not self.modified:
            self.text_old = self.text
            if self.parent != None:
                self.parent.raise_modified()
        self.modified = True
        self.text = text
        
    def revert_modifications(self):
        if self.modified:
            self.text = self.text_old
            self.modified = False
            if self.parent != None:
                self.parent.lower_modified()
        
class TextBank:
    
    def __init__(self):
        self.file_id = 0
        self.entries = {}
        self.language = 0
        self.modified = False
        self.modified_count = 0
     
    def set_data(self, data: bytearray):
        self.entries.clear()
        num_entries = int.from_bytes(data[8:12], byteorder='little')
        self.language = int.from_bytes(data[12:16], byteorder='little')
        id_section_start = 16
        offset_section_start = id_section_start + 4 * num_entries
        data_section_start = offset_section_start + 4 * num_entries
        ids = data[id_section_start:offset_section_start]
        offsets = data[offset_section_start:data_section_start]
        for n in range(num_entries):
            entry = StringEntry()
            entry.parent = self
            string_id = int.from_bytes(ids[4*n:+4*(n+1)], byteorder="little")
            string_offset = int.from_bytes(offsets[4*n:4*(n+1)], byteorder="little")
            entry.string_id = string_id
            stopIndex = string_offset + 1
            while data[stopIndex] != 0:
                stopIndex += 1
            entry.text = data[string_offset:stopIndex].decode('utf-8')
            self.entries[string_id] = entry
            
    def revert_modifications(self, entry_id: int = 0):
        if entry_id:
            self.entries[entry_id].revert_modifications()
        else:
            for entry in self.entries.values():
                entry.revert_modifications()
            
    def update(self):
        pass
        
    def get_language(self) -> int:
        return self.language
        
    def is_modified(self) -> bool:
        return self.modified

    def import_text(self, text_bank: "TextBank"):
        for new_string_entry in text_bank.entries.values():
            try:
                old_string_entry = self.entries[new_string_entry.string_id]
            except:
                continue
            if (old_string_entry.modified and new_string_entry.get_text() != old_string_entry.text_old
                or (not old_string_entry.modified and new_string_entry.get_text() != old_string_entry.get_text())
            ):
                old_string_entry.set_text(new_string_entry.get_text())
        
    def generate(self) -> bytearray:
        stream = MemoryStream()
        stream.write(b'\xae\xf3\x85\x3e\x01\x00\x00\x00')
        stream.write(len(self.entries).to_bytes(4, byteorder="little"))
        stream.write(self.language.to_bytes(4, byteorder="little"))
        offset = 16 + 8*len(self.entries)
        for entry in self.entries.values():
            stream.write(entry.get_id().to_bytes(4, byteorder="little"))
        for entry in self.entries.values():
            stream.write(offset.to_bytes(4, byteorder="little"))
            initial_position = stream.tell()
            stream.seek(offset)
            text_bytes = entry.text.encode('utf-8') + b'\x00'
            stream.write(text_bytes)
            offset += len(text_bytes)
            stream.seek(initial_position)
        return stream.data
        
    def get_id(self) -> int:
        return self.file_id
            
    def raise_modified(self):
        self.modified_count+=1
        self.modified = True
        
    def lower_modified(self):
        if self.modified:
            self.modified_count-=1
            if self.modified_count == 0:
                self.modified = False

class GameArchive:
    
    def __init__(self):
        self.magic: int = -1
        self.name: str = ""
        self.num_files: int = -1
        self.num_types: int = -1
        self.path: str = ""
        self.unk4Data: bytes | bytearray = b""
        self.unknown: int = -1
        self.wwise_streams: dict[int, WwiseStream] = {}
        self.wwise_banks: dict[int, WwiseBank] = {}
        self.audio_sources: dict[int, AudioSource] = {}
        self.hierarchy_entries: dict[int, HircEntry] = {}
        self.text_banks = {}
   
    @classmethod
    def from_file(cls, path: str) -> 'GameArchive': 
        archive = GameArchive()
        archive.name = os.path.basename(path)
        archive.path = path
        toc_file = MemoryStream()
        with open(path, 'r+b') as f:
            toc_file = MemoryStream(f.read())

        stream_file = MemoryStream()
        if os.path.isfile(path+".stream"):
            with open(path+".stream", 'r+b') as f:
                stream_file = MemoryStream(f.read())
        archive.load(toc_file, stream_file)
        return archive
        
    def get_wwise_streams(self) -> dict[int, WwiseStream]:
        return self.wwise_streams
        
    def get_wwise_banks(self) -> dict[int, WwiseBank]:
        return self.wwise_banks
        
    def get_audio_sources(self) -> dict[int, AudioSource]:
        return self.audio_sources
        
    def get_text_banks(self) -> dict[int, TextBank]:
        return self.text_banks

    def get_hierarchy_entries(self) -> dict[int, HircEntry]:
        return self.hierarchy_entries

    def write_type_header(self, toc_file: MemoryStream, entry_type: int, num_entries: int):
        if num_entries > 0:
            toc_file.write(struct.pack("<QQQII", 0, entry_type, num_entries, 16, 64))
        
    def to_file(self, path: str):
        toc_file = MemoryStream()
        stream_file = MemoryStream()
        self.num_files = len(self.wwise_streams) + 2*len(self.wwise_banks) + len(self.text_banks)
        self.num_types = (1 if self.wwise_streams else 0) + (1 if self.text_banks else 0) + (2 if self.wwise_banks else 0)
        
        # write header
        toc_file.write(struct.pack("<IIII56s", self.magic, self.num_types, self.num_files, self.unknown, self.unk4Data))
        
        self.write_type_header(toc_file, WWISE_STREAM, len(self.wwise_streams))
        self.write_type_header(toc_file, WWISE_BANK, len(self.wwise_banks))
        self.write_type_header(toc_file, WWISE_DEP, len(self.wwise_banks))
        self.write_type_header(toc_file, TEXT_BANK, len(self.text_banks))
        
        toc_data_offset = toc_file.tell() + 80 * self.num_files + 8
        stream_file_offset = 0
        
        # generate data and toc entries
        toc_entries = []
        toc_data = []
        stream_data = []
        entry_index = 0
        
        for stream in self.wwise_streams.values():
            s_data = pad_to_16_byte_align(stream.get_data())
            t_data = WWISE_STREAM_PREFIX + struct.pack("<Q", len(stream.get_data()))
            toc_entry = TocHeader()
            toc_entry.file_id = stream.get_id()
            toc_entry.type_id = WWISE_STREAM
            toc_entry.toc_data_offset = toc_data_offset
            toc_entry.stream_file_offset = stream_file_offset
            toc_entry.toc_data_size = 0x0C
            toc_entry.stream_size = len(stream.get_data())
            toc_entry.entry_index = entry_index
            stream_data.append(s_data)
            toc_data.append(t_data)
            toc_entries.append(toc_entry)
            entry_index += 1
            stream_file_offset += len(s_data)
            toc_data_offset += 16
            
        for bank in self.wwise_banks.values():
            bank_data = bank.generate(self.audio_sources)
            toc_entry = TocHeader()
            toc_entry.file_id = bank.get_id()
            toc_entry.type_id = WWISE_BANK
            toc_entry.toc_data_offset = toc_data_offset
            toc_entry.stream_file_offset = stream_file_offset
            toc_entry.toc_data_size = len(bank_data) + 16
            toc_entry.entry_index = entry_index
            toc_entries.append(toc_entry)
            bank_data = b"".join([
                WWISE_BANK_PREFIX,
                len(bank_data).to_bytes(4, byteorder="little"),
                bank.get_id().to_bytes(8, byteorder="little"),
                pad_to_16_byte_align(bank_data)
            ])
            toc_data.append(bank_data)
            
            toc_data_offset += len(bank_data)
            entry_index += 1
            
        for text_bank in self.text_banks.values():
            text_data = text_bank.generate()
            toc_entry = TocHeader()
            toc_entry.file_id = text_bank.get_id()
            toc_entry.type_id = TEXT_BANK
            toc_entry.toc_data_offset = toc_data_offset
            toc_entry.stream_file_offset = stream_file_offset
            toc_entry.toc_data_size = len(text_data)
            toc_entry.entry_index = entry_index
            text_data = pad_to_16_byte_align(text_data)
            
            toc_entries.append(toc_entry)
            toc_data.append(text_data)
            
            toc_data_offset += len(text_data)
            entry_index += 1
        
        for bank in self.wwise_banks.values():
            if bank.dep == None:
                raise AssertionError(
                    f"WwiseBank {bank.file_id} does not has a WwsieDep."
                )

            dep_data = bank.dep.get_data()
            toc_entry = TocHeader()
            toc_entry.file_id = bank.get_id()
            toc_entry.type_id = WWISE_DEP
            toc_entry.toc_data_offset = toc_data_offset
            toc_entry.stream_file_offset = stream_file_offset
            toc_entry.toc_data_size = len(dep_data)
            toc_entry.entry_index = entry_index
            toc_entries.append(toc_entry)
            dep_data = pad_to_16_byte_align(dep_data)
            toc_data.append(dep_data)
            
            toc_data_offset += len(dep_data)
            entry_index += 1
            
        toc_file.write(b"".join([entry.get_data() for entry in toc_entries]))
        toc_file.advance(8)
        toc_file.write(b"".join(toc_data))
        stream_file.write(b"".join(stream_data))

        with open(os.path.join(path, self.name), 'w+b') as f:
            f.write(toc_file.data)
            
        if len(stream_file.data) > 0:
            with open(os.path.join(path, self.name+".stream"), 'w+b') as f:
                f.write(stream_file.data)

    def load(self, toc_file: MemoryStream, stream_file: MemoryStream):
        self.wwise_streams.clear()
        self.wwise_banks.clear()
        self.audio_sources.clear()
        self.text_banks.clear()
        self.hierarchy_entries.clear()

        media_index = MediaIndex()
        
        self.magic      = toc_file.uint32_read()
        if self.magic != 0xF0000011: return False

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
            if toc_header.type_id == WWISE_STREAM:
                audio = AudioSource()
                audio.stream_type = STREAM
                wwise_stream = WwiseStream()
                wwise_stream.file_id = toc_header.file_id
                toc_file.seek(toc_header.toc_data_offset)
                stream_file.seek(toc_header.stream_file_offset)
                audio.set_data(stream_file.read(toc_header.stream_size), notify_subscribers=False, set_modified=False)
                audio.resource_id = toc_header.file_id
                wwise_stream.set_source(audio)
                self.wwise_streams[wwise_stream.get_id()] = wwise_stream
            elif toc_header.type_id == WWISE_BANK:
                wwise_bank = WwiseBank()
                toc_file.seek(toc_header.toc_data_offset)
                toc_file.advance(16)
                wwise_bank.file_id = toc_header.file_id
                bank_parser = BankParser()
                bank_parser.load(toc_file.read(toc_header.toc_data_size-16))
                wwise_bank.bank_header = "BKHD".encode('utf-8') + len(bank_parser.chunks["BKHD"]).to_bytes(4, byteorder="little") + bank_parser.chunks["BKHD"]
                
                hirc = WwiseHierarchy(soundbank=wwise_bank)
                try:
                    hirc.load(bank_parser.chunks['HIRC'])
                except KeyError:
                    pass

                replacements: dict[int, HircEntry] = {}
                for in_hirc_id, in_hirc_entry in hirc.entries.items():
                    if in_hirc_id not in self.hierarchy_entries:
                        self.hierarchy_entries[in_hirc_id] = in_hirc_entry
                        continue
                    existing_hirc_entry = self.hierarchy_entries[in_hirc_id]
                    if isinstance(in_hirc_entry, ActorMixer):
                        if not isinstance(existing_hirc_entry, ActorMixer): 
                            raise AssertionError(
                                f"Both hierarchy entry with id {in_hirc_id} but one "
                                f"has type of {in_hirc_entry.__class__.__name__} and "
                                f"one has type of {existing_hirc_entry.__class__.__name__}."
                            )
                        for child in in_hirc_entry.children.children:
                            if child in existing_hirc_entry.children.children:
                                continue
                            existing_hirc_entry.children.children.append(child)
                            existing_hirc_entry.children.numChildren += 1
                        existing_hirc_entry.update_size()
                    existing_hirc_entry.soundbanks.append(wwise_bank)
                    replacements[in_hirc_id] = existing_hirc_entry

                for in_hirc_id, in_hirc_entry in replacements.items():
                    hirc.remove_categorized_entry(hirc.entries[in_hirc_id])
                    hirc.categorized_entry(in_hirc_entry)

                hirc.entries.update(replacements)

                wwise_bank.hierarchy = hirc
                #Add all bank sources to the source list
                if "DIDX" in bank_parser.chunks.keys():
                    media_index.load(bank_parser.chunks["DIDX"], bank_parser.chunks["DATA"])
                
                wwise_bank.bank_misc_data = b''
                for chunk in bank_parser.chunks.keys():
                    if chunk not in ["BKHD", "DATA", "DIDX", "HIRC"]:
                        wwise_bank.bank_misc_data = wwise_bank.bank_misc_data + chunk.encode('utf-8') + len(bank_parser.chunks[chunk]).to_bytes(4, byteorder='little') + bank_parser.chunks[chunk]
                        
                self.wwise_banks[wwise_bank.get_id()] = wwise_bank
            elif toc_header.type_id == WWISE_DEP: #wwise dep
                dep = WwiseDep()
                toc_file.seek(toc_header.toc_data_offset)
                dep.from_memory_stream(toc_file)
                try:
                    self.wwise_banks[toc_header.file_id].dep = dep
                except KeyError:
                    pass
            elif toc_header.type_id == TEXT_BANK: #string_entry
                toc_file.seek(toc_header.toc_data_offset)
                data = toc_file.read(toc_header.toc_data_size)
                text_bank = TextBank()
                text_bank.file_id = toc_header.file_id
                text_bank.set_data(data)
                self.text_banks[text_bank.get_id()] = text_bank
        
        # Create all AudioSource objects

        self._create_all_audio_source_objects(media_index)

        # Construct list of audio sources in each bank
        self._book_keep_audio_sources_per_bank()

    def _create_all_audio_source_objects(self, media_index: MediaIndex):
       for bank in self.wwise_banks.values():
           self._create_all_audio_source_objects_from_bank(bank, media_index)

    def _create_all_audio_source_objects_from_bank(
        self, bank: WwiseBank, media_index: MediaIndex
    ):
        if bank.hierarchy == None:
            raise AssertionError(f"WwiseBank {bank.file_id} has no WwiseHierarchy")
        if bank.dep == None:
            raise AssertionError(f"WwiseBank {bank.file_id} has no WwiseDep")

        hirc = bank.hierarchy
        dep = bank.dep

        entries_with_audio_sources: list[Sound | MusicTrack] = list(hirc.get_sounds().values())
        entries_with_audio_sources += list(hirc.get_music_tracks().values()) 
        for entry_with_audio_source in entries_with_audio_sources:
            for source_struct in entry_with_audio_source.sources:
                audio_source = self._create_audio_source(
                    source_struct, media_index, hirc, dep
                )
                if audio_source == None:
                    continue
                self.audio_sources[audio_source.short_id] = audio_source


    def _create_audio_source(
        self, 
        source: BankSourceStruct,
        media_index: MediaIndex,
        hirc: WwiseHierarchy,
        dep: WwiseDep
    ) -> AudioSource | None:
        """
        Question: for REV_AUDIO, it uses media index ID. Should we use source 
        ID to check for duplication again?
        """
        source_id = source.source_id
        if source_id in self.audio_sources:
            logger.info(
                f"Audio source {source_id} already registered. Skipping audio "
                f"source {source_id}..."
            )
            return None

        plugin_id = source.plugin_id
        if plugin_id not in [VORBIS, REV_AUDIO]:
            logger.info(
               f"Audio source {source_id} has plugin ID {plugin_id}. Audio "
                "tool currently can only unpack audio source with plugin_id of "
               f"{VORBIS} or {REV_AUDIO}"
            )
            return None

        stream_type = source.stream_type
        if stream_type not in [BANK, STREAM, PREFETCH_STREAM]:
            logger.warning(
                f"Audio source {source_id} has stream type: {stream_type}. Audio"
                 "tool currently can only unpack audio source with stream type  "
                f"{BANK}, {STREAM}, or {PREFETCH_STREAM}."
            )
            return None

        if stream_type == BANK and plugin_id == REV_AUDIO:
            if hirc.has_entry(source_id):
                logger.error(
                    f"There's no custom FX hierarchy entry associated with audio"
                    f" source {source_id}!"
                )
                return None
            return self._create_audio_source_type_rev_audio(
                hirc.get_entry(source_id), media_index
            )
        if stream_type == BANK:
            if source_id not in media_index.data:
                logger.error(
                    "There is no media index data associated with audio source ID "
                   f"{source_id}"
                )
                return None
            return self._create_audio_source_type_bank(source, media_index)
        if stream_type in [STREAM, PREFETCH_STREAM]:
            return self._create_audio_source_type_stream(source, dep)

        raise AssertionError("Invalid code path!")
    
    @staticmethod
    def _create_audio_source_type_bank(
        source: BankSourceStruct, media_index: MediaIndex
    ) -> AudioSource:
        audio = AudioSource()
        audio.stream_type = BANK
        audio.short_id = source.source_id
        audio.set_data(
            media_index.data[source.source_id],
            set_modified=False,
            notify_subscribers=False
        )

        return audio

    def _create_audio_source_type_rev_audio(
        self, 
        custom_fx_entry: HircEntry,
        media_index: MediaIndex,
    ) -> AudioSource | None:
        # TODO: This should be parsed and organized in the parsing phase
        data = custom_fx_entry.get_data()
        plugin_param_size = int.from_bytes(data[13:17], byteorder="little")

        plugin_data_start = 19 + plugin_param_size
        plugin_data_end = 23 + plugin_param_size

        media_index_id = int.from_bytes(
            data[plugin_data_start:plugin_data_end], byteorder="little"
        )
        if media_index_id not in media_index.data:
            logger.error(
                f"There is no media index data associated with {media_index_id}"
            )
            return None

        audio = AudioSource()
        audio.stream_type = BANK
        audio.short_id = media_index_id
        audio.set_data(
            media_index.data[media_index_id],
            set_modified=False,
            notify_subscribers=False
        )

        return audio

    def _create_audio_source_type_stream(
        self,
        source: BankSourceStruct,
        dep: WwiseDep
    ) -> AudioSource | None:
        stream_resource_id = murmur64_hash(
            (os.path.dirname(dep.data) + "/" + str(source.source_id)).encode('utf-8')
        )
        if stream_resource_id not in self.wwise_streams:
            logger.error(
                "There is no WwiseStream associated with stream resource ID"
               f"{stream_resource_id}"
            )
            return None

        audio = self.wwise_streams[stream_resource_id].audio_source
        if audio == None:
            logger.error(
                f"WwiseStream {stream_resource_id} has no audio source."
            )
            return None
        audio.short_id = source.source_id
        return audio

    def _book_keep_audio_sources_per_bank(self):
        for bank in self.wwise_banks.values():
            if bank.hierarchy == None:
                raise AssertionError(
                    f"WwiseBank {bank.file_id} has no WwiseHierarchy"
                )

            bank_audio_sources = bank.get_content()
            music_tracks = bank.hierarchy.get_music_tracks().values()
            for music_track in music_tracks:
                for info in music_track.track_info:
                    source_id = info.source_id
                    if source_id == 0:
                        continue
                    if source_id not in self.audio_sources:
                        logger.error(
                             "There is no audio source associated with audio "
                            f"source ID {source_id}."
                        )
                        continue
                    """
                    TODO: determine whether if adding TrackInfoStruct into 
                    audio source
                    """
                for source in music_track.sources:
                    if source.plugin_id != VORBIS:
                        continue
                    source_id = source.source_id
                    if source_id not in self.audio_sources:
                        logger.error(
                            f"Audio source {source_id} is not tracked and registered "
                            f"in the list of all audio sources!",
                        )
                        continue
                    self.audio_sources[source_id].parents.add(music_track)
                    if self.audio_sources[source_id] not in bank_audio_sources:
                        bank.add_content(self.audio_sources[source_id])

            sounds = bank.hierarchy.get_sounds().values()
            for sound in sounds:
                assert_equal(
                    "Sound object should only one single audio source but Sound "
                   f" {sound.hierarchy_id} does not.",
                    1,
                    len(sound.sources),
                )

                source = sound.sources[0]
                source_id = source.source_id
                if source_id not in self.audio_sources:
                    logger.error(
                        f"Audio source {source_id} is not tracked and registered "
                        f"in the list of all audio sources!",
                    )
                    continue
                
                if source.plugin_id != VORBIS:
                    continue
                audio_source = self.audio_sources[source_id]
                audio_source.parents.add(sound)
                if audio_source not in bank_audio_sources:
                    bank.add_content(audio_source)

        
class SoundHandler:
    
    handler_instance: Union['SoundHandler', None] = None
    
    def __init__(self):
        self.audio_process = None
        self.wave_object = None
        self.audio_id = -1
        self.audio = pyaudio.PyAudio()
        
    @classmethod
    def create_instance(cls):
        cls.handler_instance = SoundHandler()
        
    @classmethod
    def get_instance(cls) -> 'SoundHandler':
        if cls.handler_instance == None:
            cls.handler_instance = SoundHandler()
        return cls.handler_instance
        
    def kill_sound(self):
        if self.audio_process is not None:
            if self.callback is not None:
                try:
                    self.callback()
                except:
                    pass
                self.callback = None
            self.audio_process.close()
            self.wave_file.close()
            try:
                os.remove(self.audio_file)
            except:
                pass
            self.audio_process = None
    
    def play_audio(self, sound_id: int, sound_data: bytearray, callback: Callable | None = None):
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
        
        def read_stream(
            _, 
            frame_count, 
            __, 
            ___
        ):
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
        
    def downmix_to_stereo(self, data: bytearray, channels: int, channel_width: int, frame_count: int) -> bytes:
        if channel_width == 2:
            arr = numpy.frombuffer(data, dtype=numpy.int16)
            stereo_array = numpy.zeros(shape=(frame_count, 2), dtype=numpy.int16)
        elif channel_width == 1:
            arr = numpy.frombuffer(data, dtype=numpy.int8)
            stereo_array = numpy.zeros(shape=(frame_count, 2), dtype=numpy.int8)
        elif channel_width == 4:
            arr = numpy.frombuffer(data, dtype=numpy.int32)
            stereo_array = numpy.zeros(shape=(frame_count, 2), dtype=numpy.int32)
        arr = arr.reshape((frame_count, channels)) # type: ignore
        
        if channels == 4:
            for index, frame in enumerate(arr):
                stereo_array[index][0] = int(0.42265 * frame[0] + 0.366025 * frame[2] + 0.211325 * frame[3]) # type: ignore
                stereo_array[index][1] = int(0.42265 * frame[1] + 0.366025 * frame[3] + 0.211325 * frame[2]) # type: ignore
        
            return stereo_array.tobytes() # type: ignore
                
        if channels == 6:
            for index, frame in enumerate(arr):
                stereo_array[index][0] = int(0.374107*frame[1] + 0.529067*frame[0] + 0.458186*frame[3] + 0.264534*frame[4] + 0.374107*frame[5]) # type: ignore
                stereo_array[index][1] = int(0.374107*frame[1] + 0.529067*frame[2] + 0.458186*frame[4] + 0.264534*frame[3] + 0.374107*frame[5]) # type: ignore
        
            return stereo_array.tobytes() # type: ignore
        
        #if not 4 or 6 channel, default to taking the L and R channels rather than mixing
        for index, frame in enumerate(arr):
            stereo_array[index][0] = frame[0] # type: ignore
            stereo_array[index][1] = frame[1] # type: ignore
        
        return stereo_array.tobytes() # type: ignore
        

class Mod:

    def __init__(self, name: str, db: SQLiteDatabase):
        self.db = db
        self.wwise_streams: dict[int, WwiseStream] = {}
        self.stream_count: dict[int, int] = {}
        self.wwise_banks: dict[int, WwiseBank] = {}
        self.bank_count: dict[int, int] = {}
        self.audio_sources: dict[int, AudioSource] = {}
        self.audio_count: dict[int, int] = {}
        self.text_banks: dict[int, TextBank] = {}
        self.text_count = {}
        self.hierarchy_entries: dict[int, HircEntry] = {}
        self.hierarchy_count: dict[int, int] = {}
        self.game_archives: dict[str, GameArchive] = {}
        self.name: str = name
        
    def revert_all(self):
        for audio in self.audio_sources.values():
            audio.revert_modifications()
        for bank in self.wwise_banks.values():
            if bank.hierarchy == None:
                raise AssertionError(
                    f"WwiseBank {bank.file_id} does not have a WwiseHierarchy"
                )
            bank.hierarchy.revert_modifications()
        for bank in self.text_banks.values():
            bank.revert_modifications()
        
    def revert_audio(self, file_id: int):
        audio = self.get_audio_source(file_id)
        audio.revert_modifications()
 
    def add_new_hierarchy_entry(self, soundbank_id: int, entry: HircEntry):
        bank = self.get_wwise_bank(soundbank_id)
        if bank.hierarchy == None:
            raise AssertionError(f"WwiseBank {soundbank_id} with no WwiseHierarchy")
        if bank in entry.soundbanks:
            raise Exception(f"Entry {entry.hierarchy_id} already exists in soundbank {soundbank_id}!")

        hirc_id = entry.hierarchy_id
        if hirc_id in self.hierarchy_entries:
            entry = self.hierarchy_entries[entry.hierarchy_id]
            self.hierarchy_count[hirc_id] = self.hierarchy_count[hirc_id] + 1
        else:
            self.hierarchy_count[hirc_id] = 1
            self.hierarchy_entries[hirc_id] = entry
        bank.hierarchy.add_entry(entry)
        
    def remove_hierarchy_entry(self, soundbank_id: int, entry_id: int):
        if entry_id not in self.hierarchy_entries:
            raise AssertionError(f"Hierarchy entry {entry_id} not found")
        bank = self.get_wwise_bank(soundbank_id)
        if bank.hierarchy == None:
            raise AssertionError(f"WwiseBank {soundbank_id} with no WwiseHierarchy")
        entry = self.get_hierarchy_entry(entry_id)
        bank.hierarchy.remove_entry(entry)
        if self.hierarchy_count[entry_id] > 1:
            self.hierarchy_count[entry_id] = self.hierarchy_count[entry_id] - 1
        else:
            del self.hierarchy_count[entry_id]
            del self.hierarchy_entries[entry_id]
       
    def revert_hierarchy_entry(self, soundbank_id: int, entry_id: int):
        self.get_hierarchy_entry(entry_id).revert_modifications()
        
    def revert_string_entry(self, textbank_id: int, entry_id: int):
        self.get_string_entry(textbank_id, entry_id).revert_modifications()
        
    def revert_text_bank(self, textbank_id: int):
        self.get_text_bank(textbank_id).revert_modifications()
        
    def revert_wwise_hierarchy(self, soundbank_id: int): 
        bank = self.get_wwise_bank(soundbank_id)
        if bank.hierarchy == None:
            raise AssertionError(f"WwiseBank {soundbank_id} with no WwiseHierarchy")
        bank.hierarchy.revert_modifications()
        
    def revert_wwise_bank(self, soundbank_id: int):
        self.revert_wwise_hierarchy(soundbank_id)
        for audio in self.get_wwise_bank(soundbank_id).get_content():
            audio.revert_modifications()

    def reroute_sound(self, sound: Sound, audio_data: bytearray):
        """
        @exception
        - AssertionError
        - NotImplementedError
        - KeyError
        """
        if len(sound.sources) != 1:
            raise AssertionError(
                "There are more than one audio source in a Sound object."
            )

        source_struct = sound.sources[0]
        if source_struct.plugin_id != VORBIS:
            raise NotImplementedError(
                "Sound rerouting only work with VORBIS type of audio source."
               f" The Sound object {sound.hierarchy_id} has plugin id"
               f" {source_struct.plugin_id}."
            )
        
        short_id = ak_media_id(self.db)
        if short_id in self.audio_sources:
            raise KeyError(
                f"Audio source short ID {short_id} already exists. Please retry "
                f"with this method call."
            )

        # Create new AudioSource
        audio_source = AudioSource()
        audio_source.data = audio_data
        audio_source.size = len(audio_data)
        audio_source.short_id = short_id
        audio_source.data_old = audio_data
        audio_source.parents.add(sound)
        audio_source.stream_type = BANK

        # Update BankSourceStruct
        source_struct.source_id = short_id

        # Mark sound is modified
        sound.raise_modified()

        # Update WwiseBank audio source list
        if len(sound.soundbanks) <= 0:
            raise AssertionError(
                f"Sound object {sound.hierarchy_id} sound bank has no associated"
                 " sound bank."
            )

        bank = sound.soundbanks[0]
        if not isinstance(bank, WwiseBank): 
            raise AssertionError(
                f"Sound object {sound.hierarchy_id} sound bank field is not "
                 "an instance of sound bank."
            )
        bank.content.append(audio_source)

        # Update Mod audio source list
        self.audio_sources[short_id] = audio_source
        self.audio_count[short_id] = 1
        
    def dump_as_wem(self, file_id: int, output_path: str = ""):
        """
        @exception
        - ValueError
            - Empty output file name
        """
        if output_path == "":
            raise ValueError("Invalid output filename!")
        with open(output_path, "wb") as f:
            f.write(self.get_audio_source(file_id).get_data())
        
    def dump_as_wav(self, file_id: int, output_file: str = "", muted: bool = False):
        """
        @exception
        - ValueError
            - Empty output file name
        """
        if output_file == "":
            raise ValueError("Invalid output filename!")

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
            )
            return

        with open(f"{save_path}.wem", 'wb') as f:
            f.write(self.get_audio_source(file_id).get_data())

        process = subprocess.run(
            [VGMSTREAM, "-o", f"{save_path}.wav", f"{save_path}.wem"], 
            stdout=subprocess.DEVNULL
        )
        
        if process.returncode != 0:
            logger.error(f"Encountered error when converting {file_id}.wem into .wav format")

        os.remove(f"{save_path}.wem")
        
    def dump_multiple_as_wem(self, file_ids: list[int], output_folder: str = ""):
        """
        @exception
        - OSError
            - output_folder does not exist
        """
        if not os.path.exists(output_folder) or not os.path.isdir(output_folder):
            raise OSError(f"Invalid output folder '{output_folder}'")

        for file_id in file_ids:
            audio = self.get_audio_source(file_id)
            if audio is not None:
                save_path = os.path.join(output_folder, f"{audio.get_id()}")
                with open(save_path+".wem", "wb") as f:
                    f.write(audio.get_data())
        
    def dump_multiple_as_wav(self, file_ids: list[int], output_folder: str = "", muted: bool = False,
                             with_seq: bool = False):
        """
        @exception
        - OSError
            - output_folder does not exist
        """
        if not os.path.exists(output_folder) or not os.path.isdir(output_folder):
            raise OSError(f"Invalid output folder '{output_folder}'")

        for i, file_id in enumerate(file_ids, start=0):
            audio: AudioSource = self.get_audio_source(int(file_id))
            basename = str(audio.get_id()) if not with_seq else f"{i:02d}_{audio.get_id()}"
            save_path = os.path.join(output_folder, basename)
            if muted:
                subprocess.run([
                    FFMPEG, 
                    "-f", "lavfi", 
                    "-i", "anullsrc=r=48000:cl=stereo",
                    "-t", "1", # TO-DO, this should match up with actual duration
                    "-c:a", "pcm_s16le",
                    f"{save_path}.wav"],
                    stdout=subprocess.DEVNULL
                )
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

    def dump_all_as_wem(self, output_folder: str = ""):
        """
        @exception
        - OSError
            - output_folder does not exist
        """
        if not os.path.exists(output_folder) or not os.path.isdir(output_folder):
            raise OSError(f"Invalid output folder '{output_folder}'")

        for bank in self.get_wwise_banks().values():
            if bank.dep == None:
                raise AssertionError(
                    f"Wwise bank {bank.get_id()} does not have a Wwise "
                     "dependency."
                )
            subfolder = os.path.join(output_folder, os.path.basename(bank.dep.data.replace('\x00', '')))
            if not os.path.exists(subfolder):
                os.mkdir(subfolder)
            for audio in bank.get_content():
                save_path = os.path.join(subfolder, f"{audio.get_id()}")
                with open(save_path+".wem", "wb") as f:
                    f.write(audio.get_data())
    
    def dump_all_as_wav(self, output_folder: str = ""):
        """
        @exception
        - OSError
            - output_folder does not exist
        """
        if not os.path.exists(output_folder) or not os.path.isdir(output_folder):
            raise OSError(f"Invalid output folder '{output_folder}'")

        for bank in self.get_wwise_banks().values():
            if bank.dep == None:
                raise AssertionError(
                    f"Wwise bank {bank.get_id()} does not have a Wwise "
                     "dependency."
                )
            subfolder = os.path.join(output_folder, os.path.basename(bank.dep.data.replace('\x00', '')))
            if not os.path.exists(subfolder):
                os.mkdir(subfolder)
            for audio in bank.get_content():
                save_path = os.path.join(subfolder, f"{audio.get_id()}")
                with open(save_path+".wem", "wb") as f:
                    f.write(audio.get_data())
                process = subprocess.run([VGMSTREAM, "-o", f"{save_path}.wav", f"{save_path}.wem"], stdout=subprocess.DEVNULL)
                if process.returncode != 0:
                    logger.error(f"Encountered error when converting {os.path.basename(save_path)}.wem to .wav")
                os.remove(f"{save_path}.wem")

    def save_archive_file(self, game_archive: GameArchive, output_folder: str = ""):
        """
        @exception
        - OSError
            - output_folder does not exist
        """
        if not os.path.exists(output_folder) or not os.path.isdir(output_folder):
            raise OSError(f"Invalid output folder '{output_folder}'")
        
        game_archive.to_file(output_folder)
        
    def save(self, output_folder: str = "", combined = True):
        """
        @exception
        - OSError
            - output_folder does not exist
        """
        if not os.path.exists(output_folder) or not os.path.isdir(output_folder):
            raise OSError(f"Invalid output folder '{output_folder}'")
        
        if combined:
            combined_game_archive = GameArchive()
            combined_game_archive.name = "9ba626afa44a3aa3.patch_0"
            combined_game_archive.magic = 0xF0000011
            combined_game_archive.num_types = 0
            combined_game_archive.num_files = 0
            combined_game_archive.unknown = 0
            combined_game_archive.unk4Data = bytes.fromhex("CE09F5F4000000000C729F9E8872B8BD00A06B02000000000079510000000000000000000000000000000000000000000000000000000000")
            combined_game_archive.audio_sources = self.audio_sources
            combined_game_archive.wwise_banks = self.wwise_banks
            combined_game_archive.wwise_streams = self.wwise_streams
            combined_game_archive.text_banks = self.text_banks
            combined_game_archive.to_file(output_folder)
        else:
            for game_archive in self.get_game_archives().values():
                self.save_archive_file(game_archive, output_folder)
            
    def get_audio_source(self, audio_id: int) -> AudioSource:
        """
        @return
        - Obtain audio source given by a Wwise audio short ID or a table of 
        content file ID

        @exception
        - KeyError - No audio source that matches up a Wwise audio short ID or 
        a table of content file ID
        """
        if audio_id in self.audio_sources:
            return self.audio_sources[audio_id]

        for audio_source in self.audio_sources.values():
            if audio_source.resource_id == audio_id:
                return audio_source

        raise KeyError(f"Failed to find audio source with ID {audio_id}")

                
    def get_string_entry(self, textbank_id: int, entry_id: int) -> StringEntry:
        """
        @exception
        - KeyError
        """
        try:
            return self.get_text_bank(textbank_id).entries[entry_id]
        except KeyError:
            raise KeyError(f"Cannot find string with id {entry_id} in textbank with id {textbank_id}")
            
    def get_string_entries(self, textbank_id: int) -> dict[int, StringEntry]:
        return self.get_text_bank(textbank_id).entries

    def get_hierarchy_entry(self, hierarchy_id: int) -> HircEntry:
        """
        @exception
        - KeyError
        """
        return self.get_hierarchy_entries()[hierarchy_id]
            
    def get_hierarchy_entries(self, soundbank_id: int = 0):
        """
        @exception
        - KeyError (Bubble up)
        - AssertionError
        """
        if soundbank_id == 0:
            return self.hierarchy_entries
        bank = self.get_wwise_bank(soundbank_id)
        if bank.hierarchy == None:
            raise AssertionError(f"WwiseBank {soundbank_id} with no WwiseHierarchy")

        return bank.hierarchy.get_entries()
            
    def get_wwise_bank(self, soundbank_id: int) -> WwiseBank:
        """
        @exception
        - KeyError
            - Trivial
        """
        try:
            return self.wwise_banks[soundbank_id]
        except KeyError:
            raise KeyError(f"Cannot find soundbank with id {soundbank_id}")
        
    def set_wwise_bank(self, soundbank_id: int, bank: WwiseBank):
        self.wwise_banks[soundbank_id] = bank
        
    def get_wwise_stream(self, stream_id: int) -> WwiseStream:
        """
        @exception
        - KeyError
            - Trivial
        """
        try:
            return self.wwise_streams[stream_id]
        except KeyError:
            raise KeyError(f"Cannot find wwise stream with id {stream_id}")
        
    def set_wwise_stream(self, stream_id: int, stream: WwiseStream):
        self.wwise_streams[stream_id] = stream
    
    def get_text_bank(self, textbank_id: int) -> TextBank:
        """
        @exception
        - KeyError
            - Trivial
        """
        try:
            return self.text_banks[textbank_id]
        except KeyError:
            raise KeyError(f"Cannot find text bank with id {textbank_id}")
    
    def get_game_archives(self) -> dict[str, GameArchive]:
        return self.game_archives
        
    def get_game_archive(self, archive_name: str) -> GameArchive:
        try:
            return self.get_game_archives()[archive_name]
        except KeyError:
            raise Exception(f"Cannot find game archive {archive_name}")
        
    def get_wwise_streams(self) -> dict[int, WwiseStream]:
        return self.wwise_streams
        
    def get_wwise_banks(self) -> dict[int, WwiseBank]:
        return self.wwise_banks
        
    def get_audio_sources(self) -> dict[int, AudioSource]:
        return self.audio_sources
        
    def get_text_banks(self) -> dict[int, TextBank]:
        return self.text_banks
        
    async def load_archive_file(self, archive_file: str = ""):
        """
        @exception
        - OSError
            - archive file does not exist
        """
        if not archive_file or not os.path.exists(archive_file) or not os.path.isfile(archive_file):
            raise OSError("Invalid path!")

        if os.path.splitext(archive_file)[1] in (".stream", ".gpu_resources"):
            archive_file = os.path.splitext(archive_file)[0]
        new_archive = GameArchive.from_file(archive_file)
        
        key = new_archive.name
        if key in self.game_archives.keys():
            return False
        
        self.add_game_archive(new_archive)

        return True
        
    def import_wwise_hierarchy(self, soundbank_id: int, new_hierarchy: WwiseHierarchy):
        self.get_wwise_bank(soundbank_id).import_hierarchy(new_hierarchy)
        
    def generate_hierarchy_id(self, soundbank_id: int) -> int:
        hierarchy = self.get_wwise_bank(soundbank_id).hierarchy

        if hierarchy == None:
            raise AssertionError(f"WwiseBank {soundbank_id} without WwiseHierarchy")

        new_id = random.randint(0, 0xffffffff)

        while new_id in hierarchy.entries.keys():
            new_id = random.randint(0, 0xffffffff)
        return new_id
        
    def remove_game_archive(self, archive_name: str = ""):
        if archive_name not in self.game_archives.keys():
            raise AssertionError(f"Archive {archive_name} not in mod!")
            
        game_archive = self.game_archives[archive_name]
            
        for key in game_archive.wwise_banks.keys():
            if key not in self.wwise_banks:
                continue

            self.bank_count[key] -= 1
            if self.bank_count[key] > 0:
                continue

            removed_bank = game_archive.wwise_banks[key]
            hirc = removed_bank.hierarchy
            assert_not_none(
                f"WwiseBank {key} has no hierarchy",
                hirc,
            )
            for entry in hirc.entries.values(): # type: ignore
                entry.soundbanks.remove(removed_bank)

            for audio in self.wwise_banks[key].get_content():
                parents = [p for p in audio.parents]
                for parent in parents:
                    if isinstance(parent, HircEntry) and key in [b.get_id() for b in parent.soundbanks]:
                        audio.parents.remove(parent)
            del self.wwise_banks[key]
            del self.bank_count[key]
        for key, entry in game_archive.get_hierarchy_entries().items():
            self.hierarchy_count[key] -= 1
            if self.hierarchy_count[key] == 0:
                del self.hierarchy_count[key]
                del self.get_hierarchy_entries()[key]
        for key in game_archive.wwise_streams.keys():
            if key in self.get_wwise_streams().keys():
                self.stream_count[key] -= 1
                if self.stream_count[key] == 0:
                    stream = self.wwise_streams[key]

                    if stream.audio_source == None:
                        logger.warning(
                            f"Wwise stream {stream.get_id()} does not have an "
                             "audio source!"
                        )
                        continue
                    stream.audio_source.parents.remove(self.get_wwise_streams()[key])
                    del self.get_wwise_streams()[key]
                    del self.stream_count[key]
        for key in game_archive.text_banks.keys():
            if key in self.get_text_banks().keys():
                self.text_count[key] -= 1
                if self.text_count[key] == 0:
                    del self.get_text_banks()[key]
                    del self.text_count[key]
        for key in game_archive.audio_sources.keys():
            if key in self.get_audio_sources().keys():
                self.audio_count[key] -= 1
                if self.audio_count[key] == 0:
                    del self.get_audio_sources()[key]
                    del self.audio_count[key]
        
        try:
            del self.game_archives[archive_name]
        except:
            pass

    def add_game_archive(self, game_archive: GameArchive):
        """
        @exception
        - AssertionError
        """
        key = game_archive.name
        if key in self.game_archives.keys():
            return

        self.game_archives[key] = game_archive

        replacements: dict[int, HircEntry] = {}
        entries = game_archive.get_hierarchy_entries()
        for new_hirc_id, new_hirc_entry in entries.items():
            if new_hirc_id not in self.hierarchy_entries:
                self.hierarchy_count[new_hirc_id] = 1
                self.hierarchy_entries[new_hirc_id] = new_hirc_entry
                continue

            self.hierarchy_count[new_hirc_id] += 1
            existing_hirc_entry = self.hierarchy_entries[new_hirc_id]
            replacements[new_hirc_id] = existing_hirc_entry

            if isinstance(new_hirc_entry, ActorMixer):
                if not isinstance(existing_hirc_entry, ActorMixer): 
                    raise AssertionError(
                        f"Both hierarchy entry with id {new_hirc_id} but one "
                        f"has type of {new_hirc_entry.__class__.__name__} and "
                        f"one has type of {existing_hirc_entry.__class__.__name__}."
                    )

                for child in new_hirc_entry.children.children:
                    if child not in existing_hirc_entry.children.children:
                        existing_hirc_entry.children.children.append(child)
                        existing_hirc_entry.children.numChildren += 1
                existing_hirc_entry.update_size()

            for bank in new_hirc_entry.soundbanks:
                assert_not_none(
                    f"WwiseBank {bank.file_id} has no WwiseHierarchy",
                    bank.hierarchy
                )
                bank.hierarchy.entries[new_hirc_id] = existing_hirc_entry
                if bank not in existing_hirc_entry.soundbanks:
                    existing_hirc_entry.soundbanks.append(bank)

        # update in each soundbank hierarchy's type lists, each soundbank hierarchy, and then GameArchive
        for new_bank in game_archive.wwise_banks.values():
            assert_not_none(
                f"WwiseBank {new_bank.file_id} has no hierarchy",
                new_bank.hierarchy
            )

            hirc: WwiseHierarchy = new_bank.hierarchy # type: ignore
            for new_hirc_id, new_hirc_entry in replacements.items():
                if new_hirc_id not in hirc.entries:
                    continue
                hirc.remove_categorized_entry(hirc.entries[new_hirc_id])
                hirc.categorized_entry(new_hirc_entry)
                hirc.entries[new_hirc_id] = new_hirc_entry

        game_archive.get_hierarchy_entries().update(replacements)
        
        for key in game_archive.wwise_banks.keys():
            if key in self.get_wwise_banks().keys():
                self.bank_count[key] += 1
                for audio in game_archive.wwise_banks[key].get_content():
                    parents = [p for p in audio.parents]
                    for parent in parents:
                        if isinstance(parent, HircEntry) and key in [b.get_id() for b in parent.soundbanks]:
                            audio.parents.remove(parent)
                            try:
                                new_parent = self.get_hierarchy_entry(parent.get_id())
                            except:
                                continue # add missing hierarchy entry?
                            audio.parents.add(new_parent)
                            if audio.modified:
                                new_parent.raise_modified()
                game_archive.wwise_banks[key] = self.get_wwise_banks()[key]
            else:
                self.bank_count[key] = 1
                self.get_wwise_banks()[key] = game_archive.wwise_banks[key]
        for key in game_archive.wwise_streams.keys():
            if key in self.get_wwise_streams().keys():
                self.stream_count[key] += 1
                audio = game_archive.wwise_streams[key].audio_source

                if audio == None:
                    raise AssertionError(
                        f"WwiseStream {key} has no audio source"
                    )

                audio.parents.remove(game_archive.wwise_streams[key])
                audio.parents.add(self.get_wwise_streams()[key])
                if audio.modified:
                    self.get_wwise_streams()[key].raise_modified()
                game_archive.wwise_streams[key] = self.get_wwise_streams()[key]
            else:
                self.stream_count[key] = 1
                self.get_wwise_streams()[key] = game_archive.wwise_streams[key]
        for key in game_archive.text_banks.keys():
            if key in self.get_text_banks().keys():
                self.text_count[key] += 1
                game_archive.text_banks[key] = self.get_text_banks()[key]
            else:
                self.text_count[key] = 1
                self.get_text_banks()[key] = game_archive.text_banks[key]
        for key in game_archive.audio_sources.keys():
            if key in self.get_audio_sources().keys():
                self.audio_count[key] += 1
                for parent in game_archive.audio_sources[key].parents:
                    self.get_audio_sources()[key].parents.add(parent)
                game_archive.audio_sources[key] = self.get_audio_sources()[key]
            else:
                self.audio_count[key] = 1
                self.get_audio_sources()[key] = game_archive.audio_sources[key]
            
    def import_patch(self, patch_file: str = ""):
        """
        @exception
        - OSError
        - AssertionError
        """
        if os.path.splitext(patch_file)[1] in (".stream", ".gpu_resources"):
            patch_file = os.path.splitext(patch_file)[0]

        if not os.path.exists(patch_file): 
            raise OSError(f"Patch file {patch_file} does not exists.")

        if not os.path.isfile(patch_file):
            raise OSError(f"Patch file {patch_file} is not a regular file")

        patch_game_archive = GameArchive.from_file(patch_file)
                                
        for new_audio in patch_game_archive.get_audio_sources().values():
            short_id = new_audio.short_id
            if short_id not in self.audio_sources:
                continue

            old_audio = self.audio_sources[short_id]
            new_audio_data = new_audio.get_data()
            if new_audio_data != old_audio.get_data():
                continue

            old_audio.set_data(new_audio_data)
            sample_rate = int.from_bytes(new_audio_data[24:28], byteorder="little")
            num_samples = int.from_bytes(new_audio_data[44:48], byteorder="little")
            len_ms = num_samples * 1000 / sample_rate
            for item in old_audio.parents:
                if not isinstance(item, MusicTrack):
                    continue
                self.set_music_track_duration(item, old_audio, len_ms)

        for bank in patch_game_archive.get_wwise_banks().values():
            bank_id = bank.get_id()
            assert_not_none(f"WwiseBank {bank_id} has no WwiseDep", bank.dep)
            assert_not_none(f"WwiseBank {bank_id} has no WwiseHierarchy", bank.hierarchy)

            if bank_id not in self.wwise_banks: 
                logger.error(
                    f"Patch {patch_file} has a sound bank {bank_id} but the "
                     "current archive does not has this sound bank."
                )
                continue

            try:
                self.wwise_banks[bank_id].import_hierarchy(bank.hierarchy) # type: ignore
            except BaseException as err:
                logger.error(
                    f"Unable import hierarchy information for {bank.dep.data}" # type: ignore
                    f": {err}"
                ) 

        for text_bank in patch_game_archive.get_text_banks().values():
            bank_id = text_bank.file_id
            if bank_id not in self.text_banks:
                logger.error(
                    f"Patch {patch_file} has a text bank {bank_id} but the "
                     "current archive does not has this text bank."
                )
                continue

            try:
                self.text_banks[bank_id].import_text(text_bank)
            except BaseException as err:
                logger.warning(f"Unable import text data from text bank {bank_id}")

    def write_patch(self, output_folder: str = ""):
        """
        @exception
        - OSError
            - output folder path does not exists
        """
        if not os.path.exists(output_folder) or not os.path.isdir(output_folder):
            raise OSError(f"Invalid output folder '{output_folder}'")
        patch_game_archive = GameArchive()
        patch_game_archive.name = "9ba626afa44a3aa3.patch_0"
        patch_game_archive.magic = 0xF0000011
        patch_game_archive.num_types = 0
        patch_game_archive.num_files = 0
        patch_game_archive.unknown = 0
        patch_game_archive.unk4Data = UNK4DATA
        patch_game_archive.audio_sources = self.audio_sources
        patch_game_archive.wwise_banks = {}
        patch_game_archive.wwise_streams = {}
        patch_game_archive.text_banks = {}
            
        for key, value in self.get_wwise_streams().items():
            if value.modified:
                patch_game_archive.wwise_streams[key] = value
                
        for key, value in self.get_wwise_banks().items():
            if value.modified:
                patch_game_archive.wwise_banks[key] = value
                
        for key, value in self.get_text_banks().items():
            if value.modified:
                patch_game_archive.text_banks[key] = value
 
        patch_game_archive.to_file(output_folder)

    async def import_wems(
        self,
        wems: dict[str, list[int]] | None = None,
        set_duration=True
    ) -> list[tuple[str, str]]: 
        """
        - OSError
        - ValueError
            - wems is None
        """

        if wems == None:
            raise ValueError("wems is None.")

        if len(wems) <= 0:
            raise ValueError("No WEM file is provided.")

        error_files: list[tuple[str, str]] = []

        for file_path, targets in wems.items():
            if not os.path.exists(file_path) or not os.path.isfile(file_path):
                error_files.append((
                    file_path, "Wem file {file_path} does not exists."
                ))

            try:
                async with aiofiles.open(file_path, "rb") as f:
                    audio_data = await f.read()
                    if audio_data[20:22] != b"\xFF\xFF":
                        error_files.append((
                            file_path, 
                            f"Wem file {file_path} has incorrect audio format."
                             "Please set it to VORBIS in Wwise IDE."
                        ))
                        continue
            except BaseException as err:
                error_files.append((
                    file_path,
                    f"Failed to read audio data of wem file {file_path}: {err}"
                ))
                continue

            have_length = True
            len_ms = -1

            if set_duration:
                try:
                    len_ms = await mediautil.get_wem_length(file_path)
                except (
                    subprocess.CalledProcessError,
                    OSError,
                    RuntimeError,
                ) as err:
                    error_files.append((
                        file_path,
                        f"Failed to obtain length for wem file {file_path}: {err}"
                    ))
                    have_length = False

            for target in targets:
                try:
                    audio = self.get_audio_source(target)
                    audio.set_data(bytearray(audio_data))
                except KeyError as err:
                    error_files.append((
                        file_path,
                       f"Target audio source {target} does not exists in the "
                        "registered audio sources."
                    ))
                    continue
                if not have_length:
                    continue
                for item in audio.parents:
                    if not isinstance(item, MusicTrack):
                        continue
                    self.set_music_track_duration(item, audio, len_ms)

        return error_files
        
    async def import_wavs(
        self,
        wavs: dict[str, list[int]] | None = None,
        wwise_project: str = DEFAULT_WWISE_PROJECT,
        conversion_setting: str = DEFAULT_CONVERSION_SETTING
    ) -> list[tuple[str, str]]:
        """
        @return list[tuple[str, str]]
            a list of files that are failed to import, if there's any
        @exception
        - ValueError
            - wavs is None
        - CalledProcessError
            - subprocess.run
        - NotImplementedError
            - Platform is on Linux
        """
        if wavs == None:
            raise ValueError("wavs is None.")

        if len(wavs) <= 0:
            raise ValueError("No WAV file is provided.")
            
        if SYSTEM not in WWISE_SUPPORTED_SYSTEMS:
            raise NotImplementedError(
                "The current operating system does not support this feature."
            )

        workspace = xpath.join(TMP, f"{fnv_30(uuid4().bytes)}")
        os.mkdir(xpath.join(workspace))

        convert_dest = await mediautil.convert_wav_to_wem(
            list(wavs.keys()),
            workspace,
            wwise_project,
            conversion_setting
        )

        if convert_dest == None:
            raise AssertionError(
                "Bypassing validation: none zero wave files should return a "
                "destination"
            ) 

        wems = {
            os.path.join(
                convert_dest, 
                f"{os.path.splitext(os.path.basename(filepath))[0]}.wem"
            ) : targets for filepath, targets in wavs.items()
        }

        error_files = await self.import_wems(wems)

        shutil.rmtree(workspace)

        return error_files
            
    async def import_files(
        self,
        file_dict: dict[str, list[int]],
        wwise_project: str = DEFAULT_WWISE_PROJECT,
        conversion_setting: str = DEFAULT_CONVERSION_SETTING
    ):
        patches: list[str] = []
        wems: dict[str, list[int]] = {}
        wavs: dict[str, list[int]] = {}
        others: dict[str, list[int]] = {}
        for file, targets in file_dict.items():
            file = fileutil.to_posix(file)
            _, ext = os.path.splitext(file)
            match ext:
                case ".patch":
                    patches.append(file)
                case ".wav":
                    wavs[file] = targets
                case ".wem":
                    wems[file] = targets
                case _:
                    if ext not in SUPPORTED_AUDIO_TYPES:
                        logger.warning(f"File {file} is not a supported format.")
                        continue
                    others[file] = targets

        error_files: list[tuple[str, str]] = []

        workspace = xpath.join(TMP, f"{fnv_30(uuid4().bytes)}")

        results = await mediautil.to_wave_batch(others.keys(), workspace)
        for result in results:
            if result[2] != 0:
                error_files.append((
                    result[0],
                    f"Failed to convert {result[0]} to wave format. Return code"
                    f": {result[2]}"
                ))
                continue
            wavs[result[1]] = others[result[0]]

        for patch in patches:
            self.import_patch(patch_file=patch)

        import_tasks: list[Coroutine[Any, Any, list[tuple[str, str]]]] = []
        if len(wems) > 0:
            import_tasks.append(self.import_wems(wems))
        if len(wavs) > 0:
            import_tasks.append(self.import_wavs(
                wavs,
                wwise_project,
                conversion_setting
            ))

        for gather in await asyncio.gather(*import_tasks):
            error_files += gather

        with ProcessPoolExecutor() as p:
            fs: list[Future[None]] = [
                p.submit(functools.partial(os.remove, result[1])) 
                for result in results
            ]
            for f in as_completed(fs, 60.0):
                # as_completed yield done Future
                err = f.exception()
                if err != None:
                    logger.error(err)

        return error_files

    @staticmethod
    def set_music_track_duration(
        item: MusicTrack, audio: AudioSource, len_ms: float
    ):
        if len_ms < 0:
            raise AssertionError("len_ms is less than 0.")

        if item.parent == None:
            raise AssertionError(
                f"Music track {item.hierarchy_id} does not have a parent!"
            )

        item.parent.set_data(duration=len_ms, entry_marker=0, exit_marker=len_ms)
        tracks = copy.deepcopy(item.track_info)

        for t in tracks:
            if t.source_id != audio.get_short_id():
                continue

            t.begin_trim_offset = 0
            t.end_trim_offset = 0
            t.source_duration = len_ms
            t.play_at = 0
            break

        item.set_data(track_info=tracks)

        
class ModHandler:
    
    handler_instance: Union['ModHandler', None] = None
    
    def __init__(self, db: SQLiteDatabase):
        self.db = db
        self.mods: dict[str, Mod] = {}
        
    @classmethod
    def create_instance(cls, db: SQLiteDatabase):
        cls.handler_instance = ModHandler(db)
        
    @classmethod
    def get_instance(cls, db: SQLiteDatabase) -> 'ModHandler':
        if cls.handler_instance == None:
            cls.handler_instance = ModHandler(db)
        return cls.handler_instance

    def add_new_mod(self, mod_name: str, mod: Mod):
        """
        @exception
        - KeyError
        """
        if mod_name in self.mods:
            raise KeyError(f"Mod name '{mod_name}' already exists!")
        self.mods[mod_name] = mod

    def create_new_mod(self, mod_name: str):
        """
        @exception
        - KeyError
            - Mod name conflict
        """
        if mod_name in self.mods.keys():
            raise KeyError(f"Mod name '{mod_name}' already exists!")
        new_mod = Mod(mod_name, self.db)
        self.mods[mod_name] = new_mod
        self.active_mod = new_mod
        return new_mod
        
    def get_active_mod(self) -> Mod:
        """
        @exception
        - LookupError
            - Query an empty blank state of ModHandler
        """
        if not self.active_mod:
            raise LookupError("No active mod!")
        return self.active_mod
        
    def set_active_mod(self, mod_name: str):
        """
        @exception
        - KeyError 
            - no matching mod name
        """
        try:
            self.active_mod = self.mods[mod_name]
        except:
            raise KeyError(f"No matching mod found for '{mod_name}'")
            
    def get_mod_names(self) -> list[str]:
        return list(self.mods.keys())

    def has_mod(self, mod_name: str) -> bool:
        return mod_name in self.mods
        
    def delete_mod(self, mod: str | Mod):
        """
        @exception
        - KeyError 
            - no matching mod name
        """

        if isinstance(mod, Mod):
            mod_name = mod.name
        else:
            mod_name = mod
        try:
            mod_to_delete = self.mods[mod_name]
        except:
            raise KeyError(f"No matching mod found for '{mod}'")
        if mod_to_delete is self.active_mod:
            if len(self.mods) > 1:
                for mod in self.mods.values():
                    if mod is not self.active_mod:
                        self.active_mod = mod
                        break
            else:
                self.active_mod = None
        del self.mods[mod_name]
