from tkinter import *
from tkinter import ttk
from tkinter import filedialog
import os
import struct
from math import ceil
from pathlib import Path
import tkinter
from tkinter.filedialog import askdirectory
from tkinter.filedialog import askopenfilename
from functools import partial
import pyaudio
import wave
import subprocess
import atexit
from itertools import takewhile
import copy
import numpy
import platform

MUSIC_TRACK = 11
SOUND = 2
BANK = 0
PREFETCH_STREAM = 1
STREAM = 2
ROW_HEIGHT = 30
ROW_WIDTH = 800
SUBROW_INDENT = 30
WINDOW_WIDTH = 700
WINDOW_HEIGHT = 720
_GAME_FILE_LOCATION = ""
_DRIVE_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_LANGUAGE = 66681687
_LANGUAGE_MAPPING = {}

def LookForSteamInstallWindows():
    path = "C:\\Program Files (x86)\\steam\\steamapps\\common\\Helldivers 2\\data"
    if os.path.exists(path):
        return path
    for letter in _DRIVE_LETTERS:
        path = f"{letter}:\\SteamLibrary\\steamapps\\common\\Helldivers 2\\data"
        if os.path.exists(path):
            return path
    return ""
    
def LoadLanguageMapping():
    _LANGUAGE_MAPPING["English (US)"] = 0x03f97b57
    _LANGUAGE_MAPPING["English (UK)"] = 0x6f4515cb 
    
def LanguageLookup(langString):
    return _LANGUAGE_MAPPING[langString]
    
def StripPatchIndex(filename):
    split = filename.split(".")
    for n in range(len(split)):
        if "patch_" in split[n]:
            del split[n]
            break
    filename = ".".join(split)
    return filename

class MemoryStream:
    '''
    Modified from https://github.com/kboykboy2/io_scene_helldivers2 with permission from kboykboy
    '''
    def __init__(self, Data=b"", IOMode = "read"):
        self.Location = 0
        self.Data = bytearray(Data)
        self.IOMode = IOMode
        self.Endian = "<"

    def open(self, Data, IOMode = "read"): # Open Stream
        self.Data = bytearray(Data)
        self.IOMode = IOMode

    def SetReadMode(self):
        self.IOMode = "read"

    def SetWriteMode(self):
        self.IOMode = "write"

    def IsReading(self):
        return self.IOMode == "read"

    def IsWriting(self):
        return self.IOMode == "write"

    def seek(self, Location): # Go To Position In Stream
        self.Location = Location
        if self.Location > len(self.Data):
            missing_bytes = self.Location - len(self.Data)
            self.Data += bytearray(missing_bytes)

    def tell(self): # Get Position In Stream
        return self.Location

    def read(self, length=-1): # Read Bytes From Stream
        if length == -1:
            length = len(self.Data) - self.Location
        if self.Location + length > len(self.Data):
            raise Exception("reading past end of stream")

        newData = self.Data[self.Location:self.Location+length]
        self.Location += length
        return bytearray(newData)

    def write(self, bytes): # Write Bytes To Stream
        length = len(bytes)
        if self.Location + length > len(self.Data):
            missing_bytes = (self.Location + length) - len(self.Data)
            self.Data += bytearray(missing_bytes)
        self.Data[self.Location:self.Location+length] = bytearray(bytes)
        self.Location += length

    def read_format(self, format, size):
        format = self.Endian+format
        return struct.unpack(format, self.read(size))[0]
        
    def bytes(self, value, size = -1):
        if size == -1:
            size = len(value)
        if len(value) != size:
            value = bytearray(size)

        if self.IsReading():
            return bytearray(self.read(size))
        elif self.IsWriting():
            self.write(value)
            return bytearray(value)
        return value
        
    def int8Read(self):
        return self.read_format('b', 1)

    def uint8Read(self):
        return self.read_format('B', 1)

    def int16Read(self):
        return self.read_format('h', 2)

    def uint16Read(self):
        return self.read_format('H', 2)

    def int32Read(self):
        return self.read_format('i', 4)

    def uint32Read(self):
        return self.read_format('I', 4)

    def int64Read(self):
        return self.read_format('q', 8)

    def uint64Read(self):
        return self.read_format('Q', 8)
        
def PadTo16ByteAlign(data):
    b = bytearray(data)
    l = len(b)
    new_len = ceil(l/16)*16
    return b + bytearray(new_len-l)
    
def _16ByteAlign(addr):
    return ceil(addr/16)*16
    
def bytes_to_long(bytes):
    assert len(bytes) == 8
    return sum((b << (k * 8) for k, b in enumerate(bytes)))

def murmur64Hash(data, seed = 0):

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
        
    def Update(self, content):
        pass
        
    def RaiseModified(self):
        pass
        
    def LowerModified(self):
        pass
        
class TrackEvent:
    pass
    
class AudioSource:

    def __init__(self):
        self.Data = b""
        self.Size = 0
        self.resourceId = 0
        self.shortId = 0
        self.Modified = False
        self.Data_OLD = b""
        self.trackInfo_OLD = None
        self.Subscribers = set()
        self.streamType = 0
        self.trackInfo = None
        
    def SetData(self, data, notifySubscribers=True, setModified=True):
        if not self.Modified and setModified:
            self.Data_OLD = self.Data
        self.Data = data
        self.Size = len(self.Data)
        if notifySubscribers:
            for item in self.Subscribers:
                item.Update(self)
                if not self.Modified:
                    item.RaiseModified()
        if setModified:
            self.Modified = True
            
    def GetId(self): #for backwards compatibility
        if self.streamType == BANK:
            return self.GetShortId()
        else:
            return self.GetResourceId()
            
    def SetTrackInfo(self, trackInfo,  notifySubscribers=True, setModified=True):
        if not self.Modified and setModified:
            self.trackInfo_OLD = self.trackInfo
        self.trackInfo = trackInfo
        if notifySubscribers:
            for item in self.Subscribers:
                item.Update(self)
                if not self.Modified:
                    item.RaiseModified()
        if setModified:
            self.Modified = True
            
    def GetTrackInfo(self):
        return self.trackInfo
        
    def GetData(self):
        return self.Data
        
    def GetResourceId(self):
        return self.resourceId
        
    def GetShortId(self):
        return self.shortId
        
    def RevertModifications(self, notifySubscribers=True):
        if self.Modified:
            self.Modified = False
            if self.Data_OLD != b"":
                self.Data = self.Data_OLD
                self.Data_OLD = b""
            if self.trackInfo_OLD is not None:
                self.trackInfo = self.trackInfo_OLD
                self.trackInfo_OLD = None
            self.Size = len(self.Data)
            if notifySubscribers:
                for item in self.Subscribers:
                    item.LowerModified()
                    item.Update(self)
                
class TocHeader:

    def __init__(self):
        pass
        
    def FromMemoryStream(self, stream):
        self.FileID             = stream.uint64Read()
        self.TypeID             = stream.uint64Read()
        self.TocDataOffset      = stream.uint64Read()
        self.StreamOffset       = stream.uint64Read()
        self.GpuResourceOffset  = stream.uint64Read()
        self.Unknown1           = stream.uint64Read() #seems to contain duplicate entry index
        self.Unknown2           = stream.uint64Read()
        self.TocDataSize        = stream.uint32Read()
        self.StreamSize         = stream.uint32Read()
        self.GpuResourceSize    = stream.uint32Read()
        self.Unknown3           = stream.uint32Read()
        self.Unknown4           = stream.uint32Read()
        self.EntryIndex         = stream.uint32Read()
        
    def GetData(self):
        return (struct.pack("<QQQQQQQIIIIII",
            self.FileID,
            self.TypeID,
            self.TocDataOffset,
            self.StreamOffset,
            self.GpuResourceOffset,
            self.Unknown1,
            self.Unknown2,
            self.TocDataSize,
            self.StreamSize,
            self.GpuResourceSize,
            self.Unknown3,
            self.Unknown4,
            self.EntryIndex))
                
class WwiseDep:

    def __init__(self):
        self.Data = ""
        
    def FromMemoryStream(self, stream):
        self.Offset = stream.tell()
        self.Tag = stream.uint32Read()
        self.DataSize = stream.uint32Read()
        self.Data = stream.read(self.DataSize).decode('utf-8')
        
    def GetData(self):
        return (self.Tag.to_bytes(4, byteorder='little')
                + self.DataSize.to_bytes(4, byteorder='little')
                + self.Data.encode('utf-8'))
                
class DidxEntry:
    def __init__(self):
        self.id = self.offset = self.size = 0
        
    @classmethod
    def FromBytes(cls, bytes):
        e = DidxEntry()
        e.id, e.offset, e.size = struct.unpack("<III", bytes)
        return e
        
    def GetData(self):
        return struct.pack("<III", self.id, self.offset, self.size)
        
class MediaIndex:

    def __init__(self):
        self.entries = {}
        self.data = {}
        
    def Load(self, didxChunk, dataChunk):
        for n in range(int(len(didxChunk)/12)):
            entry = DidxEntry.FromBytes(didxChunk[12*n : 12*(n+1)])
            self.entries[entry.id] = entry
            self.data[entry.id] = dataChunk[entry.offset:entry.offset+entry.size]
        
    def GetData(self):
        arr = [x.GetData() for x in self.entries.values()]
        dataArr = self.data.values()
        return b"".join(arr) + b"".join(dataArr)
                
class HircEntry:
    
    def __init__(self):
        self.size = self.hType = self.hId = self.misc = 0
        self.sources = []
        self.trackInfo = []
    
    @classmethod
    def FromMemoryStream(cls, stream):
        entry = HircEntry()
        entry.hType = stream.uint8Read()
        entry.size = stream.uint32Read()
        entry.hId = stream.uint32Read()
        entry.misc = stream.read(entry.size - 4)
        return entry
        
    def GetId(self):
        return self.hId
        
    def GetData(self):
        return self.hType.to_bytes(1, byteorder="little") + self.size.to_bytes(4, byteorder="little") + self.hId.to_bytes(4, byteorder="little") + self.misc
        
class HircEntryFactory:
    
    @classmethod
    def FromMemoryStream(cls, stream):
        hircType = stream.uint8Read()
        stream.seek(stream.tell()-1)
        if hircType == 2: #sound
            return Sound.FromMemoryStream(stream)
        elif hircType == 11: #music track
            return MusicTrack.FromMemoryStream(stream)
        else:
            return HircEntry.FromMemoryStream(stream)
        
class HircReader:
    
    def __init__(self):
        self.entries = {}
        
    def Load(self, hircData):
        self.entries.clear()
        reader = MemoryStream()
        reader.write(hircData)
        reader.seek(0)
        numItems = reader.uint32Read()
        for item in range(numItems):
            entry = HircEntryFactory.FromMemoryStream(reader)
            self.entries[entry.GetId()] = entry
            
    def GetData(self):
        arr = [entry.GetData() for entry in self.entries.values()]
        return len(arr).to_bytes(4, byteorder="little") + b"".join(arr)
            
class BankParser:
    
    def __init__(self):
        self.Chunks = {}
        
    def Load(self, bankData):
        self.Chunks.clear()
        reader = MemoryStream()
        reader.write(bankData)
        reader.seek(0)
        while True:
            tag = ""
            try:
                tag = reader.read(4).decode('utf-8')
            except:
                break
            size = reader.uint32Read()
            self.Chunks[tag] = reader.read(size)
            
