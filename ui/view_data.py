from collections import deque
import enum
from typing import Callable
import uuid

# Definition import
from dataclasses import dataclass

# Module import
from imgui_bundle import imgui, portable_file_dialogs as pfd

from backend.core import AudioSource, FileHandler, HircEntry
from backend.core import MusicSegment, RandomSequenceContainer, Sound
from backend.core import SoundHandler

from backend.const import VORBIS
from setting import Setting


TREE_ROOT_VIEW_ID = 0


# [View Data Class]
"""
Aka. Retain mode

View Data Class is representation layer of underlying data in Wwise Bank and 
Wwise Stream.

View Data Class is meant to use for presenting information in the UI.

There is only single source of truth. The unerlying data for Wwise Bank and 
Wwise Stream stored in FileReader class

Users perform input change, input change reflect into source of truth. The UI 
immedately reflect the change by render the UI entirely.

Since it's using ImGUI, we should rework the backend to accurately encapsulate 
the hierarchy of the Soundbank because so that we can directly pump data into 
the UI. 

The main pain point right now is that each node does not know its parent. Thus, 
this make some implementation harder to do because there are more work around 
to access parent.

The second pain point is that audio source is encapsulated by `Sound` object. 
When presenting on the UI, we shouldn't just show the audio source itself 
because we can have two `Sound` object with two different ID but both of them 
contain the same audio source.
"""
class BankExplorerTableHeader(enum.StrEnum):

    DEFAULT_LABEL = "Default Label"
    FAV = ""
    HIRC_ENTRY_TYPE = "Hierarchy Type"
    PLAY = ""
    USER_DEFINED_LABEL = "User Defined Label"


class BankExplorerTableType(enum.StrEnum):

    AUDIO_SOURCE    = "Audio Source"
    EVENT           = "Event"
    MUSIC_SEGMENT   = "Music Segement"
    MUSIC_TRACK     = "Music Track"
    RANDOM_SEQ_CNTR = "Random / Sequence"
    ROOT            = "Root"
    SEPARATOR       = "Separator"
    SOUNDBANK       = "Soundbank"
    STRING          = "String"
    TEXT_BANK       = "Text Bank"


class FilePicker:

    def __init__(self):
        self.file_picker: pfd.open_file | None = None

    def schedule(self,
                 msg: str = "Select A File", 
                 default_path: str = "",
                 multi: bool = False):
        """
        @exception
        - AssertionError
            - Rescheudle before the active one is closed
        """
        if self.file_picker != None:
            raise AssertionError("Rescheudle a new file picker before the "
                                 "active one is closed")
        if multi:
            self.file_picker = pfd.open_file(
                msg, 
                default_path, 
                options=pfd.opt.multiselect)
        else:
            self.file_picker = pfd.open_file(
                msg, 
                default_path)


    def is_ready(self):
        return self.file_picker != None and self.file_picker.ready()

    def get_result(self) -> list[str]:
        if self.file_picker != None and self.file_picker.ready():
            return self.file_picker.result()
        return []

    def reset(self):
        self.file_picker = None


class FolderPicker:

    def __init__(self):
        self.folder_picker: pfd.select_folder | None = None

    def schedule(self, msg: str = "Select A Folder", default_path: str = ""):
        """
        @exception
        - AssertionError
            - Rescheudle before the active one is closed
        """
        if self.folder_picker != None:
            raise AssertionError("Rescheudle a new folder picker before the "
                                 "active one is closed")
        self.folder_picker = pfd.select_folder(msg, default_path)

    def is_ready(self):
        return self.folder_picker != None and self.folder_picker.ready()

    def get_result(self) -> str:
        if self.folder_picker != None and self.folder_picker.ready():
            return self.folder_picker.result()
        return ""

    def reset(self):
        self.folder_picker = None


@dataclass
class BankViewerState:
    
    id: str
    file_handler: FileHandler 
    archive_picker: FilePicker
    sound_handler: SoundHandler

    """
    Two separate tree storage so that there's basically no lag between switching 
    two views. Make sure they're synced with state.

    Each tree node will use a separate id for view instead of id coming from the 
    entry. 

    This id is created as tree is built.
    Example:
        a 
        |--*
        |  |
        b  c
        |
        |--*
        |  |
        h  g
    Traversal is DFS.
    Here's the following id for each node. Zero is reserved for invisible root
    - a -> 1, b -> 2, h -> 3, g -> 4, c -> 5

    The reason is mainly for eased of implementing the following features:
        - in order range based multi selection for tree
        - quick access on node in terms of query node when handling selection 
        for tree structure
    """
    source_view_root: 'HierarchyView'
    source_views_linear: list['HierarchyView']
    hirc_view_root: 'HierarchyView'
    hirc_views_linear: list['HierarchyView']

    imgui_selection_store: imgui.SelectionBasicStorage

    source_view: bool = True


