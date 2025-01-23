import json
import numpy
import os
import platform
import pyaudio
import subprocess
import struct
import tkinter
import shutil
import wave
import sys
import pathlib
import copy
import locale
import random
import xml.etree.ElementTree as etree

from functools import partial
from functools import cmp_to_key
from math import ceil
from tkinterdnd2 import *
from tkinter import *
from tkinter import ttk
from tkinter import filedialog
from tkinter.messagebox import askokcancel
from tkinter.messagebox import showwarning
from tkinter.messagebox import showerror
from tkinter.messagebox import askyesnocancel
from tkinter.filedialog import askopenfilename
from typing import Any, Literal, Callable
from typing_extensions import Self
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

import config as cfg
import db
import log
import fileutil
import util
from util import *
from wwise_hierarchy import *

from log import logger

# constants
MUSIC_TRACK = 11
SOUND = 2
BANK = 0
MUSIC_SEGMENT = 0x0A
PREFETCH_STREAM = 1
STREAM = 2
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
VORBIS = 0x00040001
REV_AUDIO = 0x01A01052
WWISE_BANK = 6006249203084351385
WWISE_DEP = 12624162998411505776
WWISE_STREAM = 5785811756662211598
TEXT_BANK = 979299457696010195
SUPPORTED_AUDIO_TYPES = [".wem", ".wav", ".mp3", ".m4a", ".ogg"]
WWISE_SUPPORTED_SYSTEMS = ["Windows", "Darwin"]

# constants (set once on runtime)
DIR = os.path.dirname(__file__)
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    DIR = os.path.dirname(sys.argv[0])
FFMPEG = ""
VGMSTREAM = ""
GAME_FILE_LOCATION = ""
WWISE_CLI = ""
WWISE_VERSION = ""
DEFAULT_WWISE_PROJECT = os.path.join(DIR, "AudioConversionTemplate/AudioConversionTemplate.wproj") 
DEFAULT_CONVERSION_SETTING = "Vorbis Quality High"
SYSTEM = ""
CACHE = os.path.join(DIR, ".cache")

# global variables
language = 0
num_segments = 0
    
class WorkspaceEventHandler(FileSystemEventHandler):

    # TO-DO: Change get_item_by_path to return all matches, not just the first

    def __init__(self, workspace):
        self.workspace = workspace

    def on_created(self, event: FileSystemEvent) -> None:
        src_ext = os.path.splitext(event.src_path)[1]
        if ".patch" in src_ext or src_ext in SUPPORTED_AUDIO_TYPES or event.is_directory:
            parent = pathlib.Path(event.src_path).parents[0]
            parent_items = self.get_items_by_path(parent)
            new_item_name = os.path.basename(event.src_path)
            for parent_item in parent_items:
                idx = 0
                for i in self.workspace.get_children(parent_item):
                    if event.is_directory and self.workspace.item(i, option="tags")[0] != "dir":
                        break
                    if not event.is_directory and self.workspace.item(i, option="tags")[0] == "dir":
                        idx+=1
                        continue
                    name = self.workspace.item(i)["text"]
                    if name.lower() < new_item_name.lower():
                        idx+=1
                    else:
                        break
                self.workspace.insert(parent_item, idx,
                                                   text=new_item_name,
                                                   values=[event.src_path],
                                                   tags="dir" if event.is_directory else "file")
        
    def on_deleted(self, event: FileSystemEvent) -> None:
        matching_items = self.get_items_by_path(event.src_path)
        for item in matching_items:
            self.workspace.delete(item)
        
    # moved/renamed WITHIN SAME DIRECTORY
    # changing directories will fire a created and deleted event
    def on_moved(self, event: FileSystemEvent) -> None:
        matching_items = self.get_items_by_path(event.src_path)
        new_item_name = os.path.basename(event.dest_path)
        new_parent_items = self.get_items_by_path(pathlib.Path(event.dest_path).parents[0])
        dest_ext = os.path.splitext(event.dest_path)[1]
        for item in matching_items:
            self.workspace.delete(item)
        if ".patch" in dest_ext or dest_ext in SUPPORTED_AUDIO_TYPES or event.is_directory: 
            idx = 0
            for i in self.workspace.get_children(new_parent_items[0]):
                if event.is_directory and self.workspace.item(i, option="tags")[0] != "dir":
                    break
                if not event.is_directory and self.workspace.item(i, option="tags")[0] == "dir":
                    idx+=1
                    continue
                name = self.workspace.item(i)["text"]
                if name.lower() < new_item_name.lower():
                    idx+=1
                else:
                    break
            for parent_item in new_parent_items:
                self.workspace.insert(parent_item, idx,
                                               text=new_item_name,
                                               values=[event.dest_path],
                                               tags="dir" if event.is_directory else "file")
        
    def get_items_by_path(self, path):
        items = []
        path = pathlib.Path(path)
        for item in self.workspace.get_children():
            child_path = pathlib.Path(self.workspace.item(item, option="values")[0])
            if child_path in path.parents:
                i = self.get_item_by_path_recursion(item, path)
                if i is not None:
                    items.append(i)
            elif str(child_path) == str(path):
                items.append(item)
        return items
                    
    def get_item_by_path_recursion(self, node, path):
        for item in self.workspace.get_children(node):
            child_path = pathlib.Path(self.workspace.item(item, option="values")[0])
            if child_path in path.parents:
                return self.get_item_by_path_recursion(item, path)
            elif str(child_path) == str(path):
                return item
        
class AudioSource:

    def __init__(self):
        self.data = b""
        self.size = 0
        self.resource_id = 0
        self.short_id = 0
        self.modified = False
        self.data_old = b""
        self.parents = set()
        self.stream_type = 0
        
    def set_data(self, data: bytes, notify_subscribers: bool = True, set_modified: bool = True):
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

    def get_data(self) -> bytes:
        return self.data
        
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
        self.data = ""
        
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
            return None

class WwiseBank:
    
    def __init__(self):
        self.bank_header = b""
        self.bank_misc_data = b""
        self.modified = False
        self.dep = None
        self.modified_count = 0
        self.hierarchy = None
        self.content = []
        self.file_id = 0
        
    def import_hierarchy(self, new_hierarchy: WwiseHierarchy):
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
        return self.dep.data
        
    def get_id(self) -> int:
        try:
            return self.file_id
        except:
            return 0
            
    def generate(self, audio_sources) -> bytearray:
        data = bytearray()
        data += self.bank_header
        offset = 0
        
        #regenerate soundbank from the hierarchy information
        
        didx_array = []
        data_array = []
        
        added_sources = set()
        
        for entry in self.hierarchy.get_type(SOUND) + self.hierarchy.get_type(MUSIC_TRACK):
            for source in entry.sources:
                if source.plugin_id == VORBIS:
                    try:
                        audio = audio_sources[source.source_id]
                    except KeyError as e:
                        print(e)
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
        self.audio_source = None
        self.modified = False
        self.file_id = 0
        
    def set_source(self, audio_source: AudioSource):
        try:
            self.audio_source.parents.remove(self)
        except:
            pass
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
            
    def get_data(self) -> bytes:
        return self.audio_source.get_data()

class StringEntry:

    def __init__(self):
        self.text = ""
        self.text_old = ""
        self.string_id = 0
        self.modified = False
        self.parent = None
        
    def get_id(self) -> int:
        return self.string_id
        
    def get_text(self) -> str:
        return self.text
        
    def set_text(self, text: str):
        if not self.modified:
            self.text_old = self.text
            self.parent.raise_modified()
        self.modified = True
        self.text = text
        
    def revert_modifications(self):
        if self.modified:
            self.text = self.text_old
            self.modified = False
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
        offset = 0
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
        self.wwise_streams = {}
        self.wwise_banks = {}
        self.audio_sources = {}
        self.text_banks = {}
    
    @classmethod
    def from_file(cls, path: str) -> Self:
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
            t_data = bytes.fromhex("D82F767800000000") + struct.pack("<Q", len(stream.get_data()))
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
            bank_data = b"".join([bytes.fromhex("D82F7678"), len(bank_data).to_bytes(4, byteorder="little"), bank.get_id().to_bytes(8, byteorder="little"), pad_to_16_byte_align(bank_data)])
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
            entry = None
            if toc_header.type_id == WWISE_STREAM:
                audio = AudioSource()
                audio.stream_type = STREAM
                entry = WwiseStream()
                entry.file_id = toc_header.file_id
                toc_file.seek(toc_header.toc_data_offset)
                stream_file.seek(toc_header.stream_file_offset)
                audio.set_data(stream_file.read(toc_header.stream_size), notify_subscribers=False, set_modified=False)
                audio.resource_id = toc_header.file_id
                entry.set_source(audio)
                self.wwise_streams[entry.get_id()] = entry
            elif toc_header.type_id == WWISE_BANK:
                entry = WwiseBank()
                toc_file.seek(toc_header.toc_data_offset)
                toc_file.advance(16)
                entry.file_id = toc_header.file_id
                bank = BankParser()
                bank.load(toc_file.read(toc_header.toc_data_size-16))
                entry.bank_header = "BKHD".encode('utf-8') + len(bank.chunks["BKHD"]).to_bytes(4, byteorder="little") + bank.chunks["BKHD"]
                
                hirc = WwiseHierarchy(soundbank=entry)
                try:
                    hirc.load(bank.chunks['HIRC'])
                except KeyError:
                    pass
                entry.hierarchy = hirc
                #Add all bank sources to the source list
                if "DIDX" in bank.chunks.keys():
                    media_index.load(bank.chunks["DIDX"], bank.chunks["DATA"])
                
                entry.bank_misc_data = b''
                for chunk in bank.chunks.keys():
                    if chunk not in ["BKHD", "DATA", "DIDX", "HIRC"]:
                        entry.bank_misc_data = entry.bank_misc_data + chunk.encode('utf-8') + len(bank.chunks[chunk]).to_bytes(4, byteorder='little') + bank.chunks[chunk]
                        
                self.wwise_banks[entry.get_id()] = entry
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
        for bank in self.wwise_banks.values():
            for entry in bank.hierarchy.get_entries():
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
                            audio = self.wwise_streams[stream_resource_id].audio_source
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
                        if source.plugin_id == VORBIS:
                            self.audio_sources[source.source_id].parents.add(entry)
                        if source.plugin_id == VORBIS and self.audio_sources[source.source_id] not in bank.get_content(): #may be missing streamed audio if the patch didn't change it
                            bank.add_content(self.audio_sources[source.source_id])
                    except:
                        continue
        
class SoundHandler:
    
    handler_instance = None
    
    def __init__(self):
        self.audio_process = None
        self.wave_object = None
        self.audio_id = -1
        self.audio = pyaudio.PyAudio()
        
    @classmethod
    def create_instance(cls):
        cls.handler_instance = SoundHandler()
        
    @classmethod
    def get_instance(cls) -> Self:
        if not cls.handler_instance:
            cls.create_instance()
        return cls.handler_instance
        
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
        
    def play_audio(self, sound_id: int, sound_data: bytearray, callback: Callable = None):
        if not os.path.exists(VGMSTREAM):
            return
        self.kill_sound()
        self.callback = callback
        if self.audio_id == sound_id:
            self.audio_id = -1
            return
        filename = f"temp{sound_id}"
        if not os.path.isfile(f"{filename}.wav"):
            with open(f'{os.path.join(CACHE, filename)}.wem', 'wb') as f:
                f.write(sound_data)
            process = subprocess.run([VGMSTREAM, "-o", f"{os.path.join(CACHE, filename)}.wav", f"{os.path.join(CACHE, filename)}.wem"], stdout=subprocess.DEVNULL)
            os.remove(f"{os.path.join(CACHE, filename)}.wem")
            if process.returncode != 0:
                logger.error(f"Encountered error when converting {sound_id}.wem for playback")
                self.callback = None
                return
            
        self.audio_id = sound_id
        self.wave_file = wave.open(f"{os.path.join(CACHE, filename)}.wav")
        self.audio_file = f"{os.path.join(CACHE, filename)}.wav"
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
        self.audio_file = f"{os.path.join(CACHE, filename)}.wav"
        
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
        