class BankSourceStruct:

    def __init__(self):
        self.pluginId = 0
        self.streamType = self.sourceId = self.memSize = self.bitFlags = 0
        
    @classmethod
    def FromBytes(cls, bytes):
        b = BankSourceStruct()
        b.pluginId, b.streamType, b.sourceId, b.memSize, b.bitFlags = struct.unpack("<IBIIB", bytes)
        return b
        
    def GetData(self):
        return struct.pack("<IBIIB", self.pluginId, self.streamType, self.sourceId, self.memSize, self.bitFlags)
        
class TrackInfoStruct:
    
    def __init__(self):
        self.trackId = self.sourceId = self.eventId = self.playAt = self.beginTrimOffset = self.endTrimOffset = self.sourceDuration = 0
        self.playAt_OLD = self.beginTrimOffset_OLD = self.endTrimOffset_OLD = self.sourceDuration_OLD = 0
        self.modified = False
        
    @classmethod
    def FromBytes(cls, bytes):
        t = TrackInfoStruct()
        t.trackId, t.sourceId, t.eventId, t.playAt, t.beginTrimOffset, t.endTrimOffset, t.sourceDuration = struct.unpack("<IIIdddd", bytes)
        return t
        
    def GetId(self):
        if self.sourceId != 0:
            return self.sourceId
        else:
            return self.eventId
            
    def SetData(self, playAt=None, beginTrimOffset=None, endTrimOffset=None, sourceDuration=None):
        if not self.modified:
            self.playAt_OLD = self.playAt
            self.beginTrimOffset_OLD = self.beginTrimOffset
            self.endTrimOffset_OLD = self.endTrimOffset
            self.sourceDuration_OLD = self.sourceDuration
        if playAt is not None: self.playAt = playAt
        if beginTrimOffset is not None: self.beginTrimOffset = beginTrimOffset
        if endTrimOffset is not None: self.endTrimOffset = endTrimOffset
        if sourceDuration is not None: self.sourceDuration = sourceDuration
        self.modified = True
        
    def RevertModifications(self):
        if self.modified:
            self.playAt = self.playAt_OLD
            self.beginTrimOffset = self.beginTrimOffset_OLD
            self.endTrimOffset = self.endTrimOffset_OLD
            self.sourceDuration = self.sourceDuration_OLD
            self.modified = False
        
    def GetData(self):
        return struct.pack("<IIIdddd", self.trackId, self.sourceId, self.eventId, self.playAt, self.beginTrimOffset, self.endTrimOffset, self.sourceDuration)
            
class MusicTrack(HircEntry):
    
    def __init__(self):
        super().__init__()
        self.bitFlags = 0
        
    @classmethod
    def FromMemoryStream(cls, stream):
        entry = MusicTrack()
        entry.hType = stream.uint8Read()
        entry.size = stream.uint32Read()
        startPosition = stream.tell()
        entry.hId = stream.uint32Read()
        entry.bitFlags = stream.uint8Read()
        numSources = stream.uint32Read()
        for _ in range(numSources):
            source = BankSourceStruct.FromBytes(stream.read(14))
            entry.sources.append(source)
        numTrackInfo = stream.uint32Read()
        for _ in range(numTrackInfo):
            track = TrackInfoStruct.FromBytes(stream.read(44))
            entry.trackInfo.append(track)
        entry.misc = stream.read(entry.size - (stream.tell()-startPosition))
        return entry

    def GetData(self):
        b = b"".join([source.GetData() for source in self.sources])
        t = b"".join([track.GetData() for track in self.trackInfo])
        return struct.pack("<BIIBI", self.hType, self.size, self.hId, self.bitFlags, len(self.sources)) + b + len(self.trackInfo).to_bytes(4, byteorder="little") + t + self.misc
    
class Sound(HircEntry):
    
    def __init__(self):
        super().__init__()
    
    @classmethod
    def FromMemoryStream(cls, stream):
        entry = Sound()
        entry.hType = stream.uint8Read()
        entry.size = stream.uint32Read()
        entry.hId = stream.uint32Read()
        entry.sources.append(BankSourceStruct.FromBytes(stream.read(14)))
        entry.misc = stream.read(entry.size - 18)
        return entry

    def GetData(self):
        return struct.pack(f"<BII14s{len(self.misc)}s", self.hType, self.size, self.hId, self.sources[0].GetData(), self.misc)
        
class WwiseBank(Subscriber):
    
    def __init__(self):
        self.data = b""
        self.BankHeader = b""
        self.TocDataHeader = b""
        self.BankPostData = b""
        self.Modified = False
        self.TocHeader = None
        self.Dep = None
        self.ModifiedCount = 0
        self.hierarchy = None
        self.Content = []
        
    def AddContent(self, content):
        content.Subscribers.add(self)
        self.Content.append(content)
        
    def RemoveContent(self, content):
        try:
            content.Subscribers.remove(self)
        except:
            pass
            
        try:
            self.Content.remove(content)
        except:
            pass
  
    def GetContent(self):
        return self.Content
        
    def RaiseModified(self):
        self.Modified = True
        self.ModifiedCount += 1
        
    def LowerModified(self):
        if self.Modified:
            self.ModifiedCount -= 1
            if self.ModifiedCount == 0:
                self.Modified = False
        
    def GetName(self):
        return self.Dep.Data
        
    def GetId(self):
        try:
            return self.TocHeader.FileID
        except:
            return 0
            
    def GetTypeID(self):
        try:
            return self.TocHeader.TypeID
        except:
            return 0
            
    def GetData(self):
        return self.data
            
    def Generate(self, audioSources, eventTrackInfo):
        data = bytearray()
        data += self.BankHeader
        
        didxSection = b""
        dataSection = b""
        offset = 0
        
        #regenerate soundbank from the hierarchy information
        maxProgress = 0
        for entry in self.hierarchy.entries.values():
            if entry.hType == SOUND:
                maxProgress += 1
            elif entry.hType == MUSIC_TRACK:
                maxProgress += len(entry.sources)
                    
        
        bankGeneration = ProgressWindow("Generating Soundbanks", maxProgress)
        bankGeneration.Show()
        bankGeneration.SetText(f"Generating {self.Dep.Data}")
        
        didxArray = []
        dataArray = []
        
        for entry in self.hierarchy.entries.values():
            #didxArray = [struct.pack("<III", source.sourceId, offset, source.memSize) for source in entry.sources if source.pluginId == 0x00040001]
            for index, info in enumerate(entry.trackInfo):
                if info.eventId != 0:
                    entry.trackInfo[index] = eventTrackInfo[info.eventId]
            for source in entry.sources:
                bankGeneration.Step()
                if source.pluginId == 0x00040001:
                    try:
                        audio = audioSources[source.sourceId]
                    except KeyError:
                        continue
                    try:
                        count = 0
                        for info in entry.trackInfo:
                            if info.sourceId == source.sourceId:
                                break
                            count += 1
                        if audio.GetTrackInfo() is not None:
                            entry.trackInfo[count] = audio.GetTrackInfo()
                        else:
                            pass
                            #print(audio.GetId())
                            #print(entry.trackInfo[count])
                    except: #exception because there may be no original track info struct
                        pass
                    if source.streamType == PREFETCH_STREAM:
                        dataArray.append(audio.GetData()[:source.memSize])
                        didxArray.append(struct.pack("<III", source.sourceId, offset, source.memSize))
                        offset += source.memSize
                    elif source.streamType == BANK:
                        dataArray.append(audio.GetData())
                        didxArray.append(struct.pack("<III", source.sourceId, offset, audio.Size))
                        offset += audio.Size
        if len(didxArray) > 0:
            data += "DIDX".encode('utf-8') + (12*len(didxArray)).to_bytes(4, byteorder="little")
            data += b"".join(didxArray)
            data += "DATA".encode('utf-8') + sum([len(x) for x in dataArray]).to_bytes(4, byteorder="little")
            data += b"".join(dataArray)
            
        hircSection = self.hierarchy.GetData()
        data += "HIRC".encode('utf-8') + len(hircSection).to_bytes(4, byteorder="little")
        data += hircSection
        data += self.BankPostData
        self.TocHeader.TocDataSize = len(data) + len(self.TocDataHeader)
        self.TocDataHeader[4:8] = len(data).to_bytes(4, byteorder="little")
        self.data = data
        bankGeneration.Destroy()
                     
    def GetEntryIndex(self):
        try:
            return self.TocHeader.EntryIndex
        except:
            return 0
        
class WwiseStream(Subscriber):

    def __init__(self):
        self.Content = None
        self.Modified = False
        self.TocHeader = None
        self.TocData = bytearray()
        
    def SetContent(self, content):
        try:
            self.Content.Subscribers.remove(self)
        except:
            pass
        self.Content = content
        content.Subscribers.add(self)
        
    def Update(self, content):
        self.TocHeader.StreamSize = content.Size
        self.TocData[8:12] = content.Size.to_bytes(4, byteorder='little')
        
    def RaiseModified(self):
        self.Modified = True
        
    def LowerModified(self):
        self.Modified = False
        
    def GetId(self):
        try:
            return self.TocHeader.FileID
        except:
            return 0
        
    def GetTypeID(self):
        try:
            return self.TocHeader.TypeID
        except:
            return 0
            
    def GetEntryIndex(self):
        try:
            return self.TocHeader.EntryIndex
        except:
            return 0
            
    def GetData(self):
        return self.Content.GetData()

class StringEntry:

    def __init__(self):
        self.Text = ""
        self.Text_OLD = ""
        self.FileID = 0
        self.Modified = False
        
    def GetId(self):
        return self.FileID
        
    def GetText(self):
        return self.Text
        
    def SetText(self, text):
        if not self.Modified:
            self.Text_OLD = self.Text
        self.Modified = True
        self.Text = text
        
    def RevertModifications(self):
        if self.Modified:
            self.Text = self.Text_OLD
            self.Modified = False
        
    def __deepcopy__(self, memo):
        newEntry = StringEntry()
        newEntry.Text = self.Text
        newEntry.FileID = self.FileID
        newEntry.Modified = self.Modified
        return newEntry
        