@dataclass
class MessageModalState:

    msg: str
    is_trigger: bool = False


@dataclass
class AppState:

    archive_picker: FilePicker
    data_folder_picker: FolderPicker

    sound_handler: SoundHandler

    setting: Setting | None

    font: imgui.ImFont
    symbol_font: imgui.ImFont

    bank_states: list[BankViewerState]

    critical_modal: MessageModalState | None
    warning_modals: deque[MessageModalState]
# [End]


@dataclass
class HierarchyView:
    """
    view_id: int -> Row index (increment sequentially as imgui render the table )
    parent_view_id: int -> Parent row index
    """

    # Binding For Quick Access
    data: HircEntry | AudioSource | None

    view_id: int
    parent_view_id: int | None
    hirc_ul_ID: int
    default_label: str
    hirc_entry_type: BankExplorerTableType
    user_defined_label: str
    children: list['HierarchyView']


def new_hirc_view_root():
    return HierarchyView(
            None,
            TREE_ROOT_VIEW_ID, None, 
            -1, "", 
            BankExplorerTableType.ROOT, "", [])


def new_bank_explorer_states(sound_handler: SoundHandler):
    return BankViewerState(
            uuid.uuid4().hex,
            FileHandler(),
            FilePicker(), 
            sound_handler,
            new_hirc_view_root(), [],
            new_hirc_view_root(), [],
            imgui.SelectionBasicStorage())


def new_app_state(font, symbol_font):
    sound_handler = SoundHandler()
    return AppState(
            FilePicker(),
            FolderPicker(),
            sound_handler,
            None,
            font, symbol_font,
            [new_bank_explorer_states(sound_handler)],
            None, deque())


