import sqlite3

import backend.db.db_schema_map as orm

from backend.core import MusicSegment, RandomSequenceContainer, Sound
from backend.const import VORBIS

from ui.view_data import BankViewerTableType
from ui.view_data import AppState, BankViewerState, HierarchyView, MessageModalState


"""
Below seems to be controller / agent that mitgate between the frontend and backend
"""
def create_bank_hierarchy_view(app_state: AppState, bank_state: BankViewerState):
    root = bank_state.hirc_view_root
    bank_hirc_views = root.children
    bank_hirc_views_linear = bank_state.hirc_views_linear
    hierarchy_views_all = app_state.hierarchy_views_all

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
        bank_name = bank.get_name().replace("/", "_") \
                                   .replace("\x00", "")

        bank_view = HierarchyView(
                None,
                idx, root.view_id,
                bank.get_id(), -1, bank_name,
                BankViewerTableType.SOUNDBANK, 
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

                segment_label = ""
                if segment_id in hierarchy_views_all:
                    segment_label = hierarchy_views_all[segment_id].label

                segment_view = HierarchyView(
                        hirc_entry,
                        idx, bank_idx,
                        segment_id, -1,
                        f"Segment {segment_id}",
                        BankViewerTableType.MUSIC_SEGMENT,
                        segment_label, [])
                children.append(segment_view)
                bank_hirc_views_linear.append(segment_view)
                idx += 1

                segment_view_id = segment_view.view_id

                for track_id in hirc_entry.tracks:
                    track = hirc_entries[track_id]

                    track_label = ""
                    if track_id in hierarchy_views_all:
                        track_label = hierarchy_views_all[track_id].label

                    track_view = HierarchyView(
                            track,
                            idx, segment_view_id, 
                            track_id, -1,
                            f"Track {track_id}", 
                            BankViewerTableType.MUSIC_TRACK, 
                            track_label, [])
                    segment_view.children.append(track_view)
                    bank_hirc_views_linear.append(track_view)
                    idx += 1 

                    track_view_id = track_view.view_id
                    for source_struct in track.sources:
                        if source_struct.plugin_id != VORBIS:
                            continue

                        source_id = source_struct.source_id
                        audio_source = file_handler.get_audio_by_id(source_id)
                        if audio_source == None:
                            # Logging?
                            continue

                        source_view = HierarchyView(
                                audio_source,
                                idx, track_view_id,
                                track_id, source_id,
                                f"{source_id}.wem",
                                BankViewerTableType.AUDIO_SOURCE_MUSIC,
                                "", [])
                        track_view.children.append(source_view)
                        bank_hirc_views_linear.append(source_view)
                        idx += 1 

                    for info in track.track_info:
                        if info.event_id == 0:
                            # Logging?
                            continue

                        info_id = info.get_id()

                        info_label = ""
                        if info_id in hierarchy_views_all:
                            info_label = hierarchy_views_all[info_id].label

                        info_view = HierarchyView(
                                info,
                                idx, track_view_id,
                                info_id, -1, 
                                f"Event {info_id}", 
                                BankViewerTableType.EVENT, 
                                info_label, [])
                        track_view.children.append(info_view)
                        bank_hirc_views_linear.append(info_view)
                        idx += 1

            elif isinstance(hirc_entry, RandomSequenceContainer):
                cntr_id = hirc_entry.get_id()

                cntr_label = ""
                if cntr_id in hierarchy_views_all:
                    cntr_label = hierarchy_views_all[cntr_id].label

                cntr_view = HierarchyView(
                        hirc_entry,
                        idx, bank_idx,
                        cntr_id, -1,
                        f"Random / Sequence Container {cntr_id}",
                        BankViewerTableType.RANDOM_SEQ_CNTR,
                        cntr_label, [])
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

                    sound_label = ""
                    if entry_id in hierarchy_views_all:
                        sound_label = hierarchy_views_all[entry_id].label

                    source_view = HierarchyView(
                            audio_source,
                            idx, cntr_view_id,
                            entry.hierarchy_id, source_id,
                            f"{source_id}.wem",
                            BankViewerTableType.AUDIO_SOURCE,
                            sound_label, [])
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

            sound_label = ""
            if hirc_entry.hierarchy_id in hierarchy_views_all:
                sound_label = hierarchy_views_all[hirc_entry.hierarchy_id].label

            source_view = HierarchyView(
                    audio_source,
                    idx, bank_idx,
                    hirc_entry.hierarchy_id, source_id, 
                    f"{source_id}.wem",
                    BankViewerTableType.AUDIO_SOURCE,
                    sound_label, [])

            children.append(source_view)
            bank_hirc_views_linear.append(source_view)
            idx += 1


def fetch_bank_hierarchy_object_view(app_state: AppState, bank_viewer_state: BankViewerState):
    """
    @exception
    - AssertionError
    - sqlite3.*Error
    """
    file_handler = bank_viewer_state.file_handler
    banks = file_handler.get_wwise_banks()
    hierarchy_views_all = app_state.hierarchy_views_all

    db = app_state.db
    if db == None:
        return

    for bank in banks.values():
        if bank.hierarchy == None:
            continue

        bank_name = bank.get_name().replace("/", "_").replace("\x00", "")
        hierarchy_object_views: list[orm.HierarchyObjectView] = \
            db.get_hierarchy_objects_by_soundbank(bank_name, False)

        for hierarchy_object_view in hierarchy_object_views:
            wwise_object_id = hierarchy_object_view.wwise_object_id
            if wwise_object_id in hierarchy_views_all:
                continue
            hierarchy_views_all[wwise_object_id] = hierarchy_object_view


def save_hierarchy_object_views_change(
    app_state: AppState, bank_state: BankViewerState):

    db = app_state.db
    if db == None:
        app_state.warning_modals.append(MessageModalState(
            "Trying to save changes when database access is disabled.")
        )
        return

    changed_hierarchy_views = bank_state.changed_hierarchy_views
    pending_hierarchy_view_changes: dict[int, str] = {}
    for changed_hierarchy_view in changed_hierarchy_views.values():
        hirc_ul_ID = changed_hierarchy_view.hirc_ul_ID
        user_defined_label = changed_hierarchy_view.user_defined_label
        if hirc_ul_ID in pending_hierarchy_view_changes:
            if app_state.critical_modal == None:
                app_state.critical_modal = MessageModalState(
                    "A hierarchy view queue up more than one change.")
        pending_hierarchy_view_changes[hirc_ul_ID] = user_defined_label

    try:
        db.update_hierarchy_object_labels_by_hierarchy_ids(
            [(label, str(hirc_ul_ID)) 
             for hirc_ul_ID, label in pending_hierarchy_view_changes.items()],
            True,
        )
        changed_hierarchy_views.clear()

        # Sync back to cached 
        hierarchy_views_all = app_state.hierarchy_views_all
        for hirc_ul_ID, label in pending_hierarchy_view_changes.items():
            if hirc_ul_ID not in hierarchy_views_all:
                raise AssertionError("Hierarchy object record with wwise object id "
                            f"{hirc_ul_ID} is not cached from the database.")
            hierarchy_views_all[hirc_ul_ID].label = label

        bank_states = app_state.bank_states
        for unsynced_bank_state in bank_states.values():
            if unsynced_bank_state.id == bank_state.id:
                continue
            create_bank_hierarchy_view(app_state, unsynced_bank_state)
    except sqlite3.Error as err:
        app_state.warning_modals.append(MessageModalState(
            f"Failed to save changes to database. Reason: {err}")
        )
    except Exception as err:
        if app_state.critical_modal == None:
            app_state.critical_modal = MessageModalState(
                    "Unhandle exception when saving changes to database: {err}")