class TextBank:
    
    def __init__(self):
        self.TocHeader = None
        self.Data = b''
        self.StringIds = []
        self.Language = 0
        self.Modified = False
        
    def SetData(self, data):
        self.StringIds.clear()
        numEntries = int.from_bytes(data[8:12], byteorder='little')
        idStart = 16
        offsetStart = idStart + 4 * numEntries
        dataStart = offsetStart + 4 * numEntries
        ids = data[idStart:offsetStart]
        offsets = data[offsetStart:dataStart]
        for n in range(numEntries):
            stringID = int.from_bytes(ids[4*n:+4*(n+1)], byteorder="little")
            self.StringIds.append(stringID)
            
    def Update(self):
        pass
        #self.TocHeader.TocData = self.GetData()
        #self.TocHeader.TocDataSize = len(self.TocHeader.TocData)
        
    def GetData(self):
        return self.Data
        
    def Generate(self, stringEntries):
        entries = stringEntries[self.Language]
        stream = MemoryStream()
        stream.write(b'\xae\xf3\x85\x3e\x01\x00\x00\x00')
        stream.write(len(self.StringIds).to_bytes(4, byteorder="little"))
        stream.write(self.Language.to_bytes(4, byteorder="little"))
        offset = 16 + 8*len(self.StringIds)
        for i in self.StringIds:
            stream.write(entries[i].FileID.to_bytes(4, byteorder="little"))
        for i in self.StringIds:
            stream.write(offset.to_bytes(4, byteorder="little"))
            initialPos = stream.tell()
            stream.seek(offset)
            stream.write(entries[i].Text.encode('utf-8') + b'\x00')
            offset += len(entries[i].Text) + 1
            stream.seek(initialPos)
        self.Data = stream.Data
        self.TocHeader.TocDataSize = len(self.Data)
        
    def Rebuild(self, stringID, offsetDifference):
        pass
        #modifiedEntry = self.StringEntries[stringID]
        #for entry in self.StringEntries.values():
        #    if entry.Offset > modifiedEntry.Offset:
        #        entry.Offset += offsetDifference
        
    def GetId(self):
        try:
            return self.TocHeader.FileID
        except:
            return 0
        
    def GetTypeID(self):
        try:
            return self.TocHeader.TypeID
        except:
            return 0
            
    def GetEntryIndex(self):
        try:
            return self.TocHeader.EntryIndex
        except:
            return 0