class Mod:

    def __init__(self, name):
        self.wwise_streams = {}
        self.stream_count = {}
        self.wwise_banks = {}
        self.bank_count = {}
        self.audio_sources = {}
        self.audio_count = {}
        self.text_banks = {}
        self.text_count = {}
        self.game_archives = {}
        self.name = name
        
    def revert_all(self):
        for audio in self.audio_sources.values():
            audio.revert_modifications()
        for bank in self.wwise_banks.values():
            bank.hierarchy.revert_modifications()
        for bank in self.text_banks.values():
            bank.revert_modifications()
        
    def revert_audio(self, file_id: int):
        audio = self.get_audio_source(file_id)
        audio.revert_modifications()
        
    def add_new_hierarchy_entry(self, soundbank_id: int, entry: HircEntry):
        self.get_wwise_bank(soundbank_id).hierarchy.add_entry(entry)
        
    def remove_hierarchy_entry(self, soundbank_id: int, entry_id: int):
        entry = self.get_hierarchy_entry(soundbank_id, entry_id)
        self.get_wwise_bank(soundbank_id).hierarchy.remove_entry(entry)
        
    def revert_hierarchy_entry(self, soundbank_id: int, entry_id: int):
        self.get_hierarchy_entry(soundbank_id, entry_id).revert_modifications()
        
    def revert_string_entry(self, textbank_id: int, entry_id: int):
        self.get_string_entry(textbank_id, entry_id).revert_modifications()
        
    def revert_text_bank(self, textbank_id: int):
        self.get_text_bank(textbank_id).revert_modifications()
        
    def revert_wwise_hierarchy(self, soundbank_id: int):
        self.get_wwise_bank(soundbank_id).hierarchy.revert_modifications()
        
    def revert_wwise_bank(self, soundbank_id: int):
        self.revert_wwise_hierarchy(soundbank_id)
        for audio in self.get_wwise_bank(soundbank_id).get_content():
            audio.revert_modifications()
        
    def dump_as_wem(self, file_id: int, output_file: str = ""):
        if not output_file:
            raise ValueError("Invalid output filename!")
        output_file.write(self.get_audio_source(file_id).get_data())
        
    def dump_as_wav(self, file_id: int, output_file: str = "", muted: bool = False):

        if not output_file:
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
        
        if not os.path.exists(output_folder) or not os.path.isdir(output_folder):
            raise ValueError(f"Invalid output folder '{output_folder}'")

        for file_id in file_ids:
            audio = self.get_audio_source(file_id)
            if audio is not None:
                save_path = os.path.join(folder, f"{audio.get_id()}")
                with open(save_path+".wem", "wb") as f:
                    f.write(audio.get_data())
        
    def dump_multiple_as_wav(self, file_ids: list[str], output_folder: str = "", muted: bool = False,
                             with_seq: bool = False):
        
        if not os.path.exists(output_folder) or not os.path.isdir(output_folder):
            raise ValueError(f"Invalid output folder '{output_folder}'")

        for i, file_id in enumerate(file_ids, start=0):
            audio: int | None = self.get_audio_source(int(file_id))
            if audio is None:
                continue
            basename = str(audio.get_id())
            if with_seq:
                basename = f"{i:02d}" + "_" + basename
            save_path = os.path.join(folder, basename)
            progress_window.set_text(
                "Dumping " + os.path.basename(save_path) + ".wem"
            )
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
        
        if not os.path.exists(output_folder) or not os.path.isdir(output_folder):
            raise ValueError(f"Invalid output folder '{output_folder}'")
        for bank in self.game_archive.wwise_banks.values():
            subfolder = os.path.join(folder, os.path.basename(bank.dep.data.replace('\x00', '')))
            if not os.path.exists(subfolder):
                os.mkdir(subfolder)
            for audio in bank.get_content():
                save_path = os.path.join(subfolder, f"{audio.get_id()}")
                with open(save_path+".wem", "wb") as f:
                    f.write(audio.get_data())
    
    def dump_all_as_wav(self, output_folder: str = ""):
        if not os.path.exists(output_folder) or not os.path.isdir(output_folder):
            raise ValueError(f"Invalid output folder '{output_folder}'")
        for bank in self.game_archive.wwise_banks.values():
            subfolder = os.path.join(folder, os.path.basename(bank.dep.data.replace('\x00', '')))
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

        if not os.path.exists(output_folder) or not os.path.isdir(output_folder):
            raise ValueError(f"Invalid output folder '{output_folder}'")
        
        game_archive.to_file(output_folder)
        
    def save(self, output_folder: str = "", combined = True):
        
        if not os.path.exists(output_folder) or not os.path.isdir(output_folder):
            raise ValueError(f"Invalid output folder '{output_folder}'")
        
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
        try:
            return self.audio_sources[audio_id] #short_id
        except KeyError:
            pass
        for source in self.audio_sources.values(): #resource_id
            if source.resource_id == audio_id:
                return source
        raise Exception(f"Cannot find audio source with id {audio_id}")
                
    def get_string_entry(self, textbank_id: int, entry_id: int) -> StringEntry:
        try:
            return self.get_text_bank(textbank_id).entries[entry_id]
        except KeyError:
            raise Exception(f"Cannot find string with id {entry_id} in textbank with id {textbank_id}")
            
    def get_string_entries(self, textbank_id: int) -> dict[int, StringEntry]:
        return self.get_text_bank(textbank_id).entries
                
    def get_hierarchy_entry(self, soundbank_id: int, hierarchy_id: int) -> HircEntry:
        try:
            return self.get_wwise_bank(soundbank_id).hierarchy.get_entry(hierarchy_id)
        except:
            raise Exception(f"Cannot find wwise hierarchy entry with id {hierarchy_id} in soundbank with id {soundbank_id}")
            
    def get_hierarchy_entries(self, soundbank_id: int) -> dict[int, HircEntry]:
        return self.get_wwise_bank(soundbank_id).hierarchy.get_entries()
            
    def get_wwise_bank(self, soundbank_id: int) -> WwiseBank:
        try:
            return self.wwise_banks[soundbank_id]
        except KeyError:
            raise Exception(f"Cannot find soundbank with id {soundbank_id}")
        
    def set_wwise_bank(self, soundbank_id: int, bank: WwiseBank):
        self.wwise_banks[soundbank_id] = bank
        
    def get_wwise_stream(self, stream_id: int) -> WwiseStream:
        try:
            return self.wwise_streams[stream_id]
        except KeyError:
            raise Exception(f"Cannot find wwise stream with id {stream_id}")
        
    def set_wwise_stream(self, stream_id: int, stream: WwiseStream):
        self.wwise_streams[stream_id] = stream
    
    def get_text_bank(self, textbank_id: int) -> TextBank:
        try:
            return self.text_banks[textbank_id]
        except KeyError:
            raise Exception(f"Cannot find text bank with id {textbank_id}")
    
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
        
    def load_archive_file(self, archive_file: str = ""):
        if not archive_file or not os.path.exists(archive_file) or not os.path.isfile(archive_file):
            raise ValueError("Invalid path!")
        if os.path.splitext(archive_file)[1] in (".stream", ".gpu_resources"):
            archive_file = os.path.splitext(archive_file)[0]
        new_archive = GameArchive.from_file(archive_file)
        self.add_game_archive(new_archive)
        return True
        
    def import_wwise_hierarchy(self, soundbank_id: int, new_hierarchy: WwiseHierarchy):
        self.get_wwise_bank(soundbank_id).import_hierarchy(new_hierarchy)
        
    def generate_hierarchy_id(self, soundbank_id: int) -> int:
        hierarchy = self.get_wwise_bank(soundbank_id).hierarchy
        new_id = random.randint(0, 0xffffffff)
        while new_id in hierarchy.entries.keys():
            new_id = random.randint(0, 0xffffffff)
        return new_id
        
    def remove_game_archive(self, archive_name: str = ""):
        
        if archive_name not in self.game_archives.keys():
            return
            
        game_archive = self.game_archives[archive_name]
            
        for key in game_archive.wwise_banks.keys():
            if key in self.get_wwise_banks().keys():
                self.bank_count[key] -= 1
                if self.bank_count[key] == 0:
                    for audio in self.get_wwise_banks()[key].get_content():
                        parents = [p for p in audio.parents]
                        for parent in parents:
                            if isinstance(parent, HircEntry) and parent.soundbank.get_id() == key:
                                audio.parents.remove(parent)
                    del self.get_wwise_banks()[key]
                    del self.bank_count[key]
        for key in game_archive.wwise_streams.keys():
            if key in self.get_wwise_streams().keys():
                self.stream_count[key] -= 1
                if self.stream_count[key] == 0:
                    self.get_wwise_streams()[key].audio_source.parents.remove(self.get_wwise_streams()[key])
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
        key = game_archive.name
        if key in self.game_archives.keys():
            return
        else:
            self.game_archives[key] = game_archive
            for key in game_archive.wwise_banks.keys():
                if key in self.get_wwise_banks().keys():
                    self.bank_count[key] += 1
                    for audio in game_archive.wwise_banks[key].get_content():
                        parents = [p for p in audio.parents]
                        for parent in parents:
                            if isinstance(parent, HircEntry) and parent.soundbank.get_id() == key:
                                audio.parents.remove(parent)
                                try:
                                    new_parent = self.get_hierarchy_entry(key, parent.get_id())
                                except:
                                    continue
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
        if os.path.splitext(patch_file)[1] in (".stream", ".gpu_resources"):
            patch_file = os.path.splitext(patch_file)[0]
        if not os.path.exists(patch_file) or not os.path.isfile(patch_file):
            raise ValueError("Invalid file!")
        
        patch_game_archive = None
        
        try:
            patch_game_archive = GameArchive.from_file(patch_file)
        except Exception as e:
            logger.error(f"Error occured when loading {patch_file}: {e}.")
            logger.warning("Aborting load")
            return False
                                
        for new_audio in patch_game_archive.get_audio_sources().values():
            old_audio = self.get_audio_source(new_audio.get_short_id())
            if old_audio is not None:
                if (not old_audio.modified and new_audio.get_data() != old_audio.get_data()
                    or old_audio.modified and new_audio.get_data() != old_audio.data_old):
                    old_audio.set_data(new_audio.get_data())
                    sample_rate = int.from_bytes(new_audio.get_data()[24:28], byteorder="little")
                    num_samples = int.from_bytes(new_audio.get_data()[44:48], byteorder="little")
                    len_ms = num_samples * 1000 / sample_rate
                    for item in old_audio.parents:
                        if isinstance(item, MusicTrack):
                            item.parent.set_data(duration=len_ms, entry_marker=0, exit_marker=len_ms)
                            tracks = copy.deepcopy(item.track_info)
                            for t in tracks:
                                if t.source_id == old_audio.get_short_id():
                                    t.begin_trim_offset = 0
                                    t.end_trim_offset = 0
                                    t.source_duration = len_ms
                                    t.play_at = 0
                                    break
                            item.set_data(track_info=tracks)
                            
        for bank in patch_game_archive.get_wwise_banks().values():
            self.get_wwise_banks()[bank.get_id()].import_hierarchy(bank.hierarchy)
                            

        for text_bank in patch_game_archive.get_text_banks().values():
            self.get_text_banks()[text_bank.get_id()].import_text(text_bank)
        
        return True

    def write_patch(self, output_folder: str = ""):
        if not os.path.exists(output_folder) or not os.path.isdir(output_folder):
            raise ValueError(f"Invalid output folder '{output_folder}'")
        patch_game_archive = GameArchive()
        patch_game_archive.name = "9ba626afa44a3aa3.patch_0"
        patch_game_archive.magic = 0xF0000011
        patch_game_archive.num_types = 0
        patch_game_archive.num_files = 0
        patch_game_archive.unknown = 0
        patch_game_archive.unk4Data = bytes.fromhex("CE09F5F4000000000C729F9E8872B8BD00A06B02000000000079510000000000000000000000000000000000000000000000000000000000")
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

    def import_wems(self, wems: dict[str, list[int]] | None = None, set_duration=True): 
        if not wems:
            raise Exception("No wems selected for import")
        length_import_failed = False
        for filepath, targets in wems.items():
            if not os.path.exists(filepath) or not os.path.isfile(filepath):
                continue
            have_length = True
            with open(filepath, 'rb') as f:
                audio_data = f.read()    
            if set_duration:
                try:
                    process = subprocess.run([VGMSTREAM, "-m", filepath], capture_output=True)
                    process.check_returncode()
                    for line in process.stdout.decode(locale.getpreferredencoding()).split("\n"):
                        if "sample rate" in line:
                            sample_rate = float(line[13:line.index("Hz")-1])
                        if "stream total samples" in line:
                            total_samples = int(line[22:line.index("(")-1])
                    len_ms = total_samples * 1000 / sample_rate
                except:
                    have_length = False
                    length_import_failed = True
            for target in targets:
                audio: AudioSource | None = self.get_audio_source(target)
                if audio:
                    audio.set_data(audio_data)
                    if have_length:
                        # find music segment for Audio Source
                        for item in audio.parents:
                            if isinstance(item, MusicTrack):
                                item.parent.set_data(duration=len_ms, entry_marker=0, exit_marker=len_ms)
                                tracks = copy.deepcopy(item.track_info)
                                for t in tracks:
                                    if t.source_id == audio.get_short_id():
                                        t.begin_trim_offset = 0
                                        t.end_trim_offset = 0
                                        t.source_duration = len_ms
                                        t.play_at = 0
                                        break
                                item.set_data(track_info=tracks)
        if length_import_failed:
            raise Exception("Failed to set track duration for some audio sources")
    
    def create_external_sources_list(self, sources: list[str], converstion_setting: str = DEFAULT_CONVERSION_SETTING) -> str:
        root = etree.Element("ExternalSourcesList", attrib={
            "SchemaVersion": "1",
            "Root": __file__
        })
        file = etree.ElementTree(root)
        for source in sources:
            etree.SubElement(root, "Source", attrib={
                "Path": source,
                "Conversion": conversion_setting,
                "Destination": os.path.basename(source)
            })
        file.write(os.path.join(CACHE, "external_sources.wsources"))
        
        return os.path.join(CACHE, "external_sources.wsources")
        
    def import_wavs(self, wavs: dict[str, list[int]] | None = None, wwise_project: str = DEFAULT_WWISE_PROJECT):
        if not wavs:
            raise ValueError("No wav files selected for import!")
            
        source_list = self.create_external_sources_list(wavs.keys())
        
        if SYSTEM in WWISE_SUPPORTED_SYSTEMS:
            subprocess.run([
                WWISE_CLI,
                "migrate",
                wwise_project,
                "--quiet",
            ]).check_returncode()
        else:
            raise Exception("The current operating system does not support this feature")
        
        convert_dest = os.path.join(CACHE, SYSTEM)
        if SYSTEM in WWISE_SUPPORTED_SYSTEMS:
            subprocess.run([
                WWISE_CLI,
                "convert-external-source",
                wwise_project,
                "--platform", "Windows",
                "--source-file",
                source_list,
                "--output",
                CACHE,
            ]).check_returncode()
        else:
            raise Exception("The current operating system does not support this feature")
        
        wems = {os.path.join(convert_dest, filepath): targets for filepath, targets in wavs.items()}
        
        self.import_wems(wems)
        
        for wem in wems.keys():
            try:
                os.remove(wem)
            except:
                pass
                
        try:
            os.remove(source_list)
        except:
            pass
            
    def import_files(self, file_dict: dict[str, list[int]]):
        patches = [file for file in file_dict.keys() if "patch" in os.path.splitext(file)[1]]
        wems = {file: targets for file, targets in file_dict.items() if os.path.splitext(file)[1] == ".wem"}
        wavs = {file: targets for file, targets in file_dict.items() if os.path.splitext(file)[1] == ".wav"}
        
        # check other file extensions and call vgmstream to convert to wav, then add to wavs dict
        filetypes = list(SUPPORTED_AUDIO_TYPES)
        filetypes.remove(".wav")
        filetypes.remove(".wem")
        others = {file: targets for file, targets in file_dict.items() if os.path.splitext(file)[1] in filetypes}
        temp_files = []
        for file in others.keys():
            process = subprocess.run([VGMSTREAM, "-o", f"{os.path.join(CACHE, os.path.splitext(os.path.basename(file))[0])}.wav", file], stdout=subprocess.DEVNULL).check_returncode()
            wavs[f"{os.path.join(CACHE, os.path.splitext(os.path.basename(file))[0])}.wav"] = others[file]
            temp_files.append(f"{os.path.join(CACHE, os.path.splitext(os.path.basename(file))[0])}.wav")
        
        for patch in patches:
            self.import_patch(patch_file=patch)
        if len(wems) > 0:
            self.import_wems(wems)
        if len(wavs) > 0:
            self.import_wavs(wavs)
        for file in temp_files:
            try:
                os.remove(file)
            except:
                pass
                
    def load_wav_by_mapping(self,
                 wwise_project: str,
                 wems: list[tuple[str, AudioSource, int]],
                 schema: etree.Element) -> bool:
        if len(wems) == 0:
            return True
        tree = etree.ElementTree(schema)
        schema_path = os.path.join(CACHE, "schema.xml")
        tree.write(schema_path, encoding="utf-8", xml_declaration=True)
        convert_ok = True
        convert_dest = os.path.join(CACHE, SYSTEM)
        if SYSTEM in WWISE_SUPPORTED_SYSTEMS:
            subprocess.run([
                WWISE_CLI,
                "convert-external-source",
                wwise_project,
                "--platform", "Windows",
                "--source-file",
                schema_path,
                "--output",
                CACHE,
            ]).check_returncode()
        else:
            raise Exception("The current operating system does not support this feature")

        for wem in wems:
            dest_path = os.path.join(convert_dest, wem[0])
            assert(os.path.exists(dest_path))
            with open(dest_path, "rb") as f:
                wem[1].set_data(f.read())

        try:
            os.remove(schema_path)
            shutil.rmtree(convert_dest)
        except Exception as e:
            logger.error(e)

        return True

    def load_convert_spec(self):
        spec_path = filedialog.askopenfilename(title="Choose .spec file to import", 
                                          filetypes=[("json", "")])
        if spec_path == "":
            logger.warning("Import operation cancelled")
            return
        if not os.path.exists(spec_path):
            showerror(title="Operation Failed", message=f"{spec_path} does not exist.")
            logger.warning(f"{spec_path} does not exist. Import operation " \
                    "cancelled")
            return

        root_spec: Any = None
        try:
            with open(spec_path, mode="r") as f:
                root_spec = json.load(f)
        except json.JSONDecodeError as err:
            logger.warning(err)
            root_spec = None

        if root_spec == None:
            return

        if not isinstance(root_spec, dict):
            showerror(title="Operation Failed",
                      message="Invalid data format in the given spec file.") 
            logger.warning("Invalid data format in the given spec file. Import "
                           "operation cancelled")
            return

        # Validate version number #
        if "v" not in root_spec:
            showerror(title="Operation Failed", 
                      message="The given spec file is missing field `v`") 
            logger.warning("The given spec file is missing field `v`. Import "
                           "operation cancelled.")
            return
        v = root_spec["v"]
        if v != 2:
            showerror(title="Operation Failed", 
                      message="The given spec file contain invalid version " 
                      f'number {v}.')
            logger.warning("The given spec file contain invalid version "
                           f'number {v}. Import operation cancelled')
            return

        # Validate `specs` field #
        if "specs" not in root_spec:
            showerror(title="Operation Failed", 
                      message="The given spec file is missing field `specs`.")
            logger.warning("The given spec file is missing field `specs`."
                            " Import operation cancelled.")
            return
        if not isinstance(root_spec["specs"], list):
            showerror(title="Operation Failed",
                      message="Field `specs` is not an array.")
            logger.warning("Field `specs` is not an array. Import operation "
                           "cancelled.")
            return

        # Validate `project` path #
        project = DEFAULT_WWISE_PROJECT
        if "project" not in root_spec:
            logger.warning("Missing field `project`. Using default Wwise project")
        else:
            if not isinstance(root_spec["project"], str):
                logger.warning("Field `project` is not a string. Using default"
                               " Wwise project")
            elif not os.path.exists(root_spec["project"]):
                logger.warning("The given Wwise project does not exist. Using "
                               "default Wwise project")
            else:
                project = root_spec["project"]
        if not os.path.exists(project):
            showerror(title="Operation Failed",
                      message="The default Wwise Project does not exist.")
            logger.warning("The default Wwise Project does not exist. Import "
                           "operation cancelled.")
            return
        # Validate project `conversion` setting #
        conversion = DEFAULT_CONVERSION_SETTING
        if project != DEFAULT_WWISE_PROJECT:
            if "conversion" not in root_spec:
                showerror(title="Operation Failed",
                          message="Missing field `conversion`.")
                logger.warning("Missing field `conversion`. Import operation"
                               " cancelled.")
                return
            if not isinstance(root_spec["conversion"], str):
                showerror(title="Operation Failed",
                          message="Field `conversion` is not a string.")
                logger.warning("Field `conversion` is not a string. Import "
                               "operation cancelled.")
                return
            conversion = root_spec["conversion"]

        spec_dir = os.path.dirname(spec_path)
        root = etree.Element("ExternalSourcesList", attrib={
            "SchemaVersion": "1",
            "Root": spec_dir
        })
        wems: list[tuple[str, AudioSource, int]] = []
        for sub_spec in root_spec["specs"]:
            # Validate spec format #
            if not isinstance(sub_spec, dict):
                logger.warning("Current entry is not an object. Skipping "
                               "current entry.")
                continue

            # Validate work space #
            workspace = ""
            if "workspace" not in sub_spec:
                logger.warning("The given spec file is missing field "
                               "`workspace`. Use the current directory of the "
                               "given spec file is in instead.")
                workspace = spec_dir 
            else:
                workspace = sub_spec["workspace"]
                # Relative path
                if not os.path.exists(workspace): 
                    workspace = os.path.join(spec_dir, workspace) 
            if not os.path.exists(workspace):
                showwarning(title="Operation Skipped",
                            message=f"{workspace} does not exist.")
                logger.warning(f"{workspace} does not exist. Skipping current "
                               "entry.")
                continue

            # Validate `mapping` format #
            mapping: dict[str, list[str] | str] | None
            if "mapping" not in sub_spec:
                showwarning(title="Operation Skipped", 
                            message=f"The given spec file is missing field " 
                            "`mapping`")
                logger.warning("The given spec file is missing field `mapping`. "
                        "Skipping current entry.")
                continue
            mapping = sub_spec["mapping"]
            if mapping == None or not isinstance(mapping, dict):
                showwarning(title="Operation Skipped", 
                            message="field `mapping` has an invalid data type")
                logger.warning("field `mapping` has an invalid data type. Skipping "
                        "current entry.")
                continue

            suffix: str = ""
            if "suffix" in sub_spec:
                if not isinstance(sub_spec["suffix"], str):
                    logger.warning("`suffix` is not a str. Disable "
                            "substring filtering")
                else:
                    suffix = sub_spec["suffix"]
            prefix: str = ""
            if "prefix" in sub_spec:
                if not isinstance(sub_spec["prefix"], str):
                    logger.warning("`prefix` is not a str. Disable "
                            "substring filtering")
                else:
                    prefix = sub_spec["prefix"]

            for src, dest in mapping.items():
                src = prefix + src + suffix

                abs_src = os.path.join(workspace, src)
                if not abs_src.endswith(".wav"):
                    logger.info("Require import file missing .wav extension. "
                            "Adding extension.")
                    abs_src += ".wav"
                if not os.path.exists(abs_src):
                    logger.warning(f"Required import file does not exist "
                            "Skipping the current entry.")
                    continue

                if isinstance(dest, str):
                    file_id: int | None = get_number_prefix(dest)
                    if file_id == None:
                        logger.warning(f"{dest} does not contain a valid game "
                                       "asset file id. Skipping the current "
                                       "entry.")
                        continue
                    audio = self.get_audio_source(file_id)
                    convert_dest = f"{file_id}.wem"
                    if audio == None:
                        logger.warning(f"No audio source is associated with "
                                       f"game asset file id {file_id}. Skipping "
                                       "the current entry.")
                        continue
                    etree.SubElement(root, "Source", attrib={
                        "Path": abs_src,
                        "Conversion": conversion,
                        "Destination": convert_dest 
                    })
                    wems.append((convert_dest, audio, file_id))
                elif isinstance(dest, list):
                    for d in dest:
                        if not isinstance(d, str):
                            logger.warning(f"{d} is not a string. Skipping the "
                                    "current entry.")
                        file_id: int | None = get_number_prefix(d)
                        if file_id == None:
                            logger.warning(f"{d} does not contain a valid game "
                                           "asset file id. Skipping the current "
                                           "entry.")
                            continue
                        audio = self.get_audio_source(file_id)
                        if audio == None:
                            logger.warning(f"No audio source is associated with "
                                           f"game asset file id {file_id}. "
                                           "Skipping the current entry.")
                            continue
                        convert_dest = f"{file_id}.wem"
                        etree.SubElement(root, "Source", attrib={
                            "Path": abs_src,
                            "Conversion": conversion,
                            "Destination": convert_dest
                        })
                        wems.append((convert_dest, audio, file_id))
                else:
                    logger.warning(f"{dest} is not a string or list of string. "
                            "Skipping the current entry.")
            out: str | None = None
            if "write_patch_to" not in sub_spec:
                continue
            out = sub_spec["write_patch_to"]
            if not isinstance(out, str):
                showwarning(title="Operation Skipped", 
                            message="field `write_patch_to` has an invalid data "
                            "type. Write patch operation cancelled.")
                logger.warning("field `write_patch_to` has an invalid data "
                               "type. Write patch operation cancelled.")
                continue
            if not os.path.exists(out):
                # Relative patch write #
                out = os.path.join(spec_dir, out)
                if not os.path.exists(out):
                    showwarning(title="Operation Skipped",
                                message=f"{out} does not exist. Write patch "
                                "operation cancelled.")
                    logger.warning(f"{out} does not exist. Write patch operation "
                                   "cancelled.")
                    continue
            if not self.load_wav_by_mapping(project, wems, root):
                continue
            if not self.write_patch(folder=out):
                showerror(title="Operation Failed", message="Write patch operation failed. Check "
                            "log.txt for detailed.")
            root = etree.Element("ExternalSourcesList", attrib={
                "SchemaVersion": "1",
                "Root": spec_dir 
            })
            is_revert = "revert" in sub_spec and \
                    isinstance(sub_spec["revert"], bool) and \
                    sub_spec["revert"]
            is_revert_all = "revert_all" in sub_spec and \
                    isinstance(sub_spec["revert_all"], bool) and \
                    sub_spec["revert_all"]
            if is_revert_all:
                self.revert_all()
                continue
            if is_revert:
                for wem in wems:
                    self.revert_audio(wem[2])
            wems.clear()

        self.load_wav_by_mapping(project, wems, root)
        out: str | None = None
        if "write_patch_to" not in root_spec:
            return
        out = root_spec["write_patch_to"]
        if not isinstance(out, str):
            showerror(title="Operation Failed", 
                      message="field `write_patch_to` has an invalid data "
                      "type. Write patch operation cancelled.")
            logger.warning("field `write_patch_to` has an invalid data "
                           "type. Write patch operation cancelled.")
            return
        if not os.path.exists(out):
            # Relative path patch writing #
            out = os.path.join(spec_dir, out)
            if not os.path.exists(out):
                showerror(title="Operation Failed",
                          message=f"{out} does not exist. Write patch "
                          "operation cancelled.")
                logger.warning(f"{out} does not exist. Write patch operation "
                              "cancelled.")
                return
        if not self.write_patch(folder=out):
            showerror(title="Operation Failed",
                      message="Write patch operation failed. Check "
                      "log.txt for detailed.")

        is_revert = "revert" in root_spec and \
                isinstance(root_spec["revert"], bool) and \
                root_spec["revert"]
        if is_revert:
            for wem in wems:
                self.revert_audio(wem[2])

    def import_wems_spec(self):
        spec_path = filedialog.askopenfilename(title="Choose .spec file to import", 
                                          filetypes=[("json", "")])
        if spec_path == "":
            logger.warning("Import operation cancelled")
            return
        if not os.path.exists(spec_path):
            showerror(title="Operation Failed", 
                      message=f"{spec_path} does not exist.")
            logger.warning(f"{spec_path} does not exist. Import operation "
                           "cancelled")
            return

        root_spec: Any = None
        try:
            with open(spec_path, mode="r") as f:
                root_spec = json.load(f)
        except json.JSONDecodeError as err:
            logger.warning(err)
            root_spec = None

        if root_spec == None:
            return

        if not isinstance(root_spec, dict):
            showerror(title="Operation Failed",
                      message="Invalid data format in the given spec file.") 
            logger.warning("Invalid data format in the given spec file. Import "
                    "operation cancelled")
            return

        # Validate version number # 
        if "v" not in root_spec:
            showerror(title="Operation Failed",
                      message="The given spec file is missing field `v`") 
            logger.warning("The given spec file is missing field `v`. Import "
                    "operation cancelled.")
            return
        if root_spec["v"] != 2:
            showerror(title="Operation Failed",
                      message="The given spec file contain invalid version " + 
                        f'number {root_spec["v"]}.')
            logger.warning("The given spec file contain invalid version "
                    f'number {root_spec["v"]}. Import operation cancelled')
            return

        # Validate `specs` format #
        if "specs" not in root_spec:
            showerror(title="Operation Failed",
                      message="The given spec file is missing field `specs`.")
            logger.warning("The given spec file is missing field `specs`."
                            " Import operation cancelled.")
            return
        if not isinstance(root_spec["specs"], list):
            showerror(title="Operation Failed",
                      message="Field `specs` is not an array.")
            logger.warning("Field `specs` is not an array. Import operation "
                           "cancelled.")
            return

        spec_dir = os.path.dirname(spec_path)
        patched_ids: list[int] = []
        for sub_spec in root_spec["specs"]:
            if not isinstance(sub_spec, dict):
                logger.warning("Current entry is not an object. Skipping "
                               "current entry.")
                continue

            workspace = ""
            # Validate work space # 
            if "workspace" not in sub_spec:
                logger.warning("The given spec file is missing field "
                               "`workspace`. Use the current directory of the "
                               "given spec file is in instead.")
                workspace = spec_dir
            else:
                workspace = sub_spec["workspace"]
                # Relative path
                if not os.path.exists(workspace): 
                    workspace = os.path.join(spec_dir, workspace) 
            if not os.path.exists(workspace):
                showwarning(title="Operation Skipped",
                            message=f"{workspace} does not exist.")
                logger.warning(f"{workspace} does not exist. Skipping current"
                        " entry")
                continue

            # Validate `mapping` format # 
            mapping: dict[str, list[str] | str] | None
            if "mapping" not in sub_spec:
                showwarning(title="Operation Skipped",
                            message=f"The given spec file is missing field "
                            "`mapping`")
                logger.warning("The given spec file is missing field `mapping`. "
                        "Skipping current entry")
                continue
            mapping = sub_spec["mapping"]
            if mapping == None or not isinstance(mapping, dict):
                showwarning(title="Operation Skipped",
                            message="field `mapping` has an invalid data type")
                logger.warning("field `mapping` has an invalid data type. "
                        "Skipping current entry")
                continue

            suffix: str = ""
            if "suffix" in sub_spec:
                if not isinstance(sub_spec["suffix"], str):
                    logger.warning("`suffix` is not a str. Disable "
                            "substring filtering")
                else:
                    suffix = sub_spec["suffix"]
            prefix: str = ""
            if "prefix" in sub_spec:
                if not isinstance(sub_spec["prefix"], str):
                    logger.warning("`prefix` is not a str. Disable "
                            "substring filtering")
                else:
                    prefix = sub_spec["prefix"]

            progress_window = ProgressWindow(title="Loading Files",
                                             max_progress=len(sub_spec.items()))
            progress_window.show()

            for src, dest in mapping.items():
                logger.info(f"Loading {src} into {dest}")
                progress_window.set_text(f"Loading {src} into {dest}")

                src = prefix + src + suffix

                abs_src = os.path.join(workspace, src)
                if not abs_src.endswith(".wem"):
                    logger.info("Require import file missing .wem extension. "
                            "Adding extension.")
                    abs_src += ".wem"
                if not os.path.exists(abs_src):
                    logger.warning(f"Required import file does not exist "
                            "Skipping the current entry.")
                    continue

                if isinstance(dest, str):
                    file_id: int | None = get_number_prefix(dest)
                    if file_id == None:
                        logger.warning(f"{dest} does not contain a valid game "
                                       "asset file id. Skipping the current "
                                       "entry.")
                        continue
                    audio: str | None = self.get_audio_source(file_id)
                    if audio == None:
                        logger.warning(f"No audio source is associated with "
                                       "game asset file id {file_id}. Skipping "
                                       "the current entry.")
                        continue
                    with open(abs_src, "rb") as f:
                        audio.set_data(f.read())
                    progress_window.step()

                    patched_ids.append(file_id)
                elif isinstance(dest, list):
                    for d in dest:
                        if not isinstance(d, str):
                            logger.warning(f"{d} is not a string. Skipping the "
                                    "current entry.")
                        file_id: int | None = get_number_prefix(d)
                        if file_id == None:
                            logger.warning(f"{d} does not contain a valid game "
                                           "asset file id. Skipping the current "
                                           "entry.")
                            continue
                        audio: str | None = self.get_audio_source(file_id)
                        if audio == None:
                            logger.warning(f"No audio source is associated with "
                                    "game asset file id {file_id}. Skipping the "
                                    "current entry.")
                            continue
                        with open(abs_src, "rb") as f:
                            audio.set_data(f.read())
                        progress_window.step()

                        patched_ids.append(file_id)
                else:
                    logger.warning(f"{dest} is not a string or list of string. "
                            "Skipping the current entry.")

            progress_window.destroy()

            out: str | None = None
            if "write_patch_to" not in sub_spec:
                return
            out = sub_spec["write_patch_to"]
            if not isinstance(out, str):
                showwarning(title="Operation Skipped",
                            message="field `write_patch_to` has an invalid data "
                            "type. Write patch operation cancelled.")
                logger.warning("field `write_patch_to` has an invalid data "
                               "type. Write patch operation cancelled.")
                continue
            if not os.path.exists(out):
                # Relative path
                out = os.path.join(spec_dir, out)
                if not os.path.exists(out):
                    showwarning(title="Operation Skipped", 
                                message=f"{out} does not exist. Write patch "
                                "operation cancelled.")
                    logger.warning(f"{out} does not exist. Write patch operation "
                                   "cancelled.")
                    continue
            if not self.write_patch(folder=out):
                showerror(title="Operation Failed",
                          message="Write patch operation failed. Check "
                          "log.txt for detailed.")
            is_revert = "revert" in sub_spec and \
                    isinstance(sub_spec["revert"], bool) and \
                    sub_spec["revert"]
            if is_revert:
                for patched_id in patched_ids:
                    self.revert_audio(patched_id)
            patched_ids.clear()
            
        out: str | None = None
        if "write_patch_to" not in root_spec:
            return
        out = root_spec["write_patch_to"]
        if not isinstance(out, str):
            showerror(title="Operation Failed", message="field `write_patch_to` has an invalid data "
                        "type. Write patch operation cancelled.")
            logger.warning("field `write_patch_to` has an invalid data "
                           "type. Write patch operation cancelled.")
            return
        if not os.path.exists(out):
            # Relative path
            out = os.path.join(spec_dir, out)
            if not os.path.exists(out):
                showerror(title="Operation Failed", message=f"{out} does not exist. Write patch "
                            "operation cancelled.")
                logger.warning(f"{out} does not exist. Write patch operation "
                               "cancelled.")
                return
        if not self.write_patch(folder=out):
            showerror(title="Operation Failed", message="Write patch operation failed. Check "
                            "log.txt for detailed.")

        is_revert = "revert" in root_spec and \
                isinstance(root_spec["revert"], bool) and \
                root_spec["revert"]
        if is_revert:
            for patched_id in patched_ids:
                self.revert_audio(patched_id)
        patched_ids.clear()
        
