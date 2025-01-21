import enum
import uuid

from collections import deque
from dataclasses import dataclass

from imgui_bundle import imgui

import backend.db.db_schema_map as orm

from backend.util import copy_to_clipboard
from backend.const import VORBIS
from backend.core import HircEntry, MusicSegment, RandomSequenceContainer, Sound
from backend.core import AudioSource 
from backend.core import FileHandler, SoundHandler
from ui.file_picker import FilePickerTask
from ui.event_loop import DBOperationTask

TREE_ROOT_VID = 0


# [View Data Class]
"""
Aka. Retain mode

View Data Class is representation layer of underlying data in Wwise Bank and 
Wwise Stream.

View Data Class is meant to use for presenting information in the UI.

Since it's using ImGUI, we should rework the backend to accurately encapsulate 
the hierarchy of the Soundbank so that we can directly pump data into the UI. 

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
    REV = ""
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


@dataclass
class HircView:
    """
    view_id: int -> Row index (increment sequentially as imgui render the table )
    parent_view_id: int -> Parent row index
    """

    # Binding For Quick Access
    data: HircEntry | AudioSource | None

    vid: int
    parent_vid: int | None
    hirc_ul_ID: int # For Hirc. object 
    default_label: str
    hirc_obj_type: BankViewerTableType
    usr_defined_label: str
    children: list['HircView']
    modified: bool = False


class BankViewerState:

    def __init__(self, sound_handler: SoundHandler):
        self.id = uuid.uuid4().hex
        self.file_picker_task: deque[FilePickerTask] = deque(maxlen=1)
        self.file_handler: FileHandler = FileHandler()
        self.sound_handler = sound_handler

        """
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
        self.hirc_view_root = HircView(
            data = None,
            vid = TREE_ROOT_VID,
            parent_vid = None,
            hirc_ul_ID = -1,
            default_label = "",
            hirc_obj_type = BankViewerTableType.ROOT,
            usr_defined_label = "",
            children = []
        )
        self.hirc_view_list = []
        
        self.imgui_selection_store = imgui.SelectionBasicStorage()
        self.mut_hirc_views: dict[int, HircView] = {}
        self.src_view: bool = True
        self.locked: bool = False

    def close(self):
        while len(self.file_picker_task) > 0:
            task = self.file_picker_task.popleft()
            task.cancel = True
    
    def create_bank_hirc_view(self, hirc_records: dict[int, orm.HircObjRecord]):
        """
        @exception
        - AssertionError
        """
        root = self.hirc_view_root
        hirc_views = root.children
        hirc_views_list = self.hirc_view_list
        hirc_records = hirc_records

        hirc_views.clear()
        hirc_views_list.clear()

        file_handler = self.file_handler
        banks = file_handler.get_wwise_banks()

        contained_sounds: set[Sound] = set()
        if root.vid != 0:
            raise AssertionError(
                "Invisible root view must always has an `view_id` of 0")

        idx = root.vid

        hirc_views_list.append(root)
        idx += 1

        for bank in banks.values():
            if bank.hierarchy == None:
                # Logging
                continue
            bank_name = bank.get_name().replace("/", "_") \
                                       .replace("\x00", "")

            bank_view = HircView(
                    data = None,
                    vid = idx, 
                    parent_vid = root.vid,
                    hirc_ul_ID = bank.get_id(), 
                    default_label = bank_name,
                    hirc_obj_type = BankViewerTableType.SOUNDBANK, 
                    usr_defined_label = "--", 
                    children = [])
            hirc_views.append(bank_view)
            hirc_views_list.append(bank_view)
            idx += 1

            children = bank_view.children
            bank_idx = bank_view.vid
            hirc_entries = bank.hierarchy.entries
            for hirc_entry in hirc_entries.values():
                if isinstance(hirc_entry, MusicSegment):
                    segment_id = hirc_entry.get_id()

                    segment_label = ""
                    if segment_id in hirc_records:
                        segment_label = hirc_records[segment_id].label

                    segment_view = HircView(
                            data = hirc_entry,
                            vid = idx, 
                            parent_vid = bank_idx,
                            hirc_ul_ID = segment_id, 
                            default_label = f"Segment {segment_id}",
                            hirc_obj_type = BankViewerTableType.MUSIC_SEGMENT,
                            usr_defined_label = segment_label, 
                            children = [])
                    children.append(segment_view)
                    hirc_views_list.append(segment_view)
                    idx += 1

                    segment_view_id = segment_view.vid

                    for track_id in hirc_entry.tracks:
                        track = hirc_entries[track_id]

                        track_label = ""
                        if track_id in hirc_records:
                            track_label = hirc_records[track_id].label

                        track_view = HircView(
                                data = track,
                                vid = idx, 
                                parent_vid = segment_view_id, 
                                hirc_ul_ID = track_id, 
                                default_label = f"Track {track_id}", 
                                hirc_obj_type = BankViewerTableType.MUSIC_TRACK, 
                                usr_defined_label = track_label, 
                                children = [])
                        segment_view.children.append(track_view)
                        hirc_views_list.append(track_view)
                        idx += 1 

                        track_view_id = track_view.vid
                        for source_struct in track.sources:
                            if source_struct.plugin_id != VORBIS:
                                continue

                            source_id = source_struct.source_id
                            audio_source = file_handler.get_audio_by_id(source_id)
                            if audio_source == None:
                                # Logging?
                                continue

                            source_view = HircView(
                                    data = audio_source,
                                    vid = idx, 
                                    parent_vid = track_view_id,
                                    hirc_ul_ID = track_id,
                                    default_label = f"{source_id}.wem",
                                    hirc_obj_type = BankViewerTableType.AUDIO_SOURCE_MUSIC,
                                    usr_defined_label = "", 
                                    children = [])
                            track_view.children.append(source_view)
                            hirc_views_list.append(source_view)
                            idx += 1 

                        for info in track.track_info:
                            if info.event_id == 0:
                                # Logging?
                                continue

                            info_id = info.get_id()

                            info_label = ""
                            if info_id in hirc_records:
                                info_label = hirc_records[info_id].label

                            info_view = HircView(
                                    data = info,
                                    vid = idx, 
                                    parent_vid = track_view_id,
                                    hirc_ul_ID = info_id,
                                    default_label = f"Event {info_id}", 
                                    hirc_obj_type = BankViewerTableType.EVENT, 
                                    usr_defined_label = info_label, 
                                    children = [])
                            track_view.children.append(info_view)
                            hirc_views_list.append(info_view)
                            idx += 1

                elif isinstance(hirc_entry, RandomSequenceContainer):
                    cntr_id = hirc_entry.get_id()

                    cntr_label = ""
                    if cntr_id in hirc_records:
                        cntr_label = hirc_records[cntr_id].label

                    cntr_view = HircView(
                            data = hirc_entry,
                            vid = idx, 
                            parent_vid = bank_idx,
                            hirc_ul_ID = cntr_id,
                            default_label = f"Random / Sequence Container {cntr_id}",
                            hirc_obj_type = BankViewerTableType.RANDOM_SEQ_CNTR,
                            usr_defined_label = cntr_label, 
                            children = [])
                    children.append(cntr_view)
                    hirc_views_list.append(cntr_view)
                    idx += 1

                    cntr_view_id = cntr_view.vid
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

                        sound_label = ""
                        if entry_id in hirc_records:
                            sound_label = hirc_records[entry_id].label

                        source_view = HircView(
                                data = audio_source,
                                vid = idx, 
                                parent_vid = cntr_view_id,
                                hirc_ul_ID = entry.hierarchy_id,
                                default_label = f"{source_id}.wem",
                                hirc_obj_type = BankViewerTableType.AUDIO_SOURCE,
                                usr_defined_label = sound_label, 
                                children = [])
                        cntr_view.children.append(source_view)
                        hirc_views_list.append(source_view)
                        idx += 1
                    
            for hirc_entry in hirc_entries.values():
                if not isinstance(hirc_entry, Sound) or hirc_entry in contained_sounds:
                    continue

                source_id = hirc_entry.sources[0].source_id
                audio_source = file_handler.get_audio_by_id(source_id)
                if audio_source == None:
                    # Logging?
                    continue

                sound_label = ""
                if hirc_entry.hierarchy_id in hirc_records:
                    sound_label = hirc_records[hirc_entry.hierarchy_id].label

                source_view = HircView(
                        data = audio_source,
                        vid = idx, 
                        parent_vid = bank_idx,
                        hirc_ul_ID = hirc_entry.hierarchy_id, 
                        default_label = f"{source_id}.wem",
                        hirc_obj_type = BankViewerTableType.AUDIO_SOURCE,
                        usr_defined_label = sound_label, 
                        children = [])

                children.append(source_view)
                hirc_views_list.append(source_view)
                idx += 1

    @staticmethod
    def unfold_selection(selects: list[HircView]):
        fold_select_set: set[int] = set([select.vid for select in selects])
        unfold_select_set: set[int] = set()
        unfold_select_list: list[HircView] = []
        for select in selects:
            parent_vid = select.parent_vid
            if parent_vid not in fold_select_set:
                unfold_select_set.add(select.vid)
                unfold_select_list.append(select)
        return unfold_select_list

    def _get_selection_binding(self):
        selects: list[HircView] = []
        selects = [hirc_view for hirc_view in self.hirc_view_list 
                   if self.imgui_selection_store.contains(hirc_view.vid)]
    
        return selects

    def copy_audio_entry(self, hirc_view: HircView, label: bool = False):
        selects = self._get_selection_binding()

        if len(selects) == 0:
            selects = [hirc_view]

        audio_source_vid_set: set[int] = set()
        queue: deque[HircView] = deque()
        content = "" 
        for select in selects:
            if len(queue) > 0:
                raise AssertionError()
            queue.append(select)
            while len(queue) > 0:
                top = queue.popleft()
                if top.hirc_obj_type == BankViewerTableType.AUDIO_SOURCE:
                    if not isinstance(top.data, AudioSource):
                        raise AssertionError()

                    if top.vid in audio_source_vid_set:
                        continue

                    source_id = top.data.get_short_id()
                    user_defined_label = top.usr_defined_label
                    audio_source_vid_set.add(top.vid)
                    if label:
                        content += f"{source_id}: \"{user_defined_label}\"\n"
                    else:
                        content += f"{source_id}\n"
                    continue

                for c_binding in top.children:
                    queue.append(c_binding)

        copy_to_clipboard(content)

    def copy_hirc_entry_unfold(self):
        pass

    def copy_hirc_entry_fold(self):
        pass

    def check_modified(self):
        for hirc_view in self.hirc_view_list:
            data = hirc_view.data
            if isinstance(data, MusicSegment):
                hirc_view.modified = data.modified
                modified = hirc_view.modified
    
                curr_view = hirc_view
                parent_view_id = hirc_view.parent_vid
                while parent_view_id != None:
                    curr_view = self.hirc_view_list[parent_view_id]
                    curr_view.modified = modified
                    parent_view_id = curr_view.parent_vid
            elif isinstance(data, AudioSource):
                modified = data.modified
                if not modified:
                    track_info = data.get_track_info()
                    if track_info != None:
                        modified = track_info.modified
    
                hirc_view.modified = modified
    
                curr_view = hirc_view
                parent_view_id = hirc_view.parent_vid
                while parent_view_id != None:
                    curr_view = self.hirc_view_list[parent_view_id]
                    curr_view.modified = modified
                    parent_view_id = curr_view.parent_vid
            # TODO event modification and string modification