class FileReader:
    
    def __init__(self):
        self.WwiseStreams = {}
        self.WwiseBanks = {}
        self.AudioSources = {}
        self.TextBanks = {}
        self.TrackEvents = {}
        self.StringEntries = {}
        
    def FromFile(self, path):
        self.Name = os.path.basename(path)
        tocFile = MemoryStream()
        with open(path, 'r+b') as f:
            tocFile = MemoryStream(f.read())

        streamFile = MemoryStream()
        if os.path.isfile(path+".stream"):
            with open(path+".stream", 'r+b') as f:
                streamFile = MemoryStream(f.read())
        self.Load(tocFile, streamFile)
        
    def ToFile(self, path):
        tocFile = MemoryStream()
        streamFile = MemoryStream()
        self.numFiles = len(self.WwiseStreams) + 2*len(self.WwiseBanks) + len(self.TextBanks)
        self.numTypes = 0
        if len(self.WwiseStreams) > 0: self.numTypes += 1
        if len(self.WwiseBanks) > 0: self.numTypes += 2
        if len(self.TextBanks) > 0: self.numTypes += 1
        
        tocFile.write(self.magic.to_bytes(4, byteorder="little"))
        
        tocFile.write(self.numTypes.to_bytes(4, byteorder="little"))
        tocFile.write(self.numFiles.to_bytes(4, byteorder="little"))
        tocFile.write(self.unknown.to_bytes(4, byteorder="little"))
        tocFile.write(self.unk4Data)
        
        if len(self.WwiseStreams) > 0:
            unk = 0
            tocFile.write(unk.to_bytes(8, byteorder='little'))
            unk = 5785811756662211598
            tocFile.write(unk.to_bytes(8, byteorder='little'))
            unk = len(self.WwiseStreams)
            tocFile.write(unk.to_bytes(8, byteorder='little'))
            unk = 16
            tocFile.write(unk.to_bytes(4, byteorder='little'))
            unk = 64
            tocFile.write(unk.to_bytes(4, byteorder='little'))
            
        if len(self.WwiseBanks) > 0:
            unk = 0
            tocFile.write(unk.to_bytes(8, byteorder='little'))
            unk = 6006249203084351385
            tocFile.write(unk.to_bytes(8, byteorder='little'))
            unk = len(self.WwiseBanks)
            tocFile.write(unk.to_bytes(8, byteorder='little'))
            unk = 16
            tocFile.write(unk.to_bytes(4, byteorder='little'))
            unk = 64
            tocFile.write(unk.to_bytes(4, byteorder='little'))
            
            #deps
            unk = 0
            tocFile.write(unk.to_bytes(8, byteorder='little'))
            unk = 12624162998411505776
            tocFile.write(unk.to_bytes(8, byteorder='little'))
            unk = len(self.WwiseBanks)
            tocFile.write(unk.to_bytes(8, byteorder='little'))
            unk = 16
            tocFile.write(unk.to_bytes(4, byteorder='little'))
            unk = 64
            tocFile.write(unk.to_bytes(4, byteorder='little'))
            
        if len(self.TextBanks) > 0:
            unk = 0
            tocFile.write(unk.to_bytes(8, byteorder='little'))
            unk = 979299457696010195
            tocFile.write(unk.to_bytes(8, byteorder='little'))
            unk = len(self.TextBanks)
            tocFile.write(unk.to_bytes(8, byteorder='little'))
            unk = 16
            tocFile.write(unk.to_bytes(4, byteorder='little'))
            unk = 64
            tocFile.write(unk.to_bytes(4, byteorder='little'))
        
        tocPosition = tocFile.tell()
        for key in self.WwiseStreams.keys():
            tocFile.seek(tocPosition)
            tocPosition += 80
            stream = self.WwiseStreams[key]
            tocFile.write(stream.TocHeader.GetData())
            tocFile.seek(stream.TocHeader.TocDataOffset)
            tocFile.write(PadTo16ByteAlign(stream.TocData))
            streamFile.seek(stream.TocHeader.StreamOffset)
            streamFile.write(PadTo16ByteAlign(stream.Content.GetData()))
            
        for key in self.WwiseBanks.keys():
            tocFile.seek(tocPosition)
            tocPosition += 80
            bank = self.WwiseBanks[key]
            tocFile.write(bank.TocHeader.GetData())
            tocFile.seek(bank.TocHeader.TocDataOffset)
            tocFile.write(PadTo16ByteAlign(bank.TocDataHeader + bank.GetData()))
            
        for key in self.WwiseBanks.keys():
            tocFile.seek(tocPosition)
            tocPosition += 80
            bank = self.WwiseBanks[key]
            tocFile.write(bank.Dep.TocHeader.GetData())
            tocFile.seek(bank.Dep.TocHeader.TocDataOffset)
            tocFile.write(PadTo16ByteAlign(bank.Dep.GetData()))
            
        for key in self.TextBanks.keys():
            tocFile.seek(tocPosition)
            tocPosition += 80
            entry = self.TextBanks[key]
            tocFile.write(entry.TocHeader.GetData())
            tocFile.seek(entry.TocHeader.TocDataOffset)
            tocFile.write(PadTo16ByteAlign(entry.GetData())) #temporarily English (US) only
            
            
        with open(os.path.join(path, self.Name), 'w+b') as f:
            f.write(tocFile.Data)
            
        if len(streamFile.Data) > 0:
            with open(os.path.join(path, self.Name+".stream"), 'w+b') as f:
                f.write(streamFile.Data)

    def RebuildHeaders(self):
        self.numTypes = 0
        if len(self.WwiseStreams) > 0: self.numTypes += 1
        if len(self.WwiseBanks) > 0: self.numTypes += 2
        if len(self.TextBanks) > 0: self.numTypes += 1
        self.numFiles = len(self.WwiseStreams) + 2*len(self.WwiseBanks) + len(self.TextBanks)
        streamOffset = 0
        tocOffset = 80 + self.numTypes * 32 + 80 * self.numFiles
        for key, value in self.WwiseStreams.items():
            value.TocHeader.StreamOffset = streamOffset
            value.TocHeader.TocDataOffset = tocOffset
            streamOffset += _16ByteAlign(value.TocHeader.StreamSize)
            tocOffset += _16ByteAlign(value.TocHeader.TocDataSize)
        
        for key, value in self.WwiseBanks.items():
            print(3070152700 in self.TrackEvents.keys())
            value.Generate(self.AudioSources, self.TrackEvents)
            
            value.TocHeader.TocDataOffset = tocOffset
            tocOffset += _16ByteAlign(value.TocHeader.TocDataSize)
            
        for key, value in self.WwiseBanks.items():
            value.Dep.TocHeader.TocDataOffset = tocOffset
            tocOffset += _16ByteAlign(value.TocHeader.TocDataSize)
            
        for key, value in self.TextBanks.items():
            value.Generate(stringEntries=self.StringEntries)
            value.TocHeader.TocDataOffset = tocOffset
            tocOffset += _16ByteAlign(value.TocHeader.TocDataSize)
        
    def Load(self, tocFile, streamFile):
        self.WwiseStreams.clear()
        self.WwiseBanks.clear()
        self.AudioSources.clear()
        self.TextBanks.clear()
        self.TrackEvents.clear()
        self.StringEntries.clear()
        '''
        How to do music:
        1. Add self.TrackInfo dict
        2. Loop through bank hierarchy. If a source has valid trackInfo and it is not a duplicate, add it to the dict
        3. Have soundbanks load from the trackinfo dict on Generate
        4. Check trackInfo when loading patch
        5. Create UI to set trackInfo. Perhaps a pop-up window?
        6. Show type in the UI (Sound vs Music Track)
        '''
        
        
        self.magic      = tocFile.uint32Read()
        if self.magic != 4026531857: return False

        self.numTypes   = tocFile.uint32Read()
        self.numFiles   = tocFile.uint32Read()
        self.unknown    = tocFile.uint32Read()
        self.unk4Data   = tocFile.read(56)
        tocFile.seek(tocFile.tell() + 32 * self.numTypes)
        tocStart = tocFile.tell()
        for n in range(self.numFiles):
            tocFile.seek(tocStart + n*80)
            tocHeader = TocHeader()
            tocHeader.FromMemoryStream(tocFile)
            entry = None
            if tocHeader.TypeID == 5785811756662211598:
                audio = AudioSource()
                audio.streamType = STREAM
                entry = WwiseStream()
                entry.TocHeader = tocHeader
                tocFile.seek(tocHeader.TocDataOffset)
                entry.TocData = tocFile.read(tocHeader.TocDataSize)
                streamFile.seek(tocHeader.StreamOffset)
                audio.SetData(streamFile.read(tocHeader.StreamSize), notifySubscribers=False, setModified=False)
                audio.resourceId = tocHeader.FileID
                entry.SetContent(audio)
                self.WwiseStreams[entry.GetId()] = entry
            elif tocHeader.TypeID == 6006249203084351385:
                entry = WwiseBank()
                entry.TocHeader = tocHeader
                tocDataOffset = tocHeader.TocDataOffset
                tocDataSize = tocHeader.TocDataSize
                tocFile.seek(tocDataOffset)
                entry.TocDataHeader = tocFile.read(16)
                #-------------------------------------
                bank = BankParser()
                bank.Load(tocFile.read(tocHeader.TocDataSize-16))
                entry.BankHeader = "BKHD".encode('utf-8') + len(bank.Chunks["BKHD"]).to_bytes(4, byteorder="little") + bank.Chunks["BKHD"]
                
                hirc = HircReader()
                try:
                    hirc.Load(bank.Chunks['HIRC'])
                except KeyError:
                    continue
                entry.hierarchy = hirc    
                #-------------------------------------
                #Add all bank sources to the source list
                if "DIDX" in bank.Chunks.keys():
                    bankId = entry.TocHeader.FileID
                    mediaIndex = MediaIndex()
                    mediaIndex.Load(bank.Chunks["DIDX"], bank.Chunks["DATA"])
                    for e in hirc.entries.values():
                        for source in e.sources:
                            if source.pluginId == 0x00040001 and source.streamType == BANK and source.sourceId not in self.AudioSources:
                                audio = AudioSource()
                                audio.streamType = BANK
                                audio.shortId = source.sourceId
                                audio.SetData(mediaIndex.data[source.sourceId], setModified=False, notifySubscribers=False)
                                self.AudioSources[source.sourceId] = audio
                
                entry.BankPostData = b''
                for chunk in bank.Chunks.keys():
                    if chunk not in ["BKHD", "DATA", "DIDX", "HIRC"]:
                        entry.BankPostData = entry.BankPostData + chunk.encode('utf-8') + len(bank.Chunks[chunk]).to_bytes(4, byteorder='little') + bank.Chunks[chunk]
                        
                self.WwiseBanks[entry.GetId()] = entry
            elif tocHeader.TypeID == 12624162998411505776: #wwise dep
                dep = WwiseDep()
                dep.TocHeader = tocHeader
                tocFile.seek(tocHeader.TocDataOffset)
                dep.FromMemoryStream(tocFile)
                try:
                    self.WwiseBanks[tocHeader.FileID].Dep = dep
                except KeyError:
                    pass
            elif tocHeader.TypeID == 979299457696010195: #stringEntry
                tocFile.seek(tocHeader.TocDataOffset)
                data = tocFile.read(tocHeader.TocDataSize)
                numEntries = int.from_bytes(data[8:12], byteorder='little')
                language = int.from_bytes(data[12:16], byteorder='little')
                if language not in self.StringEntries:
                    self.StringEntries[language] = {}
                idStart = 16
                offsetStart = idStart + 4 * numEntries
                dataStart = offsetStart + 4 * numEntries
                ids = data[idStart:offsetStart]
                offsets = data[offsetStart:dataStart]
                textBank = TextBank()
                textBank.TocHeader = tocHeader
                textBank.Language = language
                for n in range(numEntries):
                    entry = StringEntry()
                    stringID = int.from_bytes(ids[4*n:+4*(n+1)], byteorder="little")
                    textBank.StringIds.append(stringID)
                    stringOffset = int.from_bytes(offsets[4*n:4*(n+1)], byteorder="little")
                    entry.FileID = stringID
                    stopIndex = stringOffset + 1
                    while data[stopIndex] != 0:
                        stopIndex += 1
                    entry.Text = data[stringOffset:stopIndex].decode('utf-8')
                    self.StringEntries[language][stringID] = entry

                #if int.from_bytes(data[12:16], byteorder='little') == _LANGUAGE: #English (US)
                self.TextBanks[textBank.GetId()] = textBank
        
        
        #check that all banks have valid Dep here, and ask for more data if does not?
        
        for bank in self.WwiseBanks.values():
            if bank.Dep == None: #can be None because older versions didn't save the dep along with the bank
                if not self.LoadDeps():
                    print("Failed to load")
                    self.WwiseStreams.clear()
                    self.WwiseBanks.clear()
                    self.TextBanks.clear()
                    self.AudioSources.clear()
                    return
                break
        
        if len(self.WwiseBanks) == 0 and len(self.WwiseStreams) > 0: #0 if patch was only for streams
            #print("No banks detected! This patch may have been made in an older version of the audio modding tool!") #make this a pop-up window
            if not self.LoadBanks():
                print("Failed to load")
                self.WwiseStreams.clear()
                self.WwiseBanks.clear()
                self.TextBanks.clear()
                self.AudioSources.clear()
                return
        
        #Add all stream entries to the AudioSource list, using their shortID (requires mapping via the Dep)
        for bank in self.WwiseBanks.values():
            for entry in bank.hierarchy.entries.values():
                for source in entry.sources:
                    if source.pluginId == 0x00040001 and source.streamType in [STREAM, PREFETCH_STREAM] and source.sourceId not in self.AudioSources:
                        try:
                            streamResourceId = murmur64Hash((os.path.dirname(bank.Dep.Data) + "/" + str(source.sourceId)).encode('utf-8'))
                            audio = self.WwiseStreams[streamResourceId].Content
                            audio.shortId = source.sourceId
                            self.AudioSources[source.sourceId] = audio
                        except KeyError:
                            pass
                        #elif source.sourceId in self.AudioSources:
                        #    self.AudioSources[source.sourceId].resourceId = murmur64Hash((os.path.dirname(bank.Dep.Data) + "/" + str(source.sourceId)).encode('utf-8'))
                for info in entry.trackInfo:
                    if info.eventId != 0:
                        self.TrackEvents[info.eventId] = info
        

        #construct list of audio sources in each bank
        #add trackInfo to audio sources?
        for bank in self.WwiseBanks.values():
            for entry in bank.hierarchy.entries.values():
                for source in entry.sources:
                    try:
                        if source.pluginId == 0x00040001 and self.AudioSources[source.sourceId] not in bank.GetContent(): #may be missing streamed audio if the patch didn't change it
                            bank.AddContent(self.AudioSources[source.sourceId])
                    except:
                        continue
                for info in entry.trackInfo: #can improve speed here
                    try:
                        if info.sourceId != 0:
                            self.AudioSources[info.sourceId].SetTrackInfo(info, notifySubscribers=False, setModified=False)
                    except:
                        continue
                

        
    def LoadDeps(self):
        if _GAME_FILE_LOCATION != "":
            archiveFile = os.path.join(_GAME_FILE_LOCATION, StripPatchIndex(self.Name))
        if not os.path.exists(archiveFile):
            warning = PopupWindow(message = "This patch may have been created using an older version of the audio modding tool and is missing required data. Please select the original game file to load required data.")
            warning.Show()
            warning.root.wait_window(warning.root)
            archiveFile = askopenfilename(title="Select archive")
            if os.path.splitext(archiveFile)[1] in (".stream", ".gpu_resources"):
                archiveFile = os.path.splitext(archiveFile)[0]
        if not os.path.exists(archiveFile):
            return False
        #self.Name = os.path.basename(path)
        tocFile = MemoryStream()
        with open(archiveFile, 'r+b') as f:
            tocFile = MemoryStream(f.read())

        self.magic      = tocFile.uint32Read()
        if self.magic != 4026531857: return False

        self.numTypes   = tocFile.uint32Read()
        self.numFiles   = tocFile.uint32Read()
        self.unknown    = tocFile.uint32Read()
        self.unk4Data   = tocFile.read(56)
        tocFile.seek(tocFile.tell() + 32 * self.numTypes)
        tocStart = tocFile.tell()
        for n in range(self.numFiles):
            tocFile.seek(tocStart + n*80)
            tocHeader = TocHeader()
            tocHeader.FromMemoryStream(tocFile)
            if tocHeader.TypeID == 12624162998411505776: #wwise dep
                dep = WwiseDep()
                dep.TocHeader = tocHeader
                tocFile.seek(tocHeader.TocDataOffset)
                dep.FromMemoryStream(tocFile)
                try:
                    self.WwiseBanks[tocHeader.FileID].Dep = dep
                except KeyError:
                    pass
        return True
        
    def LoadBanks(self):
        if _GAME_FILE_LOCATION != "":
            archiveFile = os.path.join(_GAME_FILE_LOCATION, StripPatchIndex(self.Name))
        if not os.path.exists(archiveFile):
            warning = PopupWindow(message = "This patch may have been created using an older version of the audio modding tool and is missing required data. Please select the original game file to load required data.")
            warning.Show()
            warning.root.wait_window(warning.root)
            archiveFile = askopenfilename(title="Select archive")
            if os.path.splitext(archiveFile)[1] in (".stream", ".gpu_resources"):
                archiveFile = os.path.splitext(archiveFile)[0]
        if not os.path.exists(archiveFile):
            return False
        tocFile = MemoryStream()
        with open(archiveFile, 'r+b') as f:
            tocFile = MemoryStream(f.read())

        self.magic      = tocFile.uint32Read()
        if self.magic != 4026531857: return False

        self.numTypes   = tocFile.uint32Read()
        self.numFiles   = tocFile.uint32Read()
        self.unknown    = tocFile.uint32Read()
        self.unk4Data   = tocFile.read(56)
        tocFile.seek(tocFile.tell() + 32 * self.numTypes)
        tocStart = tocFile.tell()
        for n in range(self.numFiles):
            tocFile.seek(tocStart + n*80)
            tocHeader = TocHeader()
            tocHeader.FromMemoryStream(tocFile)
            entry = None
            if tocHeader.TypeID == 6006249203084351385:
                entry = WwiseBank()
                entry.TocHeader = tocHeader
                tocDataOffset = tocHeader.TocDataOffset
                tocDataSize = tocHeader.TocDataSize
                tocFile.seek(tocDataOffset)
                entry.TocDataHeader = tocFile.read(16)
                #-------------------------------------
                bank = BankParser()
                bank.Load(tocFile.read(tocHeader.TocDataSize-16))
                entry.BankHeader = "BKHD".encode('utf-8') + len(bank.Chunks["BKHD"]).to_bytes(4, byteorder="little") + bank.Chunks["BKHD"]
                
                hirc = HircReader()
                try:
                    hirc.Load(bank.Chunks['HIRC'])
                except KeyError:
                    continue
                entry.hierarchy = hirc
                #-------------------------------------
                entry.BankPostData = b''
                for chunk in bank.Chunks.keys():
                    if chunk not in ["BKHD", "DATA", "DIDX", "HIRC"]:
                        entry.BankPostData = entry.BankPostData + chunk.encode('utf-8') + len(bank.Chunks[chunk]).to_bytes(4, byteorder='little') + bank.Chunks[chunk]
                        
                self.WwiseBanks[entry.GetId()] = entry
            elif tocHeader.TypeID == 12624162998411505776: #wwise dep
                dep = WwiseDep()
                dep.TocHeader = tocHeader
                tocFile.seek(tocHeader.TocDataOffset)
                dep.FromMemoryStream(tocFile)
                try:
                    self.WwiseBanks[tocHeader.FileID].Dep = dep
                except KeyError:
                    pass
        
        #only include banks that contain at least 1 of the streams
        tempBanks = {}
        for key, bank in self.WwiseBanks.items():
            includeBank = False
            for hierEntry in bank.hierarchy.entries.values():
                for source in hierEntry.sources:
                    if source.pluginId == 0x00040001 and source.streamType in [STREAM, PREFETCH_STREAM]:
                        streamResourceId = murmur64Hash((os.path.dirname(bank.Dep.Data) + "/" + str(source.sourceId)).encode('utf-8'))
                        for stream in self.WwiseStreams.values():
                            if stream.GetId() == streamResourceId:
                                includeBank = True
                                tempBanks[key] = bank
                                break
                    if includeBank:
                        break
                if includeBank:
                    break
        self.WwiseBanks = tempBanks
        
        return True
        