class ModHandler:
    
    handler_instance = None
    
    def __init__(self):
        self.mods = {}
        
    @classmethod
    def create_instance(cls):
        cls.handler_instance = ModHandler()
        
    @classmethod
    def get_instance(cls) -> Self:
        if cls.handler_instance == None:
            cls.create_instance()
        return cls.handler_instance
        
    def create_new_mod(self, mod_name: str):
        if mod_name in self.mods.keys():
            raise ValueError(f"Mod name '{mod_name}' already exists!")
        new_mod = Mod(mod_name)
        self.mods[mod_name] = new_mod
        self.active_mod = new_mod
        return new_mod
        
    def get_active_mod(self) -> Mod:
        if not self.active_mod:
            raise Exception("No active mod!")
        return self.active_mod
        
    def set_active_mod(self, mod_name: str):
        try:
            self.active_mod = self.mods[mod_name]
        except:
            raise ValueError(f"No matching mod found for '{mod_name}'")
            
    def get_mod_names(self) -> list[str]:
        return self.mods.keys()
        
    def delete_mod(self, mod: str | Mod):
        if isinstance(mod, Mod):
            mod_name = mod.name
        else:
            mod_name = mod
        try:
            mod_to_delete = self.mods[mod_name]
        except:
            raise ValueError(f"No matching mod found for '{mod}'")
        if mod_to_delete is self.active_mod:
            if len(self.mods) > 1:
                for mod in self.mods.values():
                    if mod is not self.active_mod:
                        self.active_mod = mod
                        break
            else:
                self.active_mod = None
        del self.mods[mod_name]
