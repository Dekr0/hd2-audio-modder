from collections import deque
from collections.abc import Callable
import enum
from typing import Any
import uuid

# Definition import
from dataclasses import dataclass

# Module import
from imgui_bundle import imgui, portable_file_dialogs as pfd

import backend.db.db_schema_map as orm

from backend.core import AudioSource, FileHandler, HircEntry
from backend.core import SoundHandler
from backend.db.db_access import SQLiteDatabase

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
class BankViewerTableHeader(enum.StrEnum):

    DEFAULT_LABEL = "Default Label"
    FAV = ""
    HIRC_ENTRY_TYPE = "Hierarchy Type"
    PLAY = ""
    USER_DEFINED_LABEL = "User Defined Label"


class BankViewerTableType(enum.StrEnum):

    AUDIO_SOURCE       = "Audio Source"
    AUDIO_SOURCE_MUSIC = "Audio Source (Music)"
    EVENT              = "Event"
    MUSIC_SEGMENT      = "Music Segement"
    MUSIC_TRACK        = "Music Track"
    RANDOM_SEQ_CNTR    = "Random / Sequence"
    ROOT               = "Root"
    SEPARATOR          = "Separator"
    SOUNDBANK          = "Soundbank"
    STRING             = "String"
    TEXT_BANK          = "Text Bank"


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
    # source_view_root: 'HierarchyView'
    # source_views_linear: list['HierarchyView']
    hirc_view_root: 'HierarchyView'
    hirc_views_linear: list['HierarchyView']

    imgui_selection_store: imgui.SelectionBasicStorage

    hierarchy_views_banks: dict[str, dict[int, orm.HierarchyObjectView]]

    changed_hierarchy_views: dict[int, 'HierarchyView']

    source_view: bool = True


@dataclass
class MessageModalState:

    msg: str
    is_trigger: bool = False


@dataclass
class ConfirmModalState:

    msg: str
    is_trigger: bool = False
    callback: Callable[[bool], Any] | None = None


@dataclass
class AppState:

    archive_picker: FilePicker
    data_folder_picker: FolderPicker

    sound_handler: SoundHandler

    db: SQLiteDatabase | None

    setting: Setting

    font: imgui.ImFont | None
    symbol_font: imgui.ImFont | None

    bank_states: dict[str, BankViewerState]
    bank_id_to_window_name: dict[str, str]

    # callback queue
    critical_modal: MessageModalState | None
    warning_modals: deque[MessageModalState]
    confirm_modals: deque[ConfirmModalState]
    load_archives_queue: deque[Callable[..., None]]
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
    source_id: int
    default_label: str
    hirc_entry_type: BankViewerTableType
    user_defined_label: str
    children: list['HierarchyView']


def new_hirc_view_root():
    return HierarchyView(
            None,
            TREE_ROOT_VIEW_ID, None, 
            -1, -1, "", 
            BankViewerTableType.ROOT, "", [])


def new_bank_viewer_state(sound_handler: SoundHandler):
    return BankViewerState(
            uuid.uuid4().hex, # id
            FileHandler(), # backend
            FilePicker(),
            sound_handler,
            # new_hirc_view_root(), [], # source view
            new_hirc_view_root(), [], # hirc. view
            imgui.SelectionBasicStorage(),  # selection storage
            {}, # DB data
            {}  # DB change bus
        )


def new_app_state():
    sound_handler = SoundHandler()
    
    inital_state = new_bank_viewer_state(sound_handler)

    return AppState(
            FilePicker(), FolderPicker(), # picker
            sound_handler, # sound handler
            None, # db connection 
            Setting(), # setting
            None, None, # fonts
            {"Bank Viewer": inital_state}, # bank states
            {inital_state.id: "Bank Viewer"}, # window names
            None, 
            deque(), deque(), deque())