class SoundHandler:
    
    def __init__(self):
        self.audioProcess = None
        self.waveObject = None
        self.audioID = -1
        self.audio = pyaudio.PyAudio()
        
    def KillSound(self):
        if self.audioProcess is not None:
            if self.callback is not None:
                self.callback()
                self.callback = None
            self.audioProcess.close()
            self.waveFile.close()
            try:
                os.remove(self.audioFile)
            except:
                pass
            self.audioProcess = None
        
    def PlayAudio(self, soundID, soundData, callback=None):
        self.KillSound()
        self.callback = callback
        if self.audioID == soundID:
            self.audioID = -1
            return
        filename = f"temp{soundID}"
        if not os.path.isfile(f"{filename}.wav"):
            with open(f'{filename}.wem', 'wb') as f:
                f.write(soundData)
            subprocess.run(["vgmstream-win64/vgmstream-cli.exe", "-o", f"{filename}.wav", f"{filename}.wem"], stdout=subprocess.DEVNULL)
            os.remove(f"{filename}.wem")
            
        self.audioID = soundID
        self.waveFile = wave.open(f"{filename}.wav")
        self.audioFile = f"{filename}.wav"
        self.frameCount = 0
        self.maxFrames = self.waveFile.getnframes()
        
        def readStream(input_data, frame_count, time_info, status):
            self.frameCount += frame_count
            if self.frameCount > self.maxFrames:
                if self.callback is not None:
                    self.callback()
                    self.callback = None
                self.audioID = -1
                self.waveFile.close()
                try:
                    os.remove(self.audioFile)
                except:
                    pass
                return (None, pyaudio.paComplete)
            data = self.waveFile.readframes(frame_count)
            if self.waveFile.getnchannels() > 2:
                data = self.DownmixToStereo(data, self.waveFile.getnchannels(), self.waveFile.getsampwidth(), frame_count)
            return (data, pyaudio.paContinue)

        self.audioProcess = self.audio.open(format=self.audio.get_format_from_width(self.waveFile.getsampwidth()),
                channels = min(self.waveFile.getnchannels(), 2),
                rate=self.waveFile.getframerate(),
                output=True,
                stream_callback=readStream)
        self.audioFile = f"{filename}.wav"
        
    def DownmixToStereo(self, data, channels, channelWidth, frameCount):
        if channelWidth == 2:
            arr = numpy.frombuffer(data, dtype=numpy.int16)
            stereoArr = numpy.zeros(shape=(frameCount, 2), dtype=numpy.int16)
        elif channelWidth == 1:
            arr = numpy.frombuffer(data, dtype=numpy.int8)
            stereoArr = numpy.zeros(shape=(frameCount, 2), dtype=numpy.int8)
        elif channelWidth == 4:
            arr = numpy.frombuffer(data, dtype=numpy.int32)
            stereoArr = numpy.zeros(shape=(frameCount, 2), dtype=numpy.int32)
        arr = arr.reshape((frameCount, channels))
        
        if channels == 4:
            for index, frame in enumerate(arr):
                stereoArr[index][0] = int(0.42265 * frame[0] + 0.366025 * frame[2] + 0.211325 * frame[3])
                stereoArr[index][1] = int(0.42265 * frame[1] + 0.366025 * frame[3] + 0.211325 * frame[2])
                
        if channels == 6:
            for index, frame in enumerate(arr):
                stereoArr[index][0] = int(0.374107*frame[1] + 0.529067*frame[0] + 0.458186*frame[3] + 0.264534*frame[4] + 0.374107*frame[5])
                stereoArr[index][1] = int(0.374107*frame[1] + 0.529067*frame[2] + 0.458186*frame[4] + 0.264534*frame[3] + 0.374107*frame[5])
        
        return stereoArr.tobytes()
     
class FileHandler:

    def __init__(self):
        self.FileReader = FileReader()
        
    def RevertAll(self):
        for audio in self.FileReader.AudioSources.values():
            audio.RevertModifications()
        for language in self.FileReader.StringEntries.values():
            for string in language:
                string.RevertModifications()
        for trackInfo in self.FileReader.TrackEvents.values():
            trackInfo.RevertModifications()
        
    def RevertAudio(self, fileID):
        audio = self.GetAudioByID(fileID)
        audio.RevertModifications()
        
    def DumpAsWem(self, fileID):
        outputFile = filedialog.asksaveasfile(mode='wb', title="Save As", initialfile=(str(fileID)+".wem"), defaultextension=".wem", filetypes=[("Wwise Audio", "*.wem")])
        if outputFile is None: return
        outputFile.write(self.GetAudioByID(fileID).GetData())
        
    def DumpAsWav(self, fileID):
        outputFile = filedialog.asksaveasfilename(title="Save As", initialfile=(str(fileID)+".wav"), defaultextension=".wav", filetypes=[("Wav Audio", "*.wav")])
        if outputFile == "": return
        savePath = os.path.splitext(outputFile)[0]
        with open(f"{savePath}.wem", 'wb') as f:
            f.write(self.GetAudioByID(fileID).GetData())
        subprocess.run(["vgmstream-win64/vgmstream-cli.exe", "-o", f"{savePath}.wav", f"{savePath}.wem"], stdout=subprocess.DEVNULL)
        os.remove(f"{savePath}.wem")
        
    def DumpMultipleAsWem(self, fileIDs):
        folder = filedialog.askdirectory(title="Select folder to save files to")
        
        progressWindow = ProgressWindow(title="Dumping Files", maxProgress=len(fileIDs))
        progressWindow.Show()
        
        if os.path.exists(folder):
            for fileID in fileIDs:
                audio = self.GetAudioByID(fileID)
                if audio is not None:
                    savePath = os.path.join(folder, f"{audio.GetId()}")
                    progressWindow.SetText("Dumping " + os.path.basename(savePath) + ".wem")
                    with open(savePath+".wem", "wb") as f:
                        f.write(audio.GetData())
                progressWindow.Step()
        else:
            print("Invalid folder selected, aborting dump")
            
        progressWindow.Destroy()
        
    def DumpMultipleAsWav(self, fileIDs):
        folder = filedialog.askdirectory(title="Select folder to save files to")
        
        progressWindow = ProgressWindow(title="Dumping Files", maxProgress=len(fileIDs))
        progressWindow.Show()
        
        if os.path.exists(folder):
            for fileID in fileIDs:
                audio = self.GetAudioByID(fileID)
                if audio is not None:
                    savePath = os.path.join(folder, f"{audio.GetId()}")
                    progressWindow.SetText("Dumping " + os.path.basename(savePath) + ".wem")
                    with open(savePath+".wem", "wb") as f:
                        f.write(audio.GetData())
                    subprocess.run(["vgmstream-win64/vgmstream-cli.exe", "-o", f"{savePath}.wav", f"{savePath}.wem"], stdout=subprocess.DEVNULL)
                    os.remove(f"{savePath}.wem")
                progressWindow.Step()
        else:
            print("Invalid folder selected, aborting dump")
            
        progressWindow.Destroy()

    def DumpAllAsWem(self):
        folder = filedialog.askdirectory(title="Select folder to save files to")
        
        progressWindow = ProgressWindow(title="Dumping Files", maxProgress=len(self.FileReader.AudioSources))
        progressWindow.Show()
        
        if os.path.exists(folder):
            for bank in self.FileReader.WwiseBanks.values():
                subfolder = os.path.join(folder, os.path.basename(bank.Dep.Data.replace('\x00', '')))
                if not os.path.exists(subfolder):
                    os.mkdir(subfolder)
                for audio in bank.GetContent():
                    savePath = os.path.join(subfolder, f"{audio.GetId()}")
                    progressWindow.SetText("Dumping " + os.path.basename(savePath) + ".wem")
                    with open(savePath+".wem", "wb") as f:
                        f.write(audio.GetData())
                    progressWindow.Step()
        else:
            print("Invalid folder selected, aborting dump")
            
        progressWindow.Destroy()
    
    def DumpAllAsWav(self):
        folder = filedialog.askdirectory(title="Select folder to save files to")

        progressWindow = ProgressWindow(title="Dumping Files", maxProgress=len(self.FileReader.AudioSources))
        progressWindow.Show()
        
        if os.path.exists(folder):
            for bank in self.FileReader.WwiseBanks.values():
                subfolder = os.path.join(folder, os.path.basename(bank.Dep.Data.replace('\x00', '')))
                if not os.path.exists(subfolder):
                    os.mkdir(subfolder)
                for audio in bank.GetContent():
                    savePath = os.path.join(subfolder, f"{audio.GetId()}")
                    progressWindow.SetText("Dumping " + os.path.basename(savePath) + ".wav")
                    with open(savePath+".wem", "wb") as f:
                        f.write(audio.GetData())
                    subprocess.run(["vgmstream-win64/vgmstream-cli.exe", "-o", f"{savePath}.wav", f"{savePath}.wem"], stdout=subprocess.DEVNULL)
                    os.remove(f"{savePath}.wem")
                    progressWindow.Step()
        else:
            print("Invalid folder selected, aborting dump")
            
        progressWindow.Destroy()
        
    def GetFileNumberPrefix(self, n):
        number = ''.join(takewhile(str.isdigit, n or ""))
        try:
            return int(number)
        except:
            print("File name must begin with a number: "+n)
        
    def SaveArchiveFile(self):
        folder = filedialog.askdirectory(title="Select folder to save files to")
        if os.path.exists(folder):
            self.FileReader.RebuildHeaders()
            self.FileReader.ToFile(folder)
        else:
            print("Invalid folder selected, aborting save")
            
    def GetAudioByID(self, fileID):
        try:
            return self.FileReader.AudioSources[fileID] #shortId
        except KeyError:
            pass
        for source in self.FileReader.AudioSources.values(): #resourceId
            if source.resourceId == fileID:
                return source
                
    def GetEventByID(self, eventId):
        try:
            return self.FileReader.TrackEvents[eventId]
        except:
            pass
            
    def GetStringEntryByID(self, stringId):
        try:
            return self.FileReader.StringEntries[_LANGUAGE][stringId]
        except:
            pass
        
    def GetWwiseStreams(self):
        return self.FileReader.WwiseStreams
        
    def GetWwiseBanks(self):
        return self.FileReader.WwiseBanks
        
    def GetAudio(self):
        return self.FileReader.AudioSources
        
    def GetStrings(self):
        return self.FileReader.StringEntries
        
    def LoadArchiveFile(self):
        archiveFile = askopenfilename(title="Select archive")
        if os.path.splitext(archiveFile)[1] in (".stream", ".gpu_resources"):
            archiveFile = os.path.splitext(archiveFile)[0]
        if os.path.exists(archiveFile):
            self.FileReader.FromFile(archiveFile)
        else:
            print("Invalid file selected, aborting load")   
            return False
        return True
            
            
    def LoadPatch(self): #TO-DO: only import if DIFFERENT from original audio; makes it possible to import different mods that change the same soundbank
        patchFileReader = FileReader()
        patchFile = filedialog.askopenfilename(title="Choose patch file to import")
        if os.path.splitext(patchFile)[1] in (".stream", ".gpu_resources"):
            patchFile = os.path.splitext(patchFile)[0]
        if os.path.exists(patchFile):
            patchFileReader.FromFile(patchFile)
        else:
            print("Invalid file selected, aborting load")
            return False
            
        progressWindow = ProgressWindow(title="Loading Files", maxProgress=len(patchFileReader.AudioSources))
        progressWindow.Show()
        
        for bank in patchFileReader.WwiseBanks.values():
            for newAudio in bank.GetContent():
                progressWindow.SetText(f"Loading {newAudio.GetId()}")
                oldAudio = self.GetAudioByID(newAudio.GetShortId())
                oldAudio.SetData(newAudio.GetData())
                progressWindow.Step()

        for textData in patchFileReader.TextBanks.values():
            for stringId in textData.StringIds:
                newTextData = patchFileReader.StringEntries[_LANGUAGE][stringId]
                oldTextData = self.FileReader.StringEntries[_LANGUAGE][stringId]
                oldTextData.SetText(newTextData.GetText())
        
        progressWindow.Destroy()
        return True

    def WritePatch(self):
        folder = filedialog.askdirectory(title="Select folder to save files to")
        if os.path.exists(folder):
            patchedFileReader = FileReader()
            patchedFileReader.Name = self.FileReader.Name + ".patch_0"
            patchedFileReader.magic = self.FileReader.magic
            patchedFileReader.numTypes = 0
            patchedFileReader.numFiles = 0
            patchedFileReader.unknown = self.FileReader.unknown
            patchedFileReader.unk4Data = self.FileReader.unk4Data
            patchedFileReader.AudioSources = self.FileReader.AudioSources
            patchedFileReader.StringEntries = self.FileReader.StringEntries
            patchedFileReader.TrackEvents = self.FileReader.TrackEvents
            patchedFileReader.WwiseBanks = {}
            patchedFileReader.WwiseStreams = {}
            patchedFileReader.TextBanks = {}
            
            for key, value in self.FileReader.WwiseStreams.items():
                if value.Content.Modified:
                    patchedFileReader.WwiseStreams[key] = copy.deepcopy(value)
                    
            for key, value in self.FileReader.WwiseBanks.items():
                if value.Modified:
                    patchedFileReader.WwiseBanks[key] = copy.deepcopy(value)
                    
            for key, value in self.FileReader.TextBanks.items():
                for stringId in value.StringIds:
                    if self.FileReader.StringEntries[value.Language][stringId].Modified:
                        patchedFileReader.TextBanks[key] = copy.deepcopy(value)
                        break
     
            patchedFileReader.RebuildHeaders()
            patchedFileReader.ToFile(folder)
        else:
            print("Invalid folder selected, aborting save")
            return False
        return True

    def LoadWems(self): 
        wems = filedialog.askopenfilenames(title="Choose .wem files to import")
        
        progressWindow = ProgressWindow(title="Loading Files", maxProgress=len(wems))
        progressWindow.Show()
        
        for file in wems:
            progressWindow.SetText("Loading "+os.path.basename(file))
            fileID = self.GetFileNumberPrefix(os.path.basename(file))
            audio = self.GetAudioByID(fileID)
            if audio is not None:
                with open(file, 'rb') as f:
                    audio.SetData(f.read())
            progressWindow.Step()
        
        progressWindow.Destroy()
      