class ProgressWindow:
    def __init__(self, title, max_progress):
        self.title = title
        self.max_progress = max_progress
        
    def show(self):
        self.root = Tk()
        self.root.title(self.title)
        self.root.geometry("410x45")
        self.root.attributes('-topmost', True)
        self.progress_bar = tkinter.ttk.Progressbar(self.root, orient=HORIZONTAL, length=400, mode="determinate", maximum=self.max_progress)
        self.progress_bar_text = Text(self.root)
        self.progress_bar.pack()
        self.progress_bar_text.pack()
        self.root.resizable(False, False)
        
    def step(self):
        self.progress_bar.step()
        self.root.update_idletasks()
        self.root.update()
        
    def set_text(self, s):
        self.progress_bar_text.delete('1.0', END)
        self.progress_bar_text.insert(INSERT, s)
        self.root.update_idletasks()
        self.root.update()
        
    def destroy(self):
        self.root.destroy()
        
class PopupWindow:
    def __init__(self, message, title="Missing Data!"):
        self.message = message
        self.title = title
        
    def show(self):
        self.root = Tk()
        self.root.title(self.title)
        #self.root.geometry("410x45")
        self.root.attributes('-topmost', True)
        self.text = ttk.Label(self.root,
                              text=self.message,
                              font=('Segoe UI', 12),
                              wraplength=500,
                              justify="left")
        self.button = ttk.Button(self.root, text="OK", command=self.destroy)
        self.text.pack(padx=20, pady=0)
        self.button.pack(pady=20)
        self.root.resizable(False, False)
        
    def destroy(self):
        self.root.destroy()
        
class StringEntryWindow:
    
    def __init__(self, parent, update_modified):
        self.frame = Frame(parent)
        self.update_modified = update_modified
        self.text_box = Text(self.frame, width=54, font=('Segoe UI', 12), wrap=WORD)
        self.string_entry = None
        self.fake_image = tkinter.PhotoImage(width=1, height=1)
        
        self.revert_button = ttk.Button(self.frame, text="\u21b6", command=self.revert)
        
        self.apply_button = ttk.Button(self.frame, text="Apply", command=self.apply_changes)
        self.text_box.pack()
        self.revert_button.pack(side="left")
        self.apply_button.pack(side="left")
        
    def set_string_entry(self, string_entry):
        self.string_entry = string_entry
        self.text_box.delete("1.0", END)
        self.text_box.insert(END, string_entry.get_text())
        
    def apply_changes(self):
        if self.string_entry is not None:
            self.string_entry.set_text(self.text_box.get("1.0", "end-1c"))
            self.update_modified()
    
    def revert(self):
        if self.string_entry is not None:
            self.string_entry.revert_modifications()
            self.text_box.delete("1.0", END)
            self.text_box.insert(END, self.string_entry.get_text())
            self.update_modified()
            
class MusicTrackWindow:
    
    def __init__(self, parent, update_modified):
        self.frame = Frame(parent)
        self.selected_track = 0
        self.update_modified = update_modified
        self.fake_image = tkinter.PhotoImage(width=1, height=1)
        self.title_label = ttk.Label(self.frame, font=('Segoe UI', 14), width=50, anchor="center")
        self.revert_button = ttk.Button(self.frame, text='\u21b6', image=self.fake_image, compound='c', width=2, command=self.revert)
        self.play_at_text_var = tkinter.StringVar(self.frame)
        self.duration_text_var = tkinter.StringVar(self.frame)
        self.start_offset_text_var = tkinter.StringVar(self.frame)
        self.end_offset_text_var = tkinter.StringVar(self.frame)
        self.source_selection_listbox = tkinter.Listbox(self.frame)
        self.source_selection_listbox.bind("<Double-Button-1>", self.set_track_info)
        
        self.play_at_label = ttk.Label(self.frame,
                                   text="Play At (ms)",
                                   font=('Segoe UI', 12),
                                   anchor="center")
        self.play_at_text = ttk.Entry(self.frame, textvariable=self.play_at_text_var, font=('Segoe UI', 12), width=54)
        
        
        self.duration_label = ttk.Label(self.frame,
                                    text="Duration (ms)",
                                    font=('Segoe UI', 12),
                                    anchor="center")
        self.duration_text = ttk.Entry(self.frame, textvariable=self.duration_text_var, font=('Segoe UI', 12), width=54)
        
        
        self.start_offset_label = ttk.Label(self.frame,
                                        text="Start Trim (ms)",
                                        font=('Segoe UI', 12),
                                        anchor="center")
        self.start_offset_text = ttk.Entry(self.frame, textvariable=self.start_offset_text_var, font=('Segoe UI', 12), width=54)
        
        
        self.end_offset_label = ttk.Label(self.frame,
                                      text="End Trim (ms)",
                                      font=('Segoe UI', 12),
                                      anchor="center")
        self.end_offset_text = ttk.Entry(self.frame, textvariable=self.end_offset_text_var, font=('Segoe UI', 12), width=54)

        self.apply_button = ttk.Button(self.frame, text="Apply", command=self.apply_changes)
        
        self.title_label.pack(pady=5)
        
    def set_track_info(self, event=None, selection=0):
        if not selection:
            selection = self.source_selection_listbox.get(self.source_selection_listbox.curselection()[0])
        for t in self.track.track_info:
            if t.source_id == selection or t.event_id == selection:
                track_info_struct = t
                break
                
        self.selected_track = track_info_struct
                
        self.duration_text.delete(0, 'end')
        self.duration_text.insert(END, str(track_info_struct.source_duration))
        self.start_offset_text.delete(0, 'end')
        self.start_offset_text.insert(END, str(track_info_struct.begin_trim_offset))
        self.end_offset_text.delete(0, 'end')
        self.end_offset_text.insert(END, str(track_info_struct.end_trim_offset))
        self.play_at_text.delete(0, 'end')
        self.play_at_text.insert(END, str(track_info_struct.play_at))
        
        self.play_at_label.pack()
        self.play_at_text.pack()
        self.duration_label.pack()
        self.duration_text.pack()
        self.start_offset_label.pack()
        self.start_offset_text.pack()
        self.end_offset_label.pack()
        self.end_offset_text.pack()
        
        self.revert_button.pack(side="left")
        
    def set_track(self, track):
        self.track = track
        self.source_selection_listbox.delete(0, 'end')
        for track_info_struct in self.track.track_info:
            if track_info_struct.source_id != 0:
                self.source_selection_listbox.insert(END, track_info_struct.source_id)
            else:
                self.source_selection_listbox.insert(END, track_info_struct.event_id)
        
        if len(track.track_info) > 0:
            self.source_selection_listbox.pack()
            self.set_track_info(selection=track.track_info[0].source_id if track.track_info[0].source_id != 0 else track.track_info[0].event_id)
    def revert(self):
        self.track.revert_modifications()
        self.set_track(self.track)
        
    def apply_changes(self):
        pass
        
        
class AudioSourceWindow:
    
    def __init__(self, parent, play, update_modified):
        self.frame = Frame(parent)
        self.update_modified = update_modified
        self.fake_image = tkinter.PhotoImage(width=1, height=1)
        self.play = play
        self.track_info = None
        self.audio = None
        self.title_label = ttk.Label(self.frame, font=('Segoe UI', 14), width=50, anchor="center")
        self.revert_button = ttk.Button(self.frame, text='\u21b6', image=self.fake_image, compound='c', width=2, command=self.revert)
        self.play_button = ttk.Button(self.frame, text= '\u23f5', image=self.fake_image, compound='c', width=2)
        self.play_original_button = ttk.Button(self.frame, text= '\u23f5', width=2)
        self.play_original_label = ttk.Label(self.frame, font=('Segoe UI', 12), text="Play Original Audio")
        self.play_at_text_var = tkinter.StringVar(self.frame)
        self.duration_text_var = tkinter.StringVar(self.frame)
        self.start_offset_text_var = tkinter.StringVar(self.frame)
        self.end_offset_text_var = tkinter.StringVar(self.frame)
        
        self.play_at_label = ttk.Label(self.frame,
                                   text="Play At (ms)",
                                   font=('Segoe UI', 12),
                                   anchor="center")
        self.play_at_text = ttk.Entry(self.frame, textvariable=self.play_at_text_var, font=('Segoe UI', 12), width=54)
        
        
        self.duration_label = ttk.Label(self.frame,
                                    text="Duration (ms)",
                                    font=('Segoe UI', 12),
                                    anchor="center")
        self.duration_text = ttk.Entry(self.frame, textvariable=self.duration_text_var, font=('Segoe UI', 12), width=54)
        
        
        self.start_offset_label = ttk.Label(self.frame,
                                        text="Start Trim (ms)",
                                        font=('Segoe UI', 12),
                                        anchor="center")
        self.start_offset_text = ttk.Entry(self.frame, textvariable=self.start_offset_text_var, font=('Segoe UI', 12), width=54)
        
        
        self.end_offset_label = ttk.Label(self.frame,
                                      text="End Trim (ms)",
                                      font=('Segoe UI', 12),
                                      anchor="center")
        self.end_offset_text = ttk.Entry(self.frame, textvariable=self.end_offset_text_var, font=('Segoe UI', 12), width=54)

        self.apply_button = ttk.Button(self.frame, text="Apply", command=self.apply_changes)
        
        self.title_label.pack(pady=5)
        
    def set_audio(self, audio):
        self.audio = audio
        self.title_label.configure(text=f"Info for {audio.get_id()}.wem")
        self.play_button.configure(text= '\u23f5')
        self.revert_button.pack_forget()
        self.play_button.pack_forget()
        self.apply_button.pack_forget()
        def reset_button_icon(button):
            button.configure(text= '\u23f5')
        def press_button(button, file_id, callback):
            if button['text'] == '\u23f9':
                button.configure(text= '\u23f5')
            else:
                button.configure(text= '\u23f9')
            self.play(file_id, callback)
        def play_original_audio(button, file_id, callback):
            if button['text'] == '\u23f9':
                button.configure(text= '\u23f5')
            else:
                button.configure(text= '\u23f9')
            temp = self.audio.data
            self.audio.data = self.audio.data_old
            self.play(file_id, callback)
            self.audio.data = temp
        self.play_button.configure(command=partial(press_button, self.play_button, audio.get_short_id(), partial(reset_button_icon, self.play_button)))
        self.play_original_button.configure(command=partial(play_original_audio, self.play_original_button, audio.get_short_id(), partial(reset_button_icon, self.play_original_button)))
        
        self.revert_button.pack(side="left")
        self.play_button.pack(side="left")
        
        if self.audio.modified and self.audio.data_old != b"":
            self.play_original_label.pack(side="right")
            self.play_original_button.pack(side="right")
        else:
            self.play_original_label.forget()
            self.play_original_button.forget()
            
    def revert(self):
        self.audio.revert_modifications()
        if self.track_info is not None:
            self.track_info.revert_modifications()
            self.play_at_text.delete(0, 'end')
            self.duration_text.delete(0, 'end')
            self.start_offset_text.delete(0, 'end')
            self.end_offset_text.delete(0, 'end')
            self.play_at_text.insert(END, f"{self.track_info.play_at}")
            self.duration_text.insert(END, f"{self.track_info.source_duration}")
            self.start_offset_text.insert(END, f"{self.track_info.begin_trim_offset}")
            self.end_offset_text.insert(END, f"{self.track_info.end_trim_offset}")
        self.update_modified()
        self.play_original_label.forget()
        self.play_original_button.forget()
        
    def apply_changes(self):
        self.track_info.set_data(play_at=float(self.play_at_text_var.get()), begin_trim_offset=float(self.start_offset_text_var.get()), end_trim_offset=float(self.end_offset_text_var.get()), source_duration=float(self.duration_text_var.get()))
        self.update_modified()
        