def create_bank_hierarchy_view(bank_state: BankViewerState):
    root = bank_state.hirc_view_root
    bank_hirc_views = root.children
    bank_hirc_views_linear = bank_state.hirc_views_linear

    bank_hirc_views.clear()
    bank_hirc_views_linear.clear()

    file_handler = bank_state.file_handler
    banks = file_handler.get_wwise_banks()

    contained_sounds: set[Sound] = set()
    if root.view_id != 0:
        raise AssertionError("Invisible root view must always has an `view_id`"
                             " of 0")
    idx = root.view_id

    bank_hirc_views_linear.append(root)
    idx += 1

    for bank in banks.values():
        if bank.hierarchy == None:
            # Logging
            continue

        bank_view = HierarchyView(
                None,
                idx, root.view_id,
                bank.get_id(), bank.get_name().replace("content/audio/", ""),
                BankExplorerTableType.SOUNDBANK, 
                "--", [])
        bank_hirc_views.append(bank_view)
        bank_hirc_views_linear.append(bank_view)
        idx += 1

        children = bank_view.children
        bank_idx = bank_view.view_id
        hirc_entries = bank.hierarchy.entries
        for hirc_entry in hirc_entries.values():
            if isinstance(hirc_entry, MusicSegment):
                segment_id = hirc_entry.get_id()
                segment_view = HierarchyView(
                        hirc_entry,
                        idx, bank_idx,
                        segment_id, f"Segment {segment_id}",
                        BankExplorerTableType.MUSIC_SEGMENT,
                        "", [])
                children.append(segment_view)
                bank_hirc_views_linear.append(segment_view)
                idx += 1

                segment_view_id = segment_view.view_id

                for track_id in hirc_entry.tracks:
                    track = hirc_entries[track_id]
                    track_view = HierarchyView(
                            track,
                            idx, segment_view_id, 
                            track_id, f"Track {track_id}", 
                            BankExplorerTableType.MUSIC_TRACK, 
                            "", [])
                    segment_view.children.append(track_view)
                    bank_hirc_views_linear.append(track_view)
                    idx += 1 

                    track_view_id = track_view.view_id
                    for source_struct in track.sources:
                        if source_struct.plugin_id != VORBIS:
                            continue

                        source_id = source_struct.source_id
                        audio_source = file_handler.get_audio_by_id(source_id)
                        if  audio_source == None:
                            # Logging?
                            continue

                        source_view = HierarchyView(
                                audio_source,
                                idx, track_view_id,
                                source_id, f"{source_id}.wem",
                                BankExplorerTableType.AUDIO_SOURCE,
                                "", [])
                        track_view.children.append(source_view)
                        bank_hirc_views_linear.append(source_view)
                        idx += 1 

                    for info in track.track_info:
                        if info.event_id == 0:
                            # Logging?
                            continue

                        info_id = info.get_id()
                        info_view = HierarchyView(
                                info,
                                idx, track_view_id,
                                info_id, f"Event {info_id}", 
                                BankExplorerTableType.EVENT, 
                                "", [])
                        track_view.children.append(info_view)
                        bank_hirc_views_linear.append(info_view)
                        idx += 1

            elif isinstance(hirc_entry, RandomSequenceContainer):
                cntr_id = hirc_entry.get_id()
                cntr_view = HierarchyView(
                        hirc_entry,
                        idx, bank_idx,
                        cntr_id, f"Random / Sequence Container {cntr_id}",
                        BankExplorerTableType.RANDOM_SEQ_CNTR,
                        "", [])
                children.append(cntr_view)
                bank_hirc_views_linear.append(cntr_view)
                idx += 1

                cntr_view_id = cntr_view.view_id
                for entry_id in hirc_entry.contents:
                    entry = hirc_entries[entry_id] 
                    if not isinstance(entry, Sound):
                        # Logging
                        continue

                    if len(entry.sources) <= 0 or entry.sources[0].plugin_id != VORBIS:
                        continue

                    source_id = entry.sources[0].source_id
                    audio_source = file_handler.get_audio_by_id(source_id)
                    if audio_source == None:
                        # Logging?
                        continue

                    contained_sounds.add(entry)

                    source_view = HierarchyView(
                            audio_source,
                            idx, cntr_view_id,
                            source_id, f"{source_id}.wem",
                            BankExplorerTableType.AUDIO_SOURCE,
                            "", [])
                    cntr_view.children.append(source_view)
                    bank_hirc_views_linear.append(source_view)
                    idx += 1
                
        for hirc_entry in hirc_entries.values():
            if not isinstance(hirc_entry, Sound) or hirc_entry in contained_sounds:
                continue

            source_id = hirc_entry.sources[0].source_id
            audio_source = file_handler.get_audio_by_id(source_id)
            if audio_source == None:
                # Logging?
                continue

            source_view = HierarchyView(
                    audio_source,
                    idx, bank_idx,
                    source_id, f"{source_id}.wem",
                    BankExplorerTableType.AUDIO_SOURCE,
                    "", [])
            children.append(source_view)
            bank_hirc_views_linear.append(source_view)
            idx += 1


def create_bank_source_view(bank_viewer_state: BankViewerState):
    root = bank_viewer_state.source_view_root
    bank_source_views = root.children
    bank_source_views_linear = bank_viewer_state.source_views_linear

    bank_source_views.clear()
    bank_source_views_linear.clear()

    file_handler = bank_viewer_state.file_handler
    banks = file_handler.get_wwise_banks()

    memo: set[int] = set()
    if root.view_id != 0:
        raise AssertionError("Invisible root view must always has an `view_id`"
                             " of 0")
    idx = root.view_id

    bank_source_views_linear.append(root)
    idx += 1

    for bank in banks.values():
        if bank.hierarchy == None:
            # Logging
            continue
        memo.clear()

        bank_view = HierarchyView(
                None,
                idx, root.view_id,
                bank.get_id(), bank.get_name().replace("content/audio/", ""),
                BankExplorerTableType.SOUNDBANK, 
                "--", 
                [])
        bank_source_views.append(bank_view)
        bank_source_views_linear.append(bank_view)
        idx += 1

        children = bank_view.children 
        bank_idx = bank_view.view_id

        for hirc_entry in bank.hierarchy.entries.values():
            if len(hirc_entry.sources) <= 0:
                continue

            for source in hirc_entry.sources:
                source_id = source.source_id
                if source.plugin_id != VORBIS or source_id in memo:
                    continue

                audio_source = file_handler.get_audio_by_id(source_id)
                if audio_source == None:
                    # Logging
                    continue

                source_view = HierarchyView(
                    audio_source,
                    idx, bank_idx, 
                    source_id, f"{source_id}.wem",
                    BankExplorerTableType.AUDIO_SOURCE,
                    "", [])
                children.append(source_view)
                bank_source_views_linear.append(source_view)
                idx += 1

                memo.add(source_id)