class ProgressWindow:
    def __init__(self, title, maxProgress):
        self.title = title
        self.maxProgress = maxProgress
        
    def Show(self):
        self.root = Tk()
        self.root.title(self.title)
        self.root.configure(background="white")
        self.root.geometry("410x45")
        self.root.attributes('-topmost', True)
        self.progressBar = tkinter.ttk.Progressbar(self.root, orient=HORIZONTAL, length=400, mode="determinate", maximum=self.maxProgress)
        self.progressBarText = Text(self.root)
        self.progressBarText.configure(background="white")
        self.progressBar.pack()
        self.progressBarText.pack()
        self.root.resizable(False, False)
        
    def Step(self):
        self.progressBar.step()
        self.root.update_idletasks()
        self.root.update()
        
    def SetText(self, s):
        self.progressBarText.delete('1.0', END)
        self.progressBarText.insert(INSERT, s)
        self.root.update_idletasks()
        self.root.update()
        
    def Destroy(self):
        self.root.destroy()
        
class PopupWindow:
    def __init__(self, message, title="Missing Data!"):
        self.message = message
        self.title = title
        
    def Show(self):
        self.root = Tk()
        self.root.title(self.title)
        self.root.configure(background="white")
        #self.root.geometry("410x45")
        self.root.attributes('-topmost', True)
        self.text = ttk.Label(self.root, text=self.message, background="white", font=('Segoe UI', 12), wraplength=500, justify="left")
        self.button = ttk.Button(self.root, text="OK", command=self.Destroy)
        self.text.pack(padx=20, pady=0)
        self.button.pack(pady=20)
        self.root.resizable(False, False)
        
    def Destroy(self):
        self.root.destroy()
        
class StringEntryWindow:
    
    def __init__(self, parent):
        self.frame = Frame(parent)
        #self.text = tkinter.StringVar(self.frame)
        self.textBox = Text(self.frame, width=50, font=('Arial', 8), wrap=WORD)
        self.stringEntry = None
        self.fakeImage = tkinter.PhotoImage(width=1, height=1)
        #textBox.insert(END, stringEntry.GetText())
        
        #create revert button
        self.revertButton = ttk.Button(self.frame, text="Revert", command=self.Revert)
        
        #create apply button
        self.applyButton = ttk.Button(self.frame, text="Apply", command=self.ApplyChanges)
        self.textBox.pack()
        self.revertButton.pack(side="left")
        self.applyButton.pack(side="left")
        
    def SetStringEntry(self, stringEntry):
        self.stringEntry = stringEntry
        self.textBox.delete("1.0", END)
        self.textBox.insert(END, stringEntry.GetText())
        
    def ApplyChanges(self):
        if self.stringEntry is not None:
            self.stringEntry.SetText(self.textBox.get("1.0", "end-1c"))
    
    def Revert(self):
        if self.stringEntry is not None:
            self.stringEntry.RevertModifications()
            self.textBox.delete("1.0", END)
            self.textBox.insert(END, self.stringEntry.GetText())
        
    '''
    info = TableInfo()
        info.hidden = True
        info._type = TableInfo.BANK_WEM
    
        fillColor = "white"
        info.rectangles.append(self.mainCanvas.create_rectangle(0, 0, ROW_WIDTH-SUBROW_INDENT, ROW_HEIGHT, fill=fillColor))
        self.tableInfo[stringEntry.GetFileID()] = info
        text = tkinter.StringVar(self.mainCanvas)
        textBox = Entry(self.mainCanvas, width=50, textvariable=text, font=('Arial', 8))
        stringEntry.TextVariable = text
        textBox.insert(END, stringEntry.GetText())
        info.text.append(self.mainCanvas.create_window(0, 0, window=textBox, anchor='nw'))
        
        #create revert button
        revert = Button(self.mainCanvas, text='\u21b6', fg='black', font=('Arial', 14, 'bold'), image=self.fakeImage, compound='c', height=20, width=20)
        
        info.revertButton = self.mainCanvas.create_window(0, 0, window=revert, anchor='nw')
        info.buttons.append(info.revertButton)
        
        #create apply button
        apply = Button(self.mainCanvas, text="\u2713", fg='green', font=('Arial', 14, 'bold'), image=self.fakeImage, compound='c', height=20, width=20)
        def applyText(entry):
            entry.UpdateText()
        apply.configure(command=partial(applyText, stringEntry))
        info.buttons.append(self.mainCanvas.create_window(0, 0, window=apply, anchor='nw'))
    '''
class AudioSourceWindow:
    
    def __init__(self, parent, revertFunc, playFunc):
        self.frame = Frame(parent)
        self.frame.configure(background="white")
        self.fakeImage = tkinter.PhotoImage(width=1, height=1)
        self.RevertFunc = revertFunc
        self.PlayFunc = playFunc
        self.titleLabel = Label(self.frame, background="white", font=('Segoe UI', 14))
        #self.revertButton = ttk.Button(self.frame, text='\u21b6', fg='black', font=('Arial', 14, 'bold'), image=self.fakeImage, compound='c', height=20, width=20)
        self.revertButton = ttk.Button(self.frame, text='\u21b6', image=self.fakeImage, compound='c', width=2, command=self.Revert)
        #self.playButton = Button(self.frame, text= '\u23f5', fg='green', font=('Arial', 14, 'bold'), image=self.fakeImage, compound='c', height=20, width=20)
        self.playButton = ttk.Button(self.frame, text= '\u23f5', image=self.fakeImage, compound='c', width=2)
        self.playAtTextVar = tkinter.StringVar(self.frame)
        self.durationTextVar = tkinter.StringVar(self.frame)
        self.startOffsetTextVar = tkinter.StringVar(self.frame)
        self.endOffsetTextVar = tkinter.StringVar(self.frame)
        
        self.playAtLabel = Label(self.frame, text="Play At (ms)", background="white", font=('Segoe UI', 12))
        self.playAtText = Entry(self.frame, textvariable=self.playAtTextVar, font=('Segoe UI', 12), width=50)
        
        
        self.durationLabel = Label(self.frame, text="Duration (ms)", background="white", font=('Segoe UI', 12))
        self.durationText = Entry(self.frame, textvariable=self.durationTextVar, font=('Segoe UI', 12), width=50)
        
        
        self.startOffsetLabel = Label(self.frame, text="Start Trim (ms)", background="white", font=('Segoe UI', 12))
        self.startOffsetText = Entry(self.frame, textvariable=self.startOffsetTextVar, font=('Segoe UI', 12), width=50)
        
        
        self.endOffsetLabel = Label(self.frame, text="End Trim (ms)", background="white", font=('Segoe UI', 12))
        self.endOffsetText = Entry(self.frame, textvariable=self.endOffsetTextVar, font=('Segoe UI', 12), width=50)

        self.applyButton = ttk.Button(self.frame, text="Apply", command=self.ApplyChanges)
        
        self.titleLabel.pack()
       
        
    def SetAudio(self, audio):
        self.audio = audio
        self.trackInfo = audio.GetTrackInfo()
        self.titleLabel.configure(text=f"Info for {audio.GetId()}.wem")
        #self.revertButton.configure(command=partial(self.RevertFunc, audio.GetShortId()))
        self.playButton.configure(text= '\u23f5')
        self.revertButton.pack_forget()
        self.playButton.pack_forget()
        self.applyButton.pack_forget()
        def resetButtonIcon(button):
            button.configure(text= '\u23f5')
        def pressButton(button, fileID, callback):
            if button['text'] == '\u23f9':
                button.configure(text= '\u23f5')
            else:
                button.configure(text= '\u23f9')
            self.PlayFunc(fileID, callback)
        self.playButton.configure(command=partial(pressButton, self.playButton, audio.GetShortId(), partial(resetButtonIcon, self.playButton)))
        if self.trackInfo is not None:
            self.playAtText.delete(0, 'end')
            self.durationText.delete(0, 'end')
            self.startOffsetText.delete(0, 'end')
            self.endOffsetText.delete(0, 'end')
            self.playAtText.insert(END, f"{self.trackInfo.playAt}")
            self.durationText.insert(END, f"{self.trackInfo.sourceDuration}")
            self.startOffsetText.insert(END, f"{self.trackInfo.beginTrimOffset}")
            self.endOffsetText.insert(END, f"{self.trackInfo.endTrimOffset}")
            self.playAtLabel.pack()
            self.playAtText.pack()
            self.durationLabel.pack()
            self.durationText.pack()
            self.startOffsetLabel.pack()
            self.startOffsetText.pack()
            self.endOffsetLabel.pack()
            self.endOffsetText.pack()
        self.revertButton.pack(side="left")
        self.playButton.pack(side="left")
        if self.trackInfo is not None:
            self.applyButton.pack(side="left")
        else:
            self.playAtLabel.forget()
            self.playAtText.forget()
            self.durationLabel.forget()
            self.durationText.forget()
            self.startOffsetLabel.forget()
            self.startOffsetText.forget()
            self.endOffsetLabel.forget()
            self.endOffsetText.forget()
            self.applyButton.forget()
            
    def Revert(self):
        self.audio.RevertModifications()
        self.trackInfo.RevertModifications()
        if self.trackInfo is not None:
            self.playAtText.delete(0, 'end')
            self.durationText.delete(0, 'end')
            self.startOffsetText.delete(0, 'end')
            self.endOffsetText.delete(0, 'end')
            self.playAtText.insert(END, f"{self.trackInfo.playAt}")
            self.durationText.insert(END, f"{self.trackInfo.sourceDuration}")
            self.startOffsetText.insert(END, f"{self.trackInfo.beginTrimOffset}")
            self.endOffsetText.insert(END, f"{self.trackInfo.endTrimOffset}")
        
    def ApplyChanges(self):
        newTrackInfo = copy.deepcopy(self.trackInfo)
        newTrackInfo.SetData(playAt=float(self.playAtTextVar.get()), beginTrimOffset=float(self.startOffsetTextVar.get()), endTrimOffset=float(self.endOffsetTextVar.get()), sourceDuration=float(self.durationTextVar.get()))
        self.audio.SetTrackInfo(newTrackInfo)
        self.trackInfo = newTrackInfo
        