class MusicSegmentWindow:
    def __init__(self, parent, update_modified):
        self.frame = Frame(parent)
        self.update_modified = update_modified
        
        self.title_label = ttk.Label(self.frame, font=('Segoe UI', 14), anchor="center")

        self.duration_text_var = tkinter.StringVar(self.frame)
        self.fade_in_text_var = tkinter.StringVar(self.frame)
        self.fade_out_text_var = tkinter.StringVar(self.frame)
        
        self.duration_label = ttk.Label(self.frame,
                                    text="Duration (ms)",
                                    font=('Segoe UI', 12))
        self.duration_text = ttk.Entry(self.frame, textvariable=self.duration_text_var, font=('Segoe UI', 12), width=54)
        
        self.fade_in_label = ttk.Label(self.frame,
                                   text="End fade-in (ms)",
                                   font=('Segoe UI', 12))
        self.fade_in_text = ttk.Entry(self.frame, textvariable=self.fade_in_text_var, font=('Segoe UI', 12), width=54)
        
        self.fade_out_label = ttk.Label(self.frame,
                                    text="Start fade-out (ms)",
                                    font=('Segoe UI', 12))
        self.fade_out_text = ttk.Entry(self.frame, textvariable=self.fade_out_text_var, font=('Segoe UI', 12), width=54)
        self.revert_button = ttk.Button(self.frame, text="\u21b6", command=self.revert)
        self.apply_button = ttk.Button(self.frame, text="Apply", command=self.apply_changes)
        
        self.title_label.pack(pady=5)
        
        self.duration_label.pack()
        self.duration_text.pack()
        self.fade_in_label.pack()
        self.fade_in_text.pack()
        self.fade_out_label.pack()
        self.fade_out_text.pack()
        self.revert_button.pack(side="left")
        self.apply_button.pack(side="left")
        
    def set_segment_info(self, segment):
        self.title_label.configure(text=f"Info for Music Segment {segment.get_id()}")
        self.segment = segment
        self.duration_text.delete(0, 'end')
        self.fade_in_text.delete(0, 'end')
        self.fade_out_text.delete(0, 'end')
        self.duration_text.insert(END, f"{self.segment.duration}")
        self.fade_in_text.insert(END, f"{self.segment.entry_marker[1]}")
        self.fade_out_text.insert(END, f"{self.segment.exit_marker[1]}")
        
        
    def revert(self):
        self.segment.revert_modifications()
        self.duration_text.delete(0, 'end')
        self.fade_in_text.delete(0, 'end')
        self.fade_out_text.delete(0, 'end')
        self.duration_text.insert(END, f"{self.segment.duration}")
        self.fade_in_text.insert(END, f"{self.segment.entry_marker[1]}")
        self.fade_out_text.insert(END, f"{self.segment.exit_marker[1]}")
        self.update_modified()
        
    def apply_changes(self):
        self.segment.set_data(duration=float(self.duration_text_var.get()), entry_marker=float(self.fade_in_text_var.get()), exit_marker=float(self.fade_out_text_var.get()))
        self.update_modified()
 
class EventWindow:

    def __init__(self, parent, update_modified):
        self.frame = Frame(parent)
        self.update_modified = update_modified
        
        self.title_label = Label(self.frame, font=('Segoe UI', 14))
        
        self.play_at_text_var = tkinter.StringVar(self.frame)
        self.duration_text_var = tkinter.StringVar(self.frame)
        self.start_offset_text_var = tkinter.StringVar(self.frame)
        self.end_offset_text_var = tkinter.StringVar(self.frame)
        
        self.play_at_label = ttk.Label(self.frame,
                                   text="Play At (ms)",
                                   font=('Segoe UI', 12))
        self.play_at_text = ttk.Entry(self.frame, textvariable=self.play_at_text_var, font=('Segoe UI', 12), width=54)
        
        self.duration_label = ttk.Label(self.frame,
                                    text="Duration (ms)",
                                    font=('Segoe UI', 12))
        self.duration_text = ttk.Entry(self.frame, textvariable=self.duration_text_var, font=('Segoe UI', 12), width=54)
        
        self.start_offset_label = ttk.Label(self.frame,
                                        text="Start Trim (ms)",
                                        font=('Segoe UI', 12))
        self.start_offset_text = ttk.Entry(self.frame, textvariable=self.start_offset_text_var, font=('Segoe UI', 12), width=54)
        
        self.end_offset_label = ttk.Label(self.frame,
                                      text="End Trim (ms)",
                                      font=('Segoe UI', 12))
        self.end_offset_text = ttk.Entry(self.frame, textvariable=self.end_offset_text_var, font=('Segoe UI', 12), width=54)
        self.revert_button = ttk.Button(self.frame, text="\u21b6", command=self.revert)
        self.apply_button = ttk.Button(self.frame, text="Apply", command=self.apply_changes)
        
        self.title_label.pack(pady=5)
        
        self.play_at_label.pack()
        self.play_at_text.pack()
        self.duration_label.pack()
        self.duration_text.pack()
        self.start_offset_label.pack()
        self.start_offset_text.pack()
        self.end_offset_label.pack()
        self.end_offset_text.pack()
        self.revert_button.pack(side="left")
        self.apply_button.pack(side="left")
        
    def set_track_info(self, track_info):
        self.title_label.configure(text=f"Info for Event {track_info.get_id()}")
        self.track_info = track_info
        self.play_at_text.delete(0, 'end')
        self.duration_text.delete(0, 'end')
        self.start_offset_text.delete(0, 'end')
        self.end_offset_text.delete(0, 'end')
        self.play_at_text.insert(END, f"{self.track_info.play_at}")
        self.duration_text.insert(END, f"{self.track_info.source_duration}")
        self.start_offset_text.insert(END, f"{self.track_info.begin_trim_offset}")
        self.end_offset_text.insert(END, f"{self.track_info.end_trim_offset}")
        
    def revert(self):
        self.track_info.revert_modifications()
        self.play_at_text.delete(0, 'end')
        self.duration_text.delete(0, 'end')
        self.start_offset_text.delete(0, 'end')
        self.end_offset_text.delete(0, 'end')
        self.play_at_text.insert(END, f"{self.track_info.play_at}")
        self.duration_text.insert(END, f"{self.track_info.source_duration}")
        self.start_offset_text.insert(END, f"{self.track_info.begin_trim_offset}")
        self.end_offset_text.insert(END, f"{self.track_info.end_trim_offset}")
        self.update_modified()
        
    def apply_changes(self):
        self.track_info.set_data(play_at=float(self.play_at_text_var.get()), begin_trim_offset=float(self.start_offset_text_var.get()), end_trim_offset=float(self.end_offset_text_var.get()), source_duration=float(self.duration_text_var.get()))
        self.update_modified()

"""
Not suggested to use this as a generic autocomplete widget for other searches.
Currently it's only used specifically for search archive.
"""
class ArchiveSearch(ttk.Entry):

    ignore_keys: list[str] = ["Up", "Down", "Left", "Right", "Escape", "Return"]

    def __init__(self, 
                 fmt: str,
                 entries: dict[str, str] = {}, 
                 on_select_cb: Callable[[Any], None] | None = None,
                 master: Misc | None = None,
                 **options):
        super().__init__(master, **options)

        self.on_select_cb = on_select_cb
        self.entries = entries
        self.fmt = fmt

        self.cmp_root: tkinter.Toplevel | None = None
        self.cmp_list: tkinter.Listbox | None = None
        self.cmp_scrollbar: ttk.Scrollbar | None = None

        self.bind("<Key>", self.on_key_release)
        self.bind("<FocusOut>", self.on_focus_out)
        self.bind("<Return>", self.on_return)
        self.bind("<Escape>", self.destroy_cmp)
        self.bind("<Up>", self.on_arrow_up)
        self.bind("<Down>", self.on_arrow_down)
        self.winfo_toplevel().bind("<Configure>", self.sync_windows)

    def sync_windows(self, event=None):
        if self.cmp_root is not None and self.winfo_toplevel() is not None:
            self.cmp_root.geometry(f"+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height()}")
            self.cmp_root.lift()

    def on_key_release(self, event: tkinter.Event):
        if event.keysym in self.ignore_keys:
            return
        query = self.get().lower()

        if self.cmp_root != None:
            if self.cmp_list == None:
                logger.error("Autocomplete error!" \
                        "cmp_list should not be None with cmp_root still" \
                        "active", stack_info=True)
                self.cmp_root.destroy()
                return
            archives = []
            if query == "":
                archives = [self.fmt.format(k, v) 
                            for k, v in self.entries.items()]
            else:
                unique: set[str] = set()
                for archive_id, tag in self.entries.items():
                    match = archive_id.find(query) != -1 or \
                            tag.lower().find(query) != -1
                    if not match or archive_id in unique:
                        continue
                    archives.append(self.fmt.format(archive_id, tag))
                    unique.add(archive_id)
            self.cmp_list.delete(0, tkinter.END)
            for archive in archives:
                self.cmp_list.insert(tkinter.END, archive)
            height="128"
            if len(archives) < 7:
                height=str(2+18*len(archives))
                try:
                    self.cmp_scrollbar.pack_forget()
                except:
                    pass
            elif len(archives) > 7:
                try:
                    self.cmp_scrollbar.pack(side="left", fill="y")
                except:
                    pass
            self.cmp_root.geometry(f"{self.winfo_width()}x{height}")
            self.cmp_list.selection_clear(0, tkinter.END)
            self.cmp_list.selection_set(0)
            return

        archives = []
        if query == "":
            archives = [self.fmt.format(k, v) for k, v in self.entries.items()]
        else:
            unique: set[str] = set()
            for archive_id, tag in self.entries.items():
                match = archive_id.find(query) != -1 or tag.lower().find(query) != -1
                if not match or archive_id in unique:
                    continue
                archives.append(self.fmt.format(archive_id, tag))
                unique.add(archive_id)

        self.cmp_root = tkinter.Toplevel(self)
        self.cmp_root.wm_overrideredirect(True) # Hide title bar
        

        self.cmp_list = tkinter.Listbox(self.cmp_root, borderwidth=1)

        self.cmp_list.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=True)
        
        if len(archives) > 7:
            self.cmp_scrollbar = ttk.Scrollbar(self.cmp_root, orient=VERTICAL)
            self.cmp_scrollbar.pack(side="left", fill="y")
            self.cmp_list.configure(yscrollcommand=self.cmp_scrollbar.set)
            self.cmp_scrollbar['command'] = self.cmp_list.yview

        for archive in archives:
            self.cmp_list.insert(tkinter.END, archive)

        self.cmp_list.selection_set(0)

        self.cmp_list.bind("<Double-Button-1>", self.on_return)
        height="128"
        if len(archives) < 7:
            height=str(2+18*len(archives))
        self.cmp_root.geometry(f"{self.winfo_width()}x{height}")
        self.cmp_root.geometry(f"+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height()}")
        
    def error_check(self):
        if self.cmp_root == None:
            return 1
        if self.cmp_list == None:
            logger.critical("Autocomplete error!" \
                    "Autocomplete list is not initialized", stack_info=True)
            return 1
        curr_select = self.cmp_list.curselection()
        if len(curr_select) == 0:
            return 1
        if len(curr_select) != 1:
            logger.warning("Something went wrong with autocomplete: " \
                    "more than one item is selected.", stack_info=True)
        return 0

    def on_arrow_up(self, _: tkinter.Event) -> str | None:
        if self.error_check() != 0:
            return
        curr_select = self.cmp_list.curselection()
        curr_idx = curr_select[0]
        prev_idx = (curr_idx - 1) % self.cmp_list.size()
        self.cmp_list.selection_clear(0, tkinter.END)
        self.cmp_list.selection_set(prev_idx)
        self.cmp_list.activate(prev_idx)
        self.cmp_list.see(prev_idx)
        return "break" # Prevent default like in JS

    def on_arrow_down(self, _: tkinter.Event):
        if self.error_check() != 0:
            return
        curr_select = self.cmp_list.curselection()
        curr_idx = curr_select[0]
        next_idx = (curr_idx + 1) % self.cmp_list.size()
        self.cmp_list.selection_clear(0, tkinter.END)
        self.cmp_list.selection_set(next_idx)
        self.cmp_list.activate(next_idx)
        self.cmp_list.see(next_idx)
        return "break" # Prevent default like in JS

    def on_return(self, _: tkinter.Event):
        if self.error_check() != 0:
            return
        curr_select = self.cmp_list.curselection()
        value = self.cmp_list.get(curr_select[0])
        self.delete(0, tkinter.END)
        self.insert(0, value)
        self.icursor(tkinter.END)
        self.destroy_cmp(None)
        if self.on_select_cb == None:
            return
        self.on_select_cb(value)

    def destroy_cmp(self, _: tkinter.Event | None):
        if self.cmp_list != None:
            self.cmp_list.destroy()
            self.cmp_list = None

        if self.cmp_root != None:
            self.cmp_root.destroy()
            self.cmp_root = None

    def on_focus_out(self, event):
        if self.cmp_root is not None:
            self.cmp_root.after(1, self.check_should_destroy)

    def check_should_destroy(self):
        new_focus = self.cmp_root.focus_get()
        if new_focus != self.cmp_list and new_focus != self.cmp_root:
            self.destroy_cmp(None)

    def set_entries(self, entries: dict[str, str], fmt: str | None = None):
        if fmt != None:
            self.fmt = fmt
        self.entries = entries
        self.delete(0, tkinter.END)

class MainWindow:

    dark_mode_bg = "#333333"
    dark_mode_fg = "#ffffff"
    dark_mode_modified_bg = "#ffffff"
    dark_mode_modified_fg = "#333333"
    light_mode_bg = "#ffffff"
    light_mode_fg = "#000000"
    light_mode_modified_bg = "#7CFC00"
    light_mode_modified_fg = "#000000"

    def __init__(self, 
                 app_state: cfg.Config, 
                 lookup_store: db.LookupStore | None):
        self.app_state = app_state
        self.lookup_store = lookup_store
        self.sound_handler = SoundHandler.get_instance()
        self.watched_paths = []
        self.mod_handler = ModHandler.get_instance()
        self.mod_handler.create_new_mod("default")
        
        self.root = TkinterDnD.Tk()
        if os.path.exists("icon.ico"):
            self.root.iconbitmap("icon.ico")
        
        self.drag_source_widget = None
        self.workspace_selection = []
        
        try:
            self.root.tk.call("source", "azure.tcl")
        except Exception as e:
            logger.critical("Error occurred when loading themes:")
            logger.critical(e)
            logger.critical("Ensure azure.tcl and the themes folder are in the same folder as the executable")

        self.fake_image = tkinter.PhotoImage(width=1, height=1)

        self.top_bar = Frame(self.root, width=WINDOW_WIDTH, height=40)
        self.search_text_var = tkinter.StringVar(self.root)
        self.search_bar = ttk.Entry(self.top_bar, textvariable=self.search_text_var, font=('Segoe UI', 14))
        self.top_bar.pack(side="top", fill='x')
        if lookup_store != None and os.path.exists(GAME_FILE_LOCATION):
            self.init_archive_search_bar()

        self.up_button = ttk.Button(self.top_bar, text='\u25b2',
                                    width=2, command=self.search_up)
        self.down_button = ttk.Button(self.top_bar, text='\u25bc',
                                      width=2, command=self.search_down)

        self.search_label = ttk.Label(self.top_bar,
                                      width=10,
                                      font=('Segoe UI', 14),
                                      justify="center")

        self.search_icon = ttk.Label(self.top_bar, font=('Arial', 20), text="\u2315")

        self.search_label.pack(side="right", padx=1)
        self.search_bar.pack(side="right", padx=1)
        self.down_button.pack(side="right")
        self.up_button.pack(side="right")
        self.search_icon.pack(side="right", padx=4)

        self.default_bg = "#333333"
        self.default_fg = "#ffffff"
        
        self.window = PanedWindow(self.root, orient=HORIZONTAL, borderwidth=0, background="white")
        self.window.config(sashwidth=8, sashrelief="raised")
        self.window.pack(fill=BOTH)

        
        self.top_bar.pack(side="top")
        
        self.search_results = []
        self.search_result_index = 0

        self.init_workspace()
        
        self.treeview_panel = Frame(self.window)
        self.scroll_bar = ttk.Scrollbar(self.treeview_panel, orient=VERTICAL)
        self.treeview = ttk.Treeview(self.treeview_panel, columns=("type",), height=WINDOW_HEIGHT-100)
        self.scroll_bar.pack(side="right", pady=8, fill="y", padx=(0, 10))
        self.treeview.pack(side="right", padx=8, pady=8, fill="x", expand=True)
        self.treeview.heading("#0", text="File")
        self.treeview.column("#0", width=250)
        self.treeview.column("type", width=100)
        self.treeview.heading("type", text="Type")
        self.treeview.configure(yscrollcommand=self.scroll_bar.set)
        self.treeview.bind("<<TreeviewSelect>>", self.show_info_window)
        self.treeview.bind("<Double-Button-1>", self.treeview_on_double_click)
        self.treeview.bind("<Return>", self.treeview_on_double_click)
        self.scroll_bar['command'] = self.treeview.yview

        self.entry_info_panel = Frame(self.window, width=int(WINDOW_WIDTH/3))
        self.entry_info_panel.pack(side="left", fill="both", padx=8, pady=8)
        
        self.audio_info_panel = AudioSourceWindow(self.entry_info_panel,
                                                  self.play_audio,
                                                  self.check_modified)
        self.event_info_panel = EventWindow(self.entry_info_panel,
                                            self.check_modified)
        self.string_info_panel = StringEntryWindow(self.entry_info_panel,
                                                   self.check_modified)
        self.segment_info_panel = MusicSegmentWindow(self.entry_info_panel,
                                                     self.check_modified)
                                                     
        self.track_info_panel = MusicTrackWindow(self.entry_info_panel, self.check_modified)
                                                     
        self.window.add(self.treeview_panel)
        self.window.add(self.entry_info_panel)
        
        self.root.title("Helldivers 2 Audio Modder")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        
        self.right_click_menu = Menu(self.treeview, tearoff=0)
        self.right_click_id = 0

        self.menu = Menu(self.root, tearoff=0)
        
        self.selected_view = StringVar()
        self.selected_view.set("SourceView")
        self.view_menu = Menu(self.menu, tearoff=0)
        self.view_menu.add_radiobutton(label="Sources", variable=self.selected_view, value="SourceView", command=self.create_source_view)
        self.view_menu.add_radiobutton(label="Hierarchy", variable=self.selected_view, value="HierarchyView", command=self.create_hierarchy_view)
        
        self.selected_language = StringVar()
        self.options_menu = Menu(self.menu, tearoff=0)
        
        self.selected_theme = StringVar()
        self.selected_theme.set(self.app_state.theme)
        self.set_theme()
        self.theme_menu = Menu(self.menu, tearoff=0)
        self.theme_menu.add_radiobutton(label="Dark Mode", variable=self.selected_theme, value="dark_mode", command=self.set_theme)
        self.theme_menu.add_radiobutton(label="Light Mode", variable=self.selected_theme, value="light_mode", command=self.set_theme)
        self.options_menu.add_cascade(menu=self.theme_menu, label="Set Theme")
        
        self.language_menu = Menu(self.options_menu, tearoff=0)
        
        self.file_menu = Menu(self.menu, tearoff=0)

        self.recent_file_menu = Menu(self.file_menu, tearoff=0)

        self.load_archive_menu = Menu(self.menu, tearoff=0)
        if os.path.exists(GAME_FILE_LOCATION):
            self.load_archive_menu.add_command(
                label="From HD2 Data Folder",
                command=lambda: self.load_archive(initialdir=self.app_state.game_data_path)
            )
        self.load_archive_menu.add_command(
            label="From File Explorer",
            command=self.load_archive
        )

        for item in reversed(self.app_state.recent_files):
            item = os.path.normpath(item)
            self.recent_file_menu.add_command(
                label=item,
                command=partial(self.load_archive, "", item)
            )

        self.import_menu = Menu(self.menu, tearoff=0)
        self.import_menu.add_command(
            label="Import Patch File",
            command=self.import_patch
        )
        self.import_menu.add_command(
            label="Import Audio Files",
            command=self.import_audio_files
        )
        self.import_menu.add_command(
            label="Import using spec.json (.wem)",
            command=lambda: self.mod_handler.get_active_mod().import_wems_spec() or 
                self.check_modified()
        )
        if os.path.exists(WWISE_CLI):
            self.import_menu.add_command(
                label="Import using spec.json (.wav)",
                command=lambda: self.mod_handler.get_active_mod().load_convert_spec() or 
                    self.check_modified()
            )
            
        self.file_menu.add_cascade(
            menu=self.load_archive_menu, 
            label="Open"
        )
        self.file_menu.add_cascade(
            menu=self.recent_file_menu,
            label="Open Recent"
        )
        self.file_menu.add_cascade(
            menu=self.import_menu,
            label="Import"
        )
        
        self.file_menu.add_command(label="Combine Mods", command=self.combine_mods)
        
        self.file_menu.add_command(label="Save", command=self.save_mod)
        self.file_menu.add_command(label="Write Patch", command=self.write_patch)
        
        self.file_menu.add_command(label="Add a Folder to Workspace",
                                   command=self.add_new_workspace)
        
        self.edit_menu = Menu(self.menu, tearoff=0)
        self.edit_menu.add_command(label="Revert All Changes", command=self.revert_all)
        
        self.dump_menu = Menu(self.menu, tearoff=0)
        if os.path.exists(VGMSTREAM):
            self.dump_menu.add_command(label="Dump all as .wav", command=self.dump_all_as_wav)
        self.dump_menu.add_command(label="Dump all as .wem", command=self.dump_all_as_wem)
        
        self.menu.add_cascade(label="File", menu=self.file_menu)
        self.menu.add_cascade(label="Edit", menu=self.edit_menu)
        self.menu.add_cascade(label="Dump", menu=self.dump_menu)
        self.menu.add_cascade(label="View", menu=self.view_menu)
        self.menu.add_cascade(label="Options", menu=self.options_menu)
        self.root.config(menu=self.menu)
        
        self.treeview.drop_target_register(DND_FILES)
        self.workspace.drop_target_register(DND_FILES)
        self.workspace.drag_source_register(1, DND_FILES)

        self.treeview.bind("<Button-3>", self.treeview_on_right_click)
        self.workspace.bind("<Button-3>", self.workspace_on_right_click)
        self.workspace.bind("<Double-Button-1>", self.workspace_on_double_click)
        self.search_bar.bind("<Return>", self.search_bar_on_enter_key)
        self.treeview.dnd_bind("<<Drop>>", self.drop_import)
        self.treeview.dnd_bind("<<DropPosition>>", self.drop_position)
        self.workspace.dnd_bind("<<Drop>>", self.drop_add_to_workspace)
        self.workspace.dnd_bind("<<DragInitCmd>>", self.drag_init_workspace)
        self.workspace.bind("<B1-Motion>", self.workspace_drag_assist)
        self.workspace.bind("<Button-1>", self.workspace_save_selection)

        self.root.resizable(True, True)
        self.root.mainloop()
        
    def drop_position(self, event):
        if event.data:
            if len(event.widget.tk.splitlist(event.data)) != 1:
                return
        self.treeview.selection_set(event.widget.identify_row(event.y_root - self.treeview.winfo_rooty()))

    def workspace_drag_assist(self, event):
        selected_item = self.workspace.identify_row(event.y)
        if selected_item in self.workspace_selection:
            self.workspace.selection_set(self.workspace_selection)

    def workspace_save_selection(self, event):
        self.workspace_selection = self.workspace.selection()
        
    def combine_mods(self):
        mod_files = filedialog.askopenfilenames(title="Choose mod files to combine")
        if mod_files:
            combined_mod = self.mod_handler.create_new_mod("combined_mods_temp")
            combined_mod.load_archive_file(mod_files[0])
            for mod in mod_files[1:]:
                combined_mod.load_archive_file(mod)
                combined_mod.import_patch(mod)
            self.save_mod()
            self.mod_handler.delete_mod("combined_mods_temp")

    def drop_import(self, event):
        self.drag_source_widget = None
        renamed = False
        old_name = ""
        if event.data:
            import_files = []
            dropped_files = event.widget.tk.splitlist(event.data)
            for file in dropped_files:
                import_files.extend(list_files_recursive(file))
            if os.path.exists(WWISE_CLI):
                import_files = [file for file in import_files if os.path.splitext(file)[1] in SUPPORTED_AUDIO_TYPES or ".patch_" in os.path.basename(file)]
            else:
                import_files = [file for file in import_files if os.path.splitext(file)[1] == ".wem" or ".patch_" in os.path.basename(file)]
            if (
                len(import_files) == 1 
                and os.path.splitext(import_files[0])[1] in SUPPORTED_AUDIO_TYPES
                and self.treeview.item(event.widget.identify_row(event.y_root - self.treeview.winfo_rooty()), option="values")
                and self.treeview.item(event.widget.identify_row(event.y_root - self.treeview.winfo_rooty()), option="values")[0] == "Audio Source"
            ):
                audio_id = get_number_prefix(os.path.basename(import_files[0]))
                if audio_id != 0 and self.mod_handler.get_active_mod().get_audio_source(audio_id) is not None:
                    answer = askyesnocancel(title="Import", message="There is a file with the same name, would you like to replace that instead?")
                    if answer is None:
                        return
                    if not answer:
                        targets = [int(self.treeview.item(event.widget.identify_row(event.y_root - self.treeview.winfo_rooty()), option='tags')[0])]
                    else:
                        targets = [audio_id]
                else:
                    targets = [int(self.treeview.item(event.widget.identify_row(event.y_root - self.treeview.winfo_rooty()), option='tags')[0])]
                file_dict = {import_files[0]: targets}
            else:
                file_dict = {file: [get_number_prefix(os.path.basename(file))] for file in import_files}
            self.import_files(file_dict)

    def drop_add_to_workspace(self, event):
        if self.drag_source_widget is not self.workspace and event.data:
            dropped_files = event.widget.tk.splitlist(event.data)
            for file in dropped_files:
                if os.path.isdir(file):
                    self.add_new_workspace(file)
        self.drag_source_widget = None

    def drag_init_workspace(self, event):
        self.drag_source_widget = self.workspace
        data = ()
        if self.workspace.selection():
            data = tuple([self.workspace.item(i, option="values")[0] for i in self.workspace.selection()])
        return ((ASK, COPY), (DND_FILES,), data)

    def search_bar_on_enter_key(self, event):
        self.search()
        
    def set_theme(self):
        theme = self.selected_theme.get()
        try:
            if theme == "dark_mode":
                self.root.tk.call("set_theme", "dark")
                self.window.configure(background="white")
            elif theme == "light_mode":
                self.root.tk.call("set_theme", "light")
                self.window.configure(background="black")
        except Exception as e:
            logger.error(f"Error occurred when loading themes: {e}. Ensure azure.tcl and the themes folder are in the same folder as the executable")
        self.app_state.theme = theme
        self.workspace.column("#0", width=256+16)
        self.treeview.column("#0", width=250)
        self.treeview.column("type", width=100)
        self.check_modified()
        
    def get_colors(self, modified=False):
        theme = self.selected_theme.get()
        if theme == "dark_mode":
            if modified:
                return (MainWindow.dark_mode_modified_bg, MainWindow.dark_mode_modified_fg)
            else:
                return (MainWindow.dark_mode_bg, MainWindow.dark_mode_fg)
        elif theme == "light_mode":
            if modified:
                return (MainWindow.light_mode_modified_bg, MainWindow.light_mode_modified_fg)
            else:
                return (MainWindow.light_mode_bg, MainWindow.light_mode_fg)

    def render_workspace(self):
        """
        TO-DO: This should be fine grained diffing instead of tearing the entire
        thing down despite Tkinter already perform some type of rendering and
        display optimization behind the scene.
        """
        self.workspace_inodes.clear()

        for p in sorted(self.app_state.get_workspace_paths()):
            inode = fileutil.generate_file_tree(p)
            if inode != None:
                self.workspace_inodes.append(inode)

        for c in self.workspace.get_children():
            self.workspace.delete(c)

        for root_inode in self.workspace_inodes:
            root_id = self.workspace.insert("", "end", 
                                            text=root_inode.basename,
                                            values=[root_inode.absolute_path],
                                            tags="workspace")
            inode_stack = [root_inode]
            id_stack = [root_id]
            while len(inode_stack) > 0:
                top_inode = inode_stack.pop()
                top_id = id_stack.pop()
                for node in top_inode.nodes:
                    id = self.workspace.insert(top_id, "end", 
                                               text=node.basename,
                                               values=[node.absolute_path],
                                               tags="dir" if node.isdir else "file")
                    if node.isdir:
                        inode_stack.append(node)
                        id_stack.append(id)

    def add_new_workspace(self, workspace_path=""):
        if workspace_path == "":
            workspace_path = filedialog.askdirectory(
                mustexist=True,
                title="Select a folder to open as workspace"
            )
        if self.app_state.add_new_workspace(workspace_path) == 1:
            return
        inode = fileutil.generate_file_tree(workspace_path)
        if inode == None:
            return
        self.workspace_inodes.append(inode)
        idx = sorted(self.app_state.get_workspace_paths()).index(workspace_path)
        root_id = self.workspace.insert("", idx,
                                            text=inode.basename,
                                            values=[inode.absolute_path],
                                            tags="workspace")
        inode_stack = [inode]
        id_stack = [root_id]
        while len(inode_stack) > 0:
            top_inode = inode_stack.pop()
            top_id = id_stack.pop()
            for node in top_inode.nodes:
                id = self.workspace.insert(top_id, "end",
                                           text=node.basename,
                                           values=[node.absolute_path],
                                           tags="dir" if node.isdir else "file")
                if node.isdir:
                    inode_stack.append(node)
                    id_stack.append(id)
                    
        # I'm too lazy so I'm just going to unschedule and then reschedule all the watches
        # instead of locating all subfolders and then figuring out which ones to not schedule
        self.reload_watched_paths()
            
    def reload_watched_paths(self):
        for p in self.watched_paths:
            self.observer.unschedule(p)
        self.watched_paths = []
        # only track top-most folder if subfolders are added:
        # sort by number of levels
        paths = [pathlib.Path(p) for p in self.app_state.get_workspace_paths()]
        paths = sorted(paths, key=cmp_to_key(lambda item1, item2: len(item1.parents) - len(item2.parents)))

        # skip adding a folder if a parent folder has already been added
        trimmed_paths = []
        for p in paths:
            add = True
            for item in trimmed_paths:
                if item in p.parents:
                    add = False
                    break
            if add:
                trimmed_paths.append(p)
                
        for path in trimmed_paths:
            self.watched_paths.append(self.observer.schedule(self.event_handler, path, recursive=True))

    def remove_workspace(self, workspace_item):
        values = self.workspace.item(workspace_item, option="values")
        self.app_state.workspace_paths.remove(values[0])
        self.workspace.delete(workspace_item)

        # I'm too lazy so I'm just going to unschedule and then reschedule all the watches
        # instead of locating all subfolders and then figuring out which ones to not schedule
        self.reload_watched_paths()

    def workspace_on_right_click(self, event):
        self.workspace_popup_menu.delete(0, "end")
        selects: tuple[str, ...] = self.workspace.selection()
        if len(selects) == 0:
            return
        if len(selects) == 1:
            select = selects[0]
            tags = self.workspace.item(select, option="tags")
            assert(tags != '' and len(tags) == 1)
            if tags[0] == "workspace":
                values = self.workspace.item(select, option="values")
                assert(values != '' and len(values) == 1)
                self.workspace_popup_menu.add_command(
                    label="Remove Folder from Workspace",
                    command=lambda: self.remove_workspace(select),
                )
                self.workspace_popup_menu.tk_popup(
                    event.x_root, event.y_root
                )
                self.workspace_popup_menu.grab_release()
                return
            elif tags[0] == "dir":
                return
            elif tags[0] == "file":
                values = self.workspace.item(select, option="values")
                assert(values != '' and len(values) == 1)
                if "patch" in os.path.splitext(values[0])[1] and os.path.exists(values[0]):
                    self.workspace_popup_menu.add_command(
                        label="Open",
                        command=lambda: self.load_archive(archive_file=values[0]),
                    )
        file_dict = {self.workspace.item(i, option="values")[0]: [get_number_prefix(os.path.basename(self.workspace.item(i, option="values")[0]))] for i in selects if self.workspace.item(i, option="tags")[0] == "file"} 
        self.workspace_popup_menu.add_command(
            label="Import", 
            command=lambda: self.import_files(file_dict)
        )
        self.workspace_popup_menu.tk_popup(event.x_root, event.y_root)
        self.workspace_popup_menu.grab_release()
        
    def import_audio_files(self):
        
        if os.path.exists(WWISE_CLI):
            available_filetypes = [("Audio Files", " ".join(SUPPORTED_AUDIO_TYPES))]
        else:
            available_filetypes = [("Wwise Vorbis", "*.wem")]
        files = filedialog.askopenfilenames(title="Choose files to import", filetypes=available_filetypes)
        if not files:
            return
        file_dict = {file: [get_number_prefix(os.path.basename(file))] for file in files}
        self.import_files(file_dict)
        
    def import_files(self, file_dict):
        self.mod_handler.get_active_mod().import_files(file_dict)
        self.check_modified()
        self.show_info_window()

    def init_workspace(self):
        self.workspace_panel = Frame(self.window)
        self.window.add(self.workspace_panel)
        self.workspace = ttk.Treeview(self.workspace_panel, height=WINDOW_HEIGHT - 100)
        self.workspace.heading("#0", text="Workspace Folders")
        self.workspace.column("#0", width=256+16)
        self.workspace_scroll_bar = ttk.Scrollbar(self.workspace_panel, orient=VERTICAL)
        self.workspace_scroll_bar['command'] = self.workspace.yview
        self.workspace_scroll_bar.pack(side="right", pady=8, fill="y", padx=(0, 10))
        self.workspace.pack(side="right", padx=8, pady=8, fill="x", expand=True)
        self.workspace_inodes: list[fileutil.INode] = []
        self.workspace_popup_menu = Menu(self.workspace, tearoff=0)
        self.workspace.configure(yscrollcommand=self.workspace_scroll_bar.set)
        self.render_workspace()
        self.event_handler = WorkspaceEventHandler(self.workspace)
        self.observer = Observer()
        self.reload_watched_paths()
        self.observer.start()

    def init_archive_search_bar(self):
        if self.lookup_store == None:
            logger.critical("Audio archive database connection is None after \
                    bypassing all check.", stack_info=True)
            return
        archives = self.lookup_store.query_helldiver_audio_archive()
        entries: dict[str, str] = {
                archive.audio_archive_id: archive.audio_archive_name 
                for archive in archives}
        self.archive_search = ArchiveSearch("{1} || {0}", 
                                            entries=entries,
                                            on_select_cb=self.on_archive_search_bar_return,
                                            master=self.top_bar,
                                            width=64)
        categories = self.lookup_store.query_helldiver_audio_archive_category()
        categories = [""] + categories
        self.category_search = ttk.Combobox(self.top_bar,
                                            state="readonly",
                                            font=('Segoe UI', 10),
                                            width=18, height=10,
                                            values=categories) 
        self.archive_search.pack(side="left", padx=4, pady=8)
        self.category_search.pack(side="left", padx=4, pady=8)
        self.category_search.bind("<<ComboboxSelected>>",
                                  self.on_category_search_bar_select)

    def on_archive_search_bar_return(self, value: str):
        splits = value.split(" || ")
        if len(splits) != 2:
            logger.critical("Something went wrong with the archive search \
                    autocomplete.", stack_info=True)
            return
        archive_file = os.path.join(self.app_state.game_data_path, splits[1])
        self.load_archive(initialdir="", archive_file=archive_file)

    def on_category_search_bar_select(self, event):
        if self.lookup_store == None:
            logger.critical("Audio archive database connection is None after \
                    bypassing all check.", stack_info=True)
            return
        category: str = self.category_search.get()
        archives = self.lookup_store.query_helldiver_audio_archive(category)
        entries: dict[str, str] = {
                archive.audio_archive_id: archive.audio_archive_name 
                for archive in archives
        }
        self.archive_search.set_entries(entries)
        self.archive_search.focus_set()
        self.category_search.selection_clear()
        
    def targeted_import(self, targets):
        if os.path.exists(WWISE_CLI):
            available_filetypes = [("Audio Files", " ".join(SUPPORTED_AUDIO_TYPES))]
        else:
            available_filetypes = [("Wwise Vorbis", "*.wem")]
        filename = askopenfilename(title="Select audio file to import", filetypes=available_filetypes)
        if not filename or not os.path.exists(filename):
            return
        file_dict = {filename: targets}
        self.import_files(file_dict)
        
    def remove_game_archive(self, archive_name):
        self.mod_handler.get_active_mod().remove_game_archive(archive_name)
        if self.selected_view.get() == "SourceView":
            self.create_source_view()
        else:
            self.create_hierarchy_view()
        

    def treeview_on_right_click(self, event):
        try:
            self.right_click_menu.delete(0, "end")

            selects = self.treeview.selection()
            is_single = len(selects) == 1

            all_audio = True
            for select in selects:
                values = self.treeview.item(select, option="values")
                assert(len(values) == 1)
                if values[0] != "Audio Source":
                    all_audio = False
                    break

            self.right_click_menu.add_command(
                label=("Copy File ID" if is_single else "Copy File IDs"),
                command=self.copy_id
            )
            if is_single and self.treeview.item(self.treeview.selection()[0], option="values")[0] == "Archive File":
                self.right_click_menu.add_command(
                    label="Remove Archive",
                    command=lambda: self.remove_game_archive(self.treeview.item(self.treeview.selection()[0], option="tags")[0])
                )

            if all_audio:
                self.right_click_menu.add_command(
                    label="Import audio",
                    command=lambda: self.targeted_import(targets=[int(self.treeview.item(select, option="tags")[0]) for select in selects])
                )

                tags = self.treeview.item(selects[-1], option="tags")
                assert(len(tags) == 1)
                self.right_click_id = int(tags[0])
                
                self.right_click_menu.add_command(
                    label=("Dump As .wem" if is_single else "Dump Selected As .wem"),
                    command=self.dump_as_wem
                )
                if os.path.exists(VGMSTREAM):
                    self.right_click_menu.add_command(
                        label=("Dump As .wav" if is_single else "Dump Selected As .wav"),
                        command=self.dump_as_wav,
                    )
                    self.right_click_menu.add_command(
                        label="Dump As .wav with Sequence Number",
                        command=lambda: self.dump_as_wav(with_seq=True)
                    )
                self.right_click_menu.add_command(
                    label="Dump muted .wav with same ID",
                    command=lambda: self.dump_as_wav(muted=True)
                )
                self.right_click_menu.add_command(
                    label="Dump muted .wav with same ID and sequence number",
                    command=lambda: self.dump_as_wav(muted=True, with_seq=True)
                )
            self.right_click_menu.tk_popup(event.x_root, event.y_root)
        except (AttributeError, IndexError):
            pass
        finally:
            self.right_click_menu.grab_release()

    def treeview_on_double_click(self, event):
        """
        It work as before but it's setup for playing multiple selected .wem 
        files I'm planning to implement. For now, it will be overhead since 
        there's extra code need to be loaded into the memory and interpreted.
        """
        # Rewrite this part against the doc how to use .item(). Provide better 
        # LSP type hinting
        selects = self.treeview.selection() 
        for select in selects:
            values = self.treeview.item(select, option="values")
            tags = self.treeview.item(select, option="tags")
            assert(len(values) == 1 and len(tags) == 1)
            if values[0] != "Audio Source":
                continue
            self.play_audio(int(tags[0]))

    def workspace_on_double_click(self, event):
        selects = self.workspace.selection()
        if len(selects) == 1:
            select = selects[0]
            values = self.workspace.item(select, option="values")
            tags = self.workspace.item(select, option="tags")
            assert(len(values) == 1 and len(tags) == 1)
            if tags[0] == "file" and os.path.splitext(values[0])[1] == ".wem" and os.path.exists(values[0]):
                audio_data = None
                with open(values[0], "rb") as f:
                    audio_data = f.read()
                self.sound_handler.play_audio(os.path.basename(os.path.splitext(values[0])[0]), audio_data)

    def set_language(self):
        global language
        old_language = language
        language = language_lookup(self.selected_language.get())
        if language != old_language:
            if self.selected_view.get() == "SourceView":
                self.create_source_view()
            else:
                self.create_hierarchy_view()
    
    def search_down(self):
        if len(self.search_results) > 0:
            self.search_result_index += 1
            if self.search_result_index == len(self.search_results):
                self.search_result_index = 0
            self.treeview.selection_set(self.search_results[self.search_result_index])
            self.treeview.see(self.search_results[self.search_result_index])
            self.search_label['text'] = f"{self.search_result_index+1}/{len(self.search_results)}"

    def search_up(self):
        if len(self.search_results) > 0:
            self.search_result_index -= 1
            if self.search_result_index == -1:
                self.search_result_index = len(self.search_results)-1
            self.treeview.selection_set(self.search_results[self.search_result_index])
            self.treeview.see(self.search_results[self.search_result_index])
            self.search_label['text'] = f"{self.search_result_index+1}/{len(self.search_results)}"

    def show_info_window(self, event=None):
        if len(self.treeview.selection()) != 1:
            return
        selection_type = self.treeview.item(self.treeview.selection(), option="values")[0]
        if selection_type == "Archive File":
            return
        selection_id = int(self.treeview.item(self.treeview.selection(), option="tags")[0])
        item = self.treeview.selection()[0]
        while self.treeview.parent(self.treeview.parent(item)):
            item = self.treeview.parent(item)
        bank_id = int(self.treeview.item(item, option="tags")[0])
        for child in self.entry_info_panel.winfo_children():
            child.forget()
        if selection_type == "String":
            self.string_info_panel.set_string_entry(self.mod_handler.get_active_mod().get_string_entry(bank_id, selection_id))
            self.string_info_panel.frame.pack()
        elif selection_type == "Audio Source":
            self.audio_info_panel.set_audio(self.mod_handler.get_active_mod().get_audio_source(selection_id))
            self.audio_info_panel.frame.pack()
        elif selection_type == "Event":
            self.event_info_panel.set_track_info(self.mod_handler.get_active_mod().get_hierarchy_entry(bank_id, selection_id))
            self.event_info_panel.frame.pack()
        elif selection_type == "Music Segment":
            self.segment_info_panel.set_segment_info(self.mod_handler.get_active_mod().get_hierarchy_entry(bank_id, selection_id))
            self.segment_info_panel.frame.pack()
        elif selection_type == "Music Track":
            self.track_info_panel.set_track(self.mod_handler.get_active_mod().get_hierarchy_entry(bank_id, selection_id))
            self.track_info_panel.frame.pack()
        elif selection_type == "Sound Bank":
            pass
        elif selection_type == "Text Bank":
            pass

    def copy_id(self):
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join([self.treeview.item(i, option="tags")[0] for i in self.treeview.selection()]))
        self.root.update()

    def dump_as_wem(self):
        output_file = filedialog.asksaveasfile(mode='wb', title="Save As", initialfile=(str(file_id)+".wem"), defaultextension=".wem", filetypes=[("Wwise Audio", "*.wem")])
        if not output_file:
            return
        if len(self.treeview.selection()) == 1:
            self.mod_handler.get_active_mod().dump_as_wem(self.right_click_id, output_file)
        else:
            self.mod_handler.get_active_mod().dump_multiple_as_wem([int(self.treeview.item(i, option="tags")[0]) for i in self.treeview.selection()])

    def dump_as_wav(self, muted: bool = False, with_seq: int = False):
        output_file = filedialog.asksaveasfilename(
            title="Save As", 
            initialfile=f"{file_id}.wav", 
            defaultextension=".wav", 
            filetypes=[("Wav Audio", "*.wav")]
        )
        if not output_file:
            return
        if len(self.treeview.selection()) == 1:
            self.mod_handler.get_active_mod().dump_as_wav(self.right_click_id, output_file=output_file, muted=muted)
            return
        self.mod_handler.get_active_mod().dump_multiple_as_wav(
            [int(self.treeview.item(i, option="tags")[0]) for i in self.treeview.selection()],
            muted=muted,
            with_seq=with_seq
        )

    def create_treeview_entry(self, entry, parent_item=""): #if HircEntry, add id of parent bank to the tags
        if entry is None: return
        if isinstance(entry, GameArchive):
            tree_entry = self.treeview.insert(parent_item, END, tag=entry.name)
        else:
            tree_entry = self.treeview.insert(parent_item, END, tag=entry.get_id())
        if isinstance(entry, WwiseBank):
            name = entry.dep.data.split('/')[-1]
            entry_type = "Sound Bank"
        elif isinstance(entry, TextBank):
            name = f"{entry.get_id()}.text"
            entry_type = "Text Bank"
        elif isinstance(entry, AudioSource):
            name = f"{entry.get_id()}.wem"
            entry_type = "Audio Source"
        elif isinstance(entry, TrackInfoStruct):
            name = f"Event {entry.get_id()}"
            entry_type = "Event"
        elif isinstance(entry, StringEntry):
            entry_type = "String"
            name = entry.get_text()[:20]
        elif isinstance(entry, MusicTrack):
            entry_type = "Music Track"
            name = f"Track {entry.get_id()}"
        elif isinstance(entry, MusicSegment):
            entry_type = "Music Segment"
            name = f"Segment {entry.get_id()}"
        elif isinstance(entry, RandomSequenceContainer):
            entry_type = "Random Sequence"
            name = f"Sequence {entry.get_id()}"
        elif isinstance(entry, GameArchive):
            name = entry.name
            entry_type = "Archive File"
            self.treeview.item(tree_entry, open=True)
        self.treeview.item(tree_entry, text=name)
        self.treeview.item(tree_entry, values=(entry_type,))
        return tree_entry
        
    def clear_search(self):
        self.search_result_index = 0
        self.search_results.clear()
        self.search_label['text'] = ""
        self.search_text_var.set("")
            
    def create_hierarchy_view(self):
        self.clear_search()
        self.treeview.delete(*self.treeview.get_children())
        bank_dict = self.mod_handler.get_active_mod().get_wwise_banks()
        game_archives = self.mod_handler.get_active_mod().get_game_archives()
        sequence_sources = set()
        for archive in game_archives.values():
            archive_entry = self.create_treeview_entry(archive)
            for bank in archive.wwise_banks.values():
                bank_entry = self.create_treeview_entry(bank, archive_entry)
                for hierarchy_entry in bank.hierarchy.entries.values():
                    if isinstance(hierarchy_entry, MusicSegment):
                        segment_entry = self.create_treeview_entry(hierarchy_entry, bank_entry)
                        for track_id in hierarchy_entry.tracks:
                            track = bank.hierarchy.entries[track_id]
                            track_entry = self.create_treeview_entry(track, segment_entry)
                            for source in track.sources:
                                if source.plugin_id == VORBIS:
                                    try:
                                        self.create_treeview_entry(self.mod_handler.get_active_mod().get_audio_source(source.source_id), track_entry)
                                    except:
                                        pass
                            for info in track.track_info:
                                if info.event_id != 0:
                                    self.create_treeview_entry(info, track_entry)
                    elif isinstance(hierarchy_entry, RandomSequenceContainer):
                        container_entry = self.create_treeview_entry(hierarchy_entry, bank_entry)
                        for s_id in hierarchy_entry.contents:
                            sound = bank.hierarchy.entries[s_id]
                            if len(sound.sources) > 0 and sound.sources[0].plugin_id == VORBIS:
                                sequence_sources.add(sound)
                                try:
                                    self.create_treeview_entry(self.mod_handler.get_active_mod().get_audio_source(sound.sources[0].source_id), container_entry)
                                except:
                                    pass
                for hierarchy_entry in bank.hierarchy.entries.values():
                    if isinstance(hierarchy_entry, Sound) and hierarchy_entry not in sequence_sources:
                        if hierarchy_entry.sources[0].plugin_id == VORBIS:
                            try:
                                self.create_treeview_entry(self.mod_handler.get_active_mod().get_audio_source(hierarchy_entry.sources[0].source_id), bank_entry)
                            except:
                                pass
            for text_bank in archive.text_banks.values():
                if text_bank.language == language:
                    bank_entry = self.create_treeview_entry(text_bank, archive_entry)
                    for string_entry in text_bank.entries.values():
                        self.create_treeview_entry(string_entry, bank_entry)
        self.check_modified()
                
    def create_source_view(self):
        self.clear_search()
        existing_sources = set()
        self.treeview.delete(*self.treeview.get_children())
        game_archives = self.mod_handler.get_active_mod().get_game_archives()
        for archive in game_archives.values():
            archive_entry = self.create_treeview_entry(archive)
            for bank in archive.wwise_banks.values():
                existing_sources.clear()
                bank_entry = self.create_treeview_entry(bank, archive_entry)
                for hierarchy_entry in bank.hierarchy.entries.values():
                    for source in hierarchy_entry.sources:
                        if source.plugin_id == VORBIS and source.source_id not in existing_sources:
                            existing_sources.add(source.source_id)
                            try:
                                self.create_treeview_entry(self.mod_handler.get_active_mod().get_audio_source(source.source_id), bank_entry)
                            except:
                                pass
            for text_bank in archive.text_banks.values():
                if text_bank.language == language:
                    bank_entry = self.create_treeview_entry(text_bank, archive_entry)
                    for string_entry in text_bank.entries.values():
                        self.create_treeview_entry(string_entry, bank_entry)
        self.check_modified()
                
    def recursive_match(self, search_text_var, item):
        if self.treeview.item(item, option="values")[0] == "String":
            string_entry = self.mod_handler.get_active_mod().get_string_entry(int(self.treeview.item(item, option="tags")[0]))
            match = search_text_var in string_entry.get_text()
        else:
            s = self.treeview.item(item, option="text")
            match = s.startswith(search_text_var) or s.endswith(search_text_var)
        children = self.treeview.get_children(item)
        if match: self.search_results.append(item)
        if len(children) > 0:
            for child in children:
                self.recursive_match(search_text_var, child)

    def search(self):
        self.search_results.clear()
        self.search_result_index = 0
        text = self.search_text_var.get()
        if text != "":
            for child in self.treeview.get_children():
                self.recursive_match(text, child)
            if len(self.search_results) > 0:
                self.treeview.selection_set(self.search_results[self.search_result_index])
                self.treeview.see(self.search_results[self.search_result_index])
                self.search_label['text'] = f"1/{len(self.search_results)}"
            else:
                self.search_label['text'] = "0/0"
        else:
            self.search_label['text'] = ""

    def update_recent_files(self, filepath):
        try:
            self.app_state.recent_files.remove(os.path.normpath(filepath))
        except ValueError:
            pass
        self.app_state.recent_files.append(os.path.normpath(filepath))
        if len(self.app_state.recent_files) > 5:
            self.app_state.recent_files.pop(0)
        self.recent_file_menu.delete(0, "end")
        for item in reversed(self.app_state.recent_files):
            item = os.path.normpath(item)
            self.recent_file_menu.add_command(
                label=item,
                command=partial(self.load_archive, "", item)
            )

    def update_language_menu(self):
        self.options_menu.delete(1, "end") #change to delete only the language select menu
        if len(self.mod_handler.get_active_mod().text_banks) > 0:
            self.language_menu.delete(0, "end")
            first = ""
            self.options_menu.add_cascade(label="Game text language", menu=self.language_menu)
            for name, lang_id in LANGUAGE_MAPPING.items():
                if first == "": first = name
                for text_bank in self.mod_handler.get_active_mod().text_banks.values():
                    if lang_id == text_bank.language:
                        self.language_menu.add_radiobutton(label=name, variable=self.selected_language, value=name, command=self.set_language)
                        break
            self.selected_language.set(first)

    def load_archive(self, initialdir: str | None = '', archive_file: str | None = ""):
        if not archive_file:
            archive_file = askopenfilename(title="Select archive", initialdir=initialdir)
        if not archive_file:
            return
        self.sound_handler.kill_sound()
        if self.mod_handler.get_active_mod().load_archive_file(archive_file=archive_file):
            self.clear_search()
            self.update_language_menu()
            self.update_recent_files(filepath=archive_file)
            if self.selected_view.get() == "SourceView":
                self.create_source_view()
            else:
                self.create_hierarchy_view()
            for child in self.entry_info_panel.winfo_children():
                child.forget()
        else:
            for child in self.treeview.get_children():
                self.treeview.delete(child)

    def save_mod(self):
        output_folder = filedialog.askdirectory(title="Select location to save combined mod")
        if output_folder and os.path.exists(output_folder):
            self.sound_handler.kill_sound()
            self.mod_handler.get_active_mod().save(output_folder)

    def clear_treeview_background(self, item):
        bg_color, fg_color = self.get_colors()
        self.treeview.tag_configure(self.treeview.item(item)['tags'][0],
                                    background=bg_color,
                                    foreground=fg_color)
        for child in self.treeview.get_children(item):
            self.clear_treeview_background(child)
        
    """
    TO-DO:
    optimization point: small, but noticeable lag if there are many, many 
    entries in the tree
    """
    def check_modified(self): 
        for child in self.treeview.get_children():
            self.clear_treeview_background(child)
        bg: Any
        fg: Any
        for bank in self.mod_handler.get_active_mod().wwise_banks.values():
            bg, fg = self.get_colors(modified=bank.modified)
            self.treeview.tag_configure(bank.get_id(),
                                        background=bg,
                                        foreground=fg)
            for entry in bank.hierarchy.get_entries():
                is_modified = entry.modified or entry.has_modified_children()
                bg, fg = self.get_colors(modified=is_modified)
                self.treeview.tag_configure(entry.get_id(),
                                        background=bg,
                                        foreground=fg)
        for audio in self.mod_handler.get_active_mod().get_audio_sources().values():
            is_modified = audio.modified
            bg, fg = self.get_colors(modified=is_modified)
            self.treeview.tag_configure(audio.get_id(),
                                        background=bg,
                                        foreground=fg)
                    
        for text_bank in self.mod_handler.get_active_mod().text_banks.values():
            bg, fg = self.get_colors(modified=text_bank.modified)
            self.treeview.tag_configure(text_bank.get_id(), 
                                            background=bg,
                                            foreground=fg)
            for entry in text_bank.entries.values():
                bg, fg = self.get_colors(modified=entry.modified)
                self.treeview.tag_configure(entry.get_id(),
                                        background=bg,
                                        foreground=fg)
        
    def dump_all_as_wem(self):
        self.sound_handler.kill_sound()
        output_folder = filedialog.askdirectory(title="Select folder to save files to")
        if not output_folder:
            return
        self.mod_handler.get_active_mod().dump_all_as_wem(output_folder)
        
    def dump_all_as_wav(self):
        self.sound_handler.kill_sound()
        output_folder = filedialog.askdirectory(title="Select folder to save files to")
        if not output_folder:
            return
        self.mod_handler.get_active_mod().dump_all_as_wav(output_folder)
        
    def play_audio(self, file_id: int, callback=None):
        audio = self.mod_handler.get_active_mod().get_audio_source(file_id)
        self.sound_handler.play_audio(audio.get_short_id(), audio.get_data(), callback)
        
    def revert_audio(self, file_id):
        self.mod_handler.get_active_mod().revert_audio(file_id)
        
    def revert_all(self):
        self.sound_handler.kill_sound()
        self.mod_handler.get_active_mod().revert_all()
        self.check_modified()
        self.show_info_window()
        
    def write_patch(self):
        self.sound_handler.kill_sound()
        output_folder = filedialog.askdirectory(title="Select folder to save files to")
        if not output_folder:
            return
        self.mod_handler.get_active_mod().write_patch(output_folder)
        
    def import_patch(self):
        self.sound_handler.kill_sound()
        archive_file = askopenfilename(title="Select patch file")
        if not archive_file:
            return
        if self.mod_handler.get_active_mod().import_patch(archive_file):
            self.check_modified()
            self.show_info_window()