class EventWindow:

    def __init__(self, parent):
        self.frame = Frame(parent)
        #self.frame.title(f"Info for {self.audio.GetId()}")
        self.frame.configure(background="white")
        
        #self.frame.geometry("410x45")
        #self.frame.attributes('-topmost', True)
        
        self.titleLabel = Label(self.frame, background="white", font=('Segoe UI', 14))
        
        self.playAtTextVar = tkinter.StringVar(self.frame)
        self.durationTextVar = tkinter.StringVar(self.frame)
        self.startOffsetTextVar = tkinter.StringVar(self.frame)
        self.endOffsetTextVar = tkinter.StringVar(self.frame)
        
        self.playAtLabel = Label(self.frame, text="Play At (ms)", background="white", font=('Segoe UI', 12))
        self.playAtText = Entry(self.frame, textvariable=self.playAtTextVar, font=('Segoe UI', 12), width=50)
        
        self.durationLabel = Label(self.frame, text="Duration (ms)", background="white", font=('Segoe UI', 12))
        self.durationText = Entry(self.frame, textvariable=self.durationTextVar, font=('Segoe UI', 12), width=50)
        
        self.startOffsetLabel = Label(self.frame, text="Start Trim (ms)", background="white", font=('Segoe UI', 12))
        self.startOffsetText = Entry(self.frame, textvariable=self.startOffsetTextVar, font=('Segoe UI', 12), width=50)
        
        self.endOffsetLabel = Label(self.frame, text="End Trim (ms)", background="white", font=('Segoe UI', 12))
        self.endOffsetText = Entry(self.frame, textvariable=self.endOffsetTextVar, font=('Segoe UI', 12), width=50)
        self.revertButton = ttk.Button(self.frame, text="Revert", command=self.Revert)
        self.applyButton = ttk.Button(self.frame, text="Apply", command=self.ApplyChanges)
        
        self.titleLabel.pack()
        
        self.playAtLabel.pack()
        self.playAtText.pack()
        self.durationLabel.pack()
        self.durationText.pack()
        self.startOffsetLabel.pack()
        self.startOffsetText.pack()
        self.endOffsetLabel.pack()
        self.endOffsetText.pack()
        self.revertButton.pack(side="left")
        self.applyButton.pack(side="left")
        
    def SetTrackInfo(self, trackInfo):
        self.titleLabel.configure(text=f"Info for Event {trackInfo.GetId()}")
        self.trackInfo = trackInfo
        self.playAtText.delete(0, 'end')
        self.durationText.delete(0, 'end')
        self.startOffsetText.delete(0, 'end')
        self.endOffsetText.delete(0, 'end')
        self.playAtText.insert(END, f"{self.trackInfo.playAt}")
        self.durationText.insert(END, f"{self.trackInfo.sourceDuration}")
        self.startOffsetText.insert(END, f"{self.trackInfo.beginTrimOffset}")
        self.endOffsetText.insert(END, f"{self.trackInfo.endTrimOffset}")
        
    def Revert(self):
        self.trackInfo.RevertModifications()
        self.playAtText.delete(0, 'end')
        self.durationText.delete(0, 'end')
        self.startOffsetText.delete(0, 'end')
        self.endOffsetText.delete(0, 'end')
        self.playAtText.insert(END, f"{self.trackInfo.playAt}")
        self.durationText.insert(END, f"{self.trackInfo.sourceDuration}")
        self.startOffsetText.insert(END, f"{self.trackInfo.beginTrimOffset}")
        self.endOffsetText.insert(END, f"{self.trackInfo.endTrimOffset}")
        
    def ApplyChanges(self):
        self.trackInfo.SetData(playAt=float(self.playAtTextVar.get()), beginTrimOffset=float(self.startOffsetTextVar.get()), endTrimOffset=float(self.endOffsetTextVar.get()), sourceDuration=float(self.durationTextVar.get()))