if __name__ == "__main__":
    random.seed()
    app_state: cfg.Config | None = cfg.load_config()
    if app_state == None:
        exit(1)

    GAME_FILE_LOCATION = app_state.game_data_path

    try:
        if not os.path.exists(CACHE):
            os.mkdir(CACHE, mode=0o777)
    except Exception as e:
        showerror("Error when initiating application", 
                    "Failed to create application caching space")
        exit(1)

    SYSTEM = platform.system()
    if SYSTEM == "Windows":
        VGMSTREAM = "vgmstream-win64/vgmstream-cli.exe"
        FFMPEG = "ffmpeg.exe"
        try:
            WWISE_CLI = os.path.join(os.environ["WWISEROOT"],
                             "Authoring\\x64\\Release\\bin\\WwiseConsole.exe")
        except:
            pass
    elif SYSTEM == "Linux":
        VGMSTREAM = "vgmstream-linux/vgmstream-cli"
        FFMPEG = "ffmpeg"
        WWISE_CLI = ""
        showwarning(title="Unsupported", message="Wwise integration is not " \
            "supported for Linux. WAV file import is disabled")
    elif SYSTEM == "Darwin":
        VGMSTREAM = "vgmstream-macos/vgmstream-cli"
        FFMPEG = "ffmpeg"
        try:
            p = next(pathlib.Path("/Applications/Audiokinetic").glob("Wwise*"))
            WWISE_CLI = os.path.join(p, "Wwise.app/Contents/Tools/WwiseConsole.sh")
        except:
            pass
    
    if os.path.exists(WWISE_CLI):
        if "Wwise2024" in WWISE_CLI:
            WWISE_VERSION = "2024"
        elif "Wwise2023" in WWISE_CLI:
            WWISE_VERSION = "2023"
    else:
        WWISE_VERSION = ""
        
    if not os.path.exists(VGMSTREAM):
        logger.error("Cannot find vgmstream distribution! " \
                     f"Ensure the {os.path.dirname(VGMSTREAM)} folder is " \
                     "in the same folder as the executable")
        showwarning(title="Missing Plugin", message="Cannot find vgmstream distribution! " \
                    "Audio playback is disabled.")
                     
    if not os.path.exists(WWISE_CLI) and SYSTEM != "Linux":
        logger.warning("Wwise installation not found. WAV file import is disabled.")
        showwarning(title="Missing Plugin", message="Wwise installation not found. WAV file import is disabled.")
    
    if os.path.exists(WWISE_CLI) and not os.path.exists(DEFAULT_WWISE_PROJECT):
        process = subprocess.run([
            WWISE_CLI,
            "create-new-project",
            DEFAULT_WWISE_PROJECT,
            "--platform",
            "Windows",
            "--quiet",
        ])
        if process.returncode != 0:
            logger.error("Error creating Wwise project. Audio import restricted to .wem files only")
            showwarning(title="Wwise Error", message="Error creating Wwise project. Audio import restricted to .wem files only")
            WWISE_CLI = ""

    lookup_store: db.LookupStore | None = None
    
    if not os.path.exists(GAME_FILE_LOCATION):
        showwarning(title="Missing Game Data", message="No folder selected for Helldivers data folder." \
            " Audio archive search is disabled.")
    elif os.path.exists("hd_audio_db.db"):
        sqlite_initializer = db.config_sqlite_conn("hd_audio_db.db")
        try:
            lookup_store = db.SQLiteLookupStore(sqlite_initializer, logger)
        except Exception as err:
            logger.error("Failed to connect to audio archive database", 
                         stack_info=True)
            lookup_store = None
    else:
        logger.warning("Please ensure `hd_audio_db.db` is in the same folder as " \
                "the executable to enable built-in audio archive search.")
        logger.warning("Built-in audio archive search is disabled. " \
                "Please refer to the information in Google spreadsheet.")
        showwarning(title="Missing Plugin", message="Audio database not found. Audio archive search is disabled.")
        
    language = language_lookup("English (US)")
    window = MainWindow(app_state, lookup_store)
    
    app_state.save_config()

    if os.path.exists(CACHE):
        shutil.rmtree(CACHE)