class MainWindow:

    def __init__(self, fileHandler, soundHandler):
        self.fileHandler = fileHandler
        self.soundHandler = soundHandler
        self.tableInfo = {}
        self.bankItems = {}
        self.audioItems = {}
        self.musicTrackItems = {}
        self.eventItems = {}
        self.stringItems = {}
        self.stringFileItems = {}
        
        self.root = Tk()
        self.root.configure(bg="white")
        
        self.fakeImage = tkinter.PhotoImage(width=1, height=1)
        
        self.titleCanvas = Canvas(self.root, width=WINDOW_WIDTH, height=30)
        self.searchText = tkinter.StringVar(self.root)
        self.searchBar = Entry(self.titleCanvas, textvariable=self.searchText, font=('Arial', 16))
        self.titleCanvas.pack(side="top")
        
        self.upButton = ttk.Button(self.titleCanvas, text='^', image=self.fakeImage, compound='c', width=2, command=self.SearchUp)
        self.downButton = ttk.Button(self.titleCanvas, text='v', image=self.fakeImage, compound='c', width=2, command=self.SearchDown)
        
        self.searchLabel = ttk.Label(self.titleCanvas, background="white", width=10, font=('Segoe UI', 12), justify="center")
        
        self.titleCanvas.create_text(WINDOW_WIDTH-425, 0, text="\u2315", fill='gray', font=('Arial', 20), anchor='nw')
        self.titleCanvas.create_window(WINDOW_WIDTH-350, 3, window=self.searchBar, anchor='nw')
        self.titleCanvas.create_window(WINDOW_WIDTH-375, 5, window=self.upButton, anchor='nw')
        self.titleCanvas.create_window(WINDOW_WIDTH-400, 5, window=self.downButton, anchor='nw')
        self.titleCanvas.create_window(WINDOW_WIDTH-100, 5, window=self.searchLabel, anchor='nw')

        self.scrollBar = Scrollbar(self.root, orient=VERTICAL)
        
        self.titleCanvas.pack(side="top")
        
        self.detached_items = []
        self.searchResults = []
        self.searchResultIndex = 0
        
        self.treeview = ttk.Treeview(self.root, columns=("type",), height=WINDOW_HEIGHT-100)
        self.treeview.pack(side="left")
        self.scrollBar.pack(side="left", fill="y")
        self.treeview.heading("#0", text="File")
        self.treeview.column("#0", width=250)
        self.treeview.column("type", width=100)
        self.treeview.heading("type", text="Type")
        self.treeview.configure(yscrollcommand=self.scrollBar.set)
        self.treeview.bind("<<TreeviewSelect>>", self.ShowInfoWindow)
        self.treeview.bind("<Double-Button-1>", self.PlayAudioDoubleClick)
        self.scrollBar['command'] = self.treeview.yview
        
        self.entryInfoPanel = Frame(self.root, width=int(WINDOW_WIDTH/3), bg="white")
        self.entryInfoPanel.pack(side="left", fill="both")
        
        self.audioInfoWindow = AudioSourceWindow(self.entryInfoPanel, self.RevertAudio, self.PlayAudio)
        self.eventInfoWindow = EventWindow(self.entryInfoPanel)
        self.stringInfoWindow = StringEntryWindow(self.entryInfoPanel)
        
        self.root.title("Helldivers 2 Audio Modder")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        
        self.rightClickMenu = Menu(self.root, tearoff=0)
        self.rightClickID = 0

        self.menu = Menu(self.root, tearoff=0)
        
        self.currentView = StringVar()
        self.currentView.set("SourceView")
        self.viewMenu = Menu(self.menu, tearoff=0)
        self.viewMenu.add_radiobutton(label="Sources", variable=self.currentView, value="SourceView", command=self.CreateSourceView)
        self.viewMenu.add_radiobutton(label="Hierarchy", variable=self.currentView, value="HierarchyView", command=self.CreateHierarchyView)
        
        self.currentLanguage = StringVar()
        self.currentLanguage.set("English (US)")
        self.optionsMenu = Menu(self.menu, tearoff=0)
        self.languageMenu = Menu(self.optionsMenu, tearoff=0)
        self.optionsMenu.add_cascade(label="Game Text Language", menu=self.languageMenu)
        for language in _LANGUAGE_MAPPING:
            self.languageMenu.add_radiobutton(label=language, variable=self.currentLanguage, value=language, command=self.SetLanguage)
        
        self.fileMenu = Menu(self.menu, tearoff=0)
        self.fileMenu.add_command(label="Load Archive", command=self.LoadArchive)
        self.fileMenu.add_command(label="Save Archive", command=self.SaveArchive)
        self.fileMenu.add_command(label="Write Patch", command=self.WritePatch)
        self.fileMenu.add_command(label="Import Patch File", command=self.LoadPatch)
        self.fileMenu.add_command(label="Import .wems", command=self.LoadWems)
        
        
        self.editMenu = Menu(self.menu, tearoff=0)
        self.editMenu.add_command(label="Revert All Changes", command=self.RevertAll)
        
        self.dumpMenu = Menu(self.menu, tearoff=0)
        self.dumpMenu.add_command(label="Dump all as .wav", command=self.DumpAllAsWav)
        self.dumpMenu.add_command(label="Dump all as .wem", command=self.DumpAllAsWem)
        
        self.menu.add_cascade(label="File", menu=self.fileMenu)
        self.menu.add_cascade(label="Edit", menu=self.editMenu)
        self.menu.add_cascade(label="Dump", menu=self.dumpMenu)
        self.menu.add_cascade(label="View", menu=self.viewMenu)
        self.menu.add_cascade(label="Options", menu=self.optionsMenu)
        self.root.config(menu=self.menu)
        self.treeview.bind_all("<Button-3>", self._on_rightclick)
        self.searchBar.bind("<Return>", self._on_enter)
        self.root.resizable(False, False)
        self.root.mainloop()
        
    def _on_enter(self, event):
        self.Search()
        
    def print_element(self, event):
        if len(self.treeview.selection()) == 1:
            print(self.treeview.item(self.treeview.selection()))
            
    def PlayAudioDoubleClick(self, event):
        if len(self.treeview.selection()) == 1 and self.treeview.item(self.treeview.selection())['values'][0] == "Audio Source":
            self.PlayAudio(self.treeview.item(self.treeview.selection())['tags'][0])
            
    def SetLanguage(self):
        global _LANGUAGE
        oldLanguage = _LANGUAGE
        _LANGUAGE = LanguageLookup(self.currentLanguage.get())
        if _LANGUAGE != oldLanguage:
            if self.currentView.get() == "SourceView":
                self.CreateSourceView()
            else:
                self.CreateHierarchyView()
    
    def SearchDown(self):
        if len(self.searchResults) > 0:
            self.searchResultIndex += 1
            if self.searchResultIndex == len(self.searchResults):
                self.searchResultIndex = 0
            self.treeview.selection_set(self.searchResults[self.searchResultIndex])
            self.treeview.see(self.searchResults[self.searchResultIndex])
            self.searchLabel['text'] = f"{self.searchResultIndex+1}/{len(self.searchResults)}"

    def SearchUp(self):
        if len(self.searchResults) > 0:
            self.searchResultIndex -= 1
            if self.searchResultIndex == -1:
                self.searchResultIndex = len(self.searchResults)-1
            self.treeview.selection_set(self.searchResults[self.searchResultIndex])
            self.treeview.see(self.searchResults[self.searchResultIndex])
            self.searchLabel['text'] = f"{self.searchResultIndex+1}/{len(self.searchResults)}"

    def ShowInfoWindow(self, event):
        if len(self.treeview.selection()) != 1:
            return
        _type = self.treeview.item(self.treeview.selection())['values'][0]
        for child in self.entryInfoPanel.winfo_children():
            child.forget()
        if _type == "String":
            self.stringInfoWindow.SetStringEntry(self.fileHandler.GetStringEntryByID(self.treeview.item(self.treeview.selection())['tags'][0]))
            self.stringInfoWindow.frame.pack()
        elif _type == "Audio Source":
            self.audioInfoWindow.SetAudio(self.fileHandler.GetAudioByID(self.treeview.item(self.treeview.selection())['tags'][0]))
            self.audioInfoWindow.frame.pack()
        elif _type == "Event":
            self.eventInfoWindow.SetTrackInfo(self.fileHandler.GetEventByID(self.treeview.item(self.treeview.selection())['tags'][0]))
            self.eventInfoWindow.frame.pack()
        elif _type == "Music Track":
            pass
        elif _type == "Sound Bank":
            pass
        elif _type == "Text Bank":
            pass
        
    def _on_rightclick(self, event):
        try:
            types = {self.treeview.item(i)['values'][0] for i in self.treeview.selection()}
            self.rightClickMenu.delete(0, "end")
            self.rightClickID = self.treeview.item(self.treeview.selection()[-1])['tags'][0]
            self.rightClickMenu.add_command(label="Copy File ID" if len(self.treeview.selection()) == 1 else "Copy File IDs", command=self.CopyID)
            if "Audio Source" in types:
                self.rightClickMenu.add_command(label="Dump As .wem" if len(self.treeview.selection()) == 1 else "Dump Selected As .wem", command=self.DumpAsWem)
                self.rightClickMenu.add_command(label="Dump As .wav" if len(self.treeview.selection()) == 1 else "Dump Selected As .wav", command=self.DumpAsWav)
            self.rightClickMenu.tk_popup(event.x_root, event.y_root)
        except (AttributeError, IndexError):
            pass
        finally:
            self.rightClickMenu.grab_release()
            
    def PrintTrackInfo(self):
        audio = self.fileHandler.GetAudioByID(self.rightClickID)
        info = audio.GetTrackInfo()
        if info is not None:
            print(f"Source ID: {info.sourceId}\nPlay At: {info.playAt}ms\nDuration: {info.sourceDuration}ms\nStart Offset: {info.beginTrimOffset}ms\nEnd Offset: {info.endTrimOffset}ms\n")
        else:
            print("No track info available\n")
            
    def CopyID(self):
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join([f"{self.treeview.item(i)['tags'][0]}" for i in self.treeview.selection()]))
        self.root.update()
        
    def DumpAsWem(self):
        if len(self.treeview.selection()) == 1:
            self.fileHandler.DumpAsWem(self.rightClickID)
        else:
            self.fileHandler.DumpMultipleAsWem([self.treeview.item(i)['tags'][0] for i in self.treeview.selection()])
        
    def DumpAsWav(self):
        if len(self.treeview.selection()) == 1:
            self.fileHandler.DumpAsWav(self.rightClickID)
        else:
            self.fileHandler.DumpMultipleAsWav([self.treeview.item(i)['tags'][0] for i in self.treeview.selection()])
        
    def CreateTableRow(self, entry, parentItem=""):
        if entry is None: return
        treeEntry = self.treeview.insert(parentItem, END, tag=entry.GetId())
        if isinstance(entry, WwiseBank):
            name = entry.Dep.Data.split('/')[-1]
            self.bankItems[entry.GetId()] = treeEntry
            _type = "Sound Bank"
        elif isinstance(entry, TextBank):
            name = f"{entry.GetId()}.text"
            self.stringFileItems[entry.GetId()] = treeEntry
            _type = "Text Bank"
        elif isinstance(entry, AudioSource):
            name = f"{entry.GetId()}.wem"
            _type = "Audio Source"
        elif isinstance(entry, TrackInfoStruct):
            name = f"Event {entry.GetId()}"
            _type = "Event"
        elif isinstance(entry, StringEntry):
            _type = "String"
            name = entry.GetText()[:20]
            self.stringItems[entry.GetId()] = treeEntry
        elif isinstance(entry, MusicTrack):
            _type = "Music Track"
            name = f"Track {entry.GetId()}"
        self.treeview.item(treeEntry, text=name)
        self.treeview.item(treeEntry, values=(_type,))
        return treeEntry
        
    def ClearSearch(self):
        self.searchResultIndex = 0
        self.searchResults.clear()
        self.searchLabel['text'] = ""
        self.searchText.set("")
            
    def CreateHierarchyView(self):
        self.ClearSearch()
        self.treeview.delete(*self.treeview.get_children())
        bankDict = self.fileHandler.GetWwiseBanks()
        for bank in bankDict.values():
            bankEntry = self.CreateTableRow(bank)
            for hierEntry in bank.hierarchy.entries.values():
                if isinstance(hierEntry, MusicTrack):
                    trackEntry = self.CreateTableRow(hierEntry, bankEntry)
                    for source in hierEntry.sources:
                        if source.pluginId == 0x00040001:
                            self.CreateTableRow(self.fileHandler.GetAudioByID(source.sourceId), trackEntry)
                    for info in hierEntry.trackInfo:
                        if info.eventId != 0:
                            self.CreateTableRow(info, trackEntry)
                elif isinstance(hierEntry, Sound):
                    if hierEntry.sources[0].pluginId == 0x00040001:
                        self.CreateTableRow(self.fileHandler.GetAudioByID(hierEntry.sources[0].sourceId), bankEntry)
        for entry in self.fileHandler.FileReader.TextBanks.values():
            if entry.Language == _LANGUAGE:
                e = self.CreateTableRow(entry)
                for stringId in entry.StringIds:
                    self.CreateTableRow(self.fileHandler.FileReader.StringEntries[_LANGUAGE][stringId], e)
                
    def CreateSourceView(self):
        self.ClearSearch()
        self.treeview.delete(*self.treeview.get_children())
        bankDict = self.fileHandler.GetWwiseBanks()
        for bank in bankDict.values():
            bankEntry = self.CreateTableRow(bank)
            for hierEntry in bank.hierarchy.entries.values():
                for source in hierEntry.sources:
                    if source.pluginId == 0x00040001:
                        self.CreateTableRow(self.fileHandler.GetAudioByID(source.sourceId), bankEntry)
        for entry in self.fileHandler.FileReader.TextBanks.values():
            if entry.Language == _LANGUAGE:
                e = self.CreateTableRow(entry)
                for stringId in entry.StringIds:
                    self.CreateTableRow(self.fileHandler.FileReader.StringEntries[_LANGUAGE][stringId], e)
                
    def RecurSearch(self, searchText, item):
        s = self.treeview.item(item)['text']
        match = s.startswith(searchText) or s.endswith(searchText)
        children = self.treeview.get_children(item)
        if match: self.searchResults.append(item)
        if len(children) == 0:
            return match
        else:
            for child in children:
                match = self.RecurSearch(searchText, child) or match
            if match:
                return True
            return False

    def Search(self):
        self.searchResults.clear()
        self.searchResultIndex = 0
        text = self.searchText.get()
        if text != "":
            for child in self.treeview.get_children():
                self.RecurSearch(text, child)
            if len(self.searchResults) > 0:
                self.treeview.selection_set(self.searchResults[self.searchResultIndex])
                self.treeview.see(self.searchResults[self.searchResultIndex])
                self.searchLabel['text'] = f"1/{len(self.searchResults)}"
            else:
                self.searchLabel['text'] = "0/0"
        else:
            self.searchLabel['text'] = ""

    def LoadArchive(self):
        self.soundHandler.KillSound()
        if self.fileHandler.LoadArchiveFile():
            self.ClearSearch()
            if self.currentView.get() == "SourceView":
                self.CreateSourceView()
            else:
                self.CreateHierarchyView()
            for child in self.entryInfoPanel.winfo_children():
                child.forget()
            #self.Update()
        
    def SaveArchive(self):
        self.soundHandler.KillSound()
        self.fileHandler.SaveArchiveFile()
        
    def LoadWems(self):
        self.soundHandler.KillSound()
        self.fileHandler.LoadWems()
        
    def DumpAllAsWem(self):
        self.soundHandler.KillSound()
        self.fileHandler.DumpAllAsWem()
        
    def DumpAllAsWav(self):
        self.soundHandler.KillSound()
        self.fileHandler.DumpAllAsWav()
        
    def PlayAudio(self, fileID, callback=None):
        audio = self.fileHandler.GetAudioByID(fileID)
        self.soundHandler.PlayAudio(audio.GetShortId(), audio.GetData(), callback)
        
    def RevertAudio(self, fileID):
        self.fileHandler.RevertAudio(fileID)
        
    def RevertAll(self):
        self.soundHandler.KillSound()
        self.fileHandler.RevertAll()
        
    def WritePatch(self):
        self.soundHandler.KillSound()
        self.fileHandler.WritePatch()
        
    def LoadPatch(self):
        self.soundHandler.KillSound()
        if self.fileHandler.LoadPatch():
            pass
    
def exitHandler():
    soundHandler.audio.terminate()
    

if __name__ == "__main__":
    if "Windows" in platform.platform():
        _GAME_FILE_LOCATION = LookForSteamInstallWindows()
    soundHandler = SoundHandler()
    fileHandler = FileHandler()
    atexit.register(exitHandler)
    LoadLanguageMapping()
    window = MainWindow(fileHandler, soundHandler)
    window.SetLanguage()