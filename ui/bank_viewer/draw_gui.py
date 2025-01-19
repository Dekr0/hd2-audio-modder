# Module import
import os
import posixpath
import subprocess
from imgui_bundle import imgui

from backend.core import AudioSource
from backend.env import get_data_path
from ui.bank_viewer.ctx_menu_ctrl import copy_audio_entry
from ui.bank_viewer.load_archive_ctrl import load_archive_exist_viewer_helper
from ui.bank_viewer.tree_selection_impl import apply_selection_reqs 
from ui.bank_viewer.view_ctrl import write_hirc_obj_view_change_helper
from ui.ui_flags import * 
from ui.ui_keys import *
from ui.view_data import BankViewerTableHeader, BankViewerTableType
from ui.view_data import AppState, BankViewerState, MsgModalState, HircView

from log import logger


def gui_bank_viewer(
        app_state: AppState, bank_state: BankViewerState):
    """
    @exception
    - AssertionError
    """
    archive_picker = bank_state.archive_picker

    window_name = "Bank Viewer"
    file_reader = bank_state.file_handler.file_reader
    if file_reader.path != "":
        window_name = f"{posixpath.basename(file_reader.path)} ({file_reader.path})"

    ok, is_open = imgui.begin(window_name, True, imgui.WindowFlags_.menu_bar.value)
    if not is_open and archive_picker.is_schedule():
        app_state.warning_modals.append(MsgModalState(
            "Please close the active file picker first"))
        is_open = True

    if not ok:
        imgui.end()
        
        return is_open

    gui_bank_viewer_menu(app_state, bank_state)

    gui_bank_viewer_table(app_state, bank_state)

    if archive_picker.is_ready():
        result = archive_picker.get_result()

        if len(result) > 0:
            callback = lambda: load_archive_exist_viewer_helper(app_state, 
                                                                bank_state, 
                                                                result[0])
            app_state.io_task_queue.append(callback)

        archive_picker.reset()

    imgui.end()

    return is_open


def gui_bank_viewer_menu(app_state: AppState, bank_state: BankViewerState):
    if not imgui.begin_menu_bar():
        return

    gui_bank_viewer_load_menu(app_state, bank_state)

    imgui.end_menu_bar()


def gui_bank_viewer_load_menu(app_state: AppState, bank_state: BankViewerState):
    if not imgui.begin_menu("Load"):
        return

    gui_bank_viewer_load_archive_menu(app_state, bank_state)
    gui_bank_viewer_load_patch_menu(app_state, bank_state)

    imgui.end_menu()


def gui_bank_viewer_load_archive_menu(app_state: AppState, bank_state: BankViewerState):
    if not imgui.begin_menu("Archive"):
        return

    archive_picker = bank_state.archive_picker

    gui_bank_viewer_load_recent_archive_menu(app_state, bank_state)

    if imgui.menu_item_simple("From Helldivers 2 Data Folder"):
        if os.path.exists(get_data_path()):
            try:
                archive_picker.schedule("Select An Archive", get_data_path())
            except AssertionError:
                app_state.warning_modals.append(
                    MsgModalState("Please finish the current archive selection.")
                )
        else:
            app_state.warning_modals.append(MsgModalState(
                f"The directory path for Helldivers 2 data folder in the setting "
                " is not correct. Please set the correct path in the Setting."
            ))

    if imgui.menu_item_simple("From File Explorer"):
        try:
            archive_picker.schedule("Select An Archive")
        except AssertionError:
            app_state.warning_modals.append(
                MsgModalState("Please finish the current archive selection.")
            )

    imgui.end_menu()


def gui_bank_viewer_load_recent_archive_menu(app_state: AppState, bank_state: BankViewerState):
    recent_files = app_state.setting.recent_files

    if len(recent_files) <= 0:
        imgui.menu_item_simple("From Recent", enabled=False)
        return

    if not imgui.begin_menu("From Recent"):
        return

    for recent_file in app_state.setting.recent_files:
        if imgui.menu_item_simple(recent_file):
            callback = lambda: load_archive_exist_viewer_helper(app_state, 
                                                                bank_state, 
                                                                recent_file)
            app_state.io_task_queue.append(callback)

            break

    imgui.end_menu()


def gui_bank_viewer_load_patch_menu(app_state: AppState, bank_state: BankViewerState):
    if not imgui.begin_menu("Load"):
        return

    if imgui.begin_menu("Patch"):
        if imgui.menu_item_simple("Load"):
            pass
        if imgui.begin_menu("Write"):
            if imgui.menu_item_simple("Without Manifest"):
                pass
            if imgui.menu_item_simple("With Manifest"):
                pass
            imgui.end_menu()
        imgui.end_menu()
    imgui.end_menu()


def gui_bank_viewer_table(app_state: AppState, bank_state: BankViewerState):
    if len(bank_state.file_handler.get_wwise_banks()) == 0:
        return

    bsid = bank_state.id
    imgui.push_id(bsid + "source_view")
    if imgui.button("\ue8fe") and not bank_state.src_view:
        bank_state.src_view = True
        bank_state.imgui_selection_store.clear()
    imgui.pop_id()

    imgui.same_line()

    imgui.push_id(bsid + "hirc_view")
    if imgui.button("\ue97a") and bank_state.src_view:
        bank_state.src_view = False
        bank_state.imgui_selection_store.clear()
    imgui.pop_id()

    imgui.same_line()

    imgui.push_id(bsid + "save_label")
    if imgui.button("\ue161"):
        callback = lambda: write_hirc_obj_view_change_helper(app_state, 
                                                             bank_state)
        app_state.io_task_queue.append(callback)
    imgui.pop_id()

    if not imgui.begin_table(WidgetKey.BANK_HIERARCHY_TABLE, 6, TABLE_FLAGS):

        return

    tree = bank_state.hirc_view_root

    linear_mapping = bank_state.hirc_views_linear
    imgui_selection_store = bank_state.imgui_selection_store

    bank_hirc_views = tree.children

    # [Table Column Setup]
    imgui.table_setup_scroll_freeze(0, 1)
    imgui.table_setup_column(BankViewerTableHeader.FAV.value, 
                             TABLE_COLUMN_FLAGS_FIXED)
    imgui.table_setup_column("", TABLE_COLUMN_FLAGS_FIXED)
    imgui.table_setup_column(BankViewerTableHeader.PLAY.value, 
                             TABLE_COLUMN_FLAGS_FIXED)
    imgui.table_setup_column(BankViewerTableHeader.DEFAULT_LABEL.value, 
                             TABLE_COLUMN_FLAGS_INDENT)
    imgui.table_setup_column(BankViewerTableHeader.USER_DEFINED_LABEL)
    imgui.table_setup_column(BankViewerTableHeader.HIRC_ENTRY_TYPE)
    imgui.table_headers_row()
    # [End]

    ms_io = imgui.begin_multi_select(MULTI_SELECT_FLAGS, imgui_selection_store.size, len(linear_mapping))
    apply_selection_reqs(ms_io, bank_state)

    if bank_state.src_view:
        for bank_hirc_view in bank_hirc_views:
            gui_bank_viewer_table_row_source_view(app_state, bank_state, bank_hirc_view)
    else:
        for bank_hirc_view in bank_hirc_views:
            gui_bank_viewer_table_row_hirc_view(app_state, bank_state, bank_hirc_view)

    ms_io = imgui.end_multi_select()
    apply_selection_reqs(ms_io, bank_state)

    imgui.end_table()


def gui_bank_viewer_table_row_source_view(
    app_state: AppState, bank_state: BankViewerState, hirc_view: HircView):
    selection: imgui.SelectionBasicStorage = bank_state.imgui_selection_store

    bsid = bank_state.id
    hvid = hirc_view.view_id
    flags = TREE_NODE_FLAGS

    if hirc_view.hirc_entry_type == BankViewerTableType.SOUNDBANK:
        imgui.table_next_row()

        # [Column 0: Favorite]
        imgui.table_next_column()
        imgui.push_id(f"{bsid}_favorite_{hvid}")
        imgui.button("\ue838")
        imgui.pop_id()
        # [End]

        # [Column 1: Select]
        selected = selection.contains(hvid)
        if selected:
            flags |= imgui.TreeNodeFlags_.selected.value
        imgui.set_next_item_storage_id(hvid)
        imgui.set_next_item_selection_user_data(hvid)

        imgui.table_next_column()
        imgui.push_id(f"{bsid}_select_{hvid}")
        imgui.checkbox("", selected)
        imgui.pop_id()
        # [End]

        # [Column 2: Play]
        imgui.table_next_column()
        imgui.text_disabled("--")
        # [End]

        # [Column 3: Default Label]
        imgui.table_next_column()
        imgui.push_id(f"{bsid}_default_label_{hvid}")
        expand = imgui.tree_node_ex(hirc_view.default_label, flags)
        gui_bank_table_item_ctx_menu(hirc_view, bank_state)
        imgui.pop_id()
        # [End]

        # [Column 4: User Defined Label]
        imgui.table_next_column()
        imgui.text(hirc_view.user_defined_label)
        # [End]

        # [Column 5: Hirc. Type]
        imgui.table_next_column()
        imgui.text(hirc_view.hirc_entry_type.value)
        # [End]

        if not expand:
            return

        for c_hirc_view in hirc_view.children:
            gui_bank_viewer_table_row_source_view(app_state, bank_state, c_hirc_view)

        imgui.tree_pop()

        return
    elif hirc_view.hirc_entry_type == BankViewerTableType.AUDIO_SOURCE or \
         hirc_view.hirc_entry_type == BankViewerTableType.AUDIO_SOURCE_MUSIC:
        imgui.table_next_row()

        # [Column 0: Favorite]
        imgui.table_next_column()
        imgui.push_id(f"{bsid}_favorite_{hvid}")
        imgui.button("\ue838")
        imgui.pop_id()
        # [End]

        # [Column 1: Select]
        selected = selection.contains(hvid)
        if selected:
            flags |= imgui.TreeNodeFlags_.selected.value
        imgui.set_next_item_storage_id(hvid)
        imgui.set_next_item_selection_user_data(hvid)

        imgui.table_next_column()
        imgui.push_id(f"{bsid}_select_{hvid}")
        imgui.checkbox("", selected)
        imgui.pop_id()
        # [End]

        # [Column 2: Play]
        imgui.table_next_column()
        if imgui.arrow_button(f"{bsid}_play_{hvid}", imgui.Dir.right):
            audio = hirc_view.data
            if not isinstance(audio, AudioSource):
                raise AssertionError("Entry is marked as type audio source but "
                                     "binding data is not an instance of Audio "
                                     f"Source ({type(audio)}).")
            try:
                bank_state \
                        .sound_handler \
                        .play_audio(audio.get_short_id(), audio.get_data())
            except (subprocess.CalledProcessError) as err:
                logger.error(f"Failed to play audio. Reason: {err}")
                # Or show modal
            except NotImplementedError as err:
                logger.error(err)
                # Or show modal
            except OSError as err:
                logger.error(err)
                # Or show modal
        # [End]

        # [Column 3: Default Label]
        imgui.table_next_column()
        imgui.push_id(f"{bsid}_default_label_{hvid}")
        flags |= imgui.TreeNodeFlags_.leaf.value
        expand = imgui.tree_node_ex(hirc_view.default_label, flags)
        gui_bank_table_item_ctx_menu(hirc_view, bank_state)
        imgui.pop_id()
        # [End]

        # [Column 4: User Defined Label] I want to future proof this but I won't do it.
        imgui.table_next_column()
        imgui.push_item_width(-imgui.FLT_MIN)
        imgui.push_id(f"{bsid}_user_defined_label_{hvid}")
        changed, next = imgui.input_text(
            "", 
            hirc_view.user_defined_label,
        )
        if changed:
           hirc_view.user_defined_label = next
           bank_state.changed_hirc_views[hirc_view.hirc_ul_ID] = hirc_view
        imgui.pop_id()
        # [End]

        # [Column 5: Hirc. Type]
        imgui.table_next_column()
        imgui.text(hirc_view.hirc_entry_type.value)
        # [End]

        if not expand:
            return

        imgui.tree_pop()
    else:
        for c_hirc_view in hirc_view.children:
            gui_bank_viewer_table_row_source_view(app_state, bank_state, c_hirc_view)


def gui_bank_viewer_table_row_hirc_view(
        app_state: AppState, bank_state: BankViewerState, hirc_view: HircView):
    selection: imgui.SelectionBasicStorage = bank_state.imgui_selection_store

    bsid = bank_state.id
    hvid = hirc_view.view_id
    flags = TREE_NODE_FLAGS

    imgui.table_next_row()

    # [Column 0: Favorite]
    imgui.table_next_column()
    imgui.push_id(f"{bsid}_favorite_{hvid}")
    imgui.button("\ue838")
    imgui.pop_id()
    # [End]

    # [Column 1: Select]
    selected = selection.contains(hvid)
    if selected:
        flags |= imgui.TreeNodeFlags_.selected.value
    imgui.set_next_item_storage_id(hvid)
    imgui.set_next_item_selection_user_data(hvid)

    imgui.table_next_column()
    imgui.push_id(f"{bsid}_select_{hvid}")
    imgui.checkbox("", selected)
    imgui.pop_id()
    # [End]

    # [Column 2: Play]
    imgui.table_next_column()
    if hirc_view.hirc_entry_type == BankViewerTableType.AUDIO_SOURCE or \
       hirc_view.hirc_entry_type == BankViewerTableType.AUDIO_SOURCE_MUSIC:
        if imgui.arrow_button(f"{bsid}_play_{hvid}", imgui.Dir.right):
            audio = hirc_view.data
            if not isinstance(audio, AudioSource):
                raise AssertionError("Entry is marked as type audio source but "
                                     "binding data is not an instance of Audio "
                                     f"Source ({type(audio)}).")
            try:
                bank_state \
                        .sound_handler \
                        .play_audio(audio.get_short_id(), audio.get_data())
            except (subprocess.CalledProcessError) as err:
                logger.error(f"Failed to play audio. Reason: {err}")
                # Or show modal
            except NotImplementedError as err:
                logger.error(err)
                # Or show modal
            except OSError as err:
                logger.error(err)
                # Or show modal
    else:
        imgui.text_disabled("--")
    # [End]

    # [Column 3: Default Label]
    imgui.table_next_column()
    imgui.push_id(f"{bsid}_default_label_{hvid}")
    if len(hirc_view.children) <= 0:
        flags |= imgui.TreeNodeFlags_.leaf.value
    expand = imgui.tree_node_ex(hirc_view.default_label, flags)
    gui_bank_table_item_ctx_menu(hirc_view, bank_state)
    imgui.pop_id()
    # [End]

    # [Column 4: User Defined Label] I want to future proof this but I won't do it.
    imgui.table_next_column()
    if hirc_view.hirc_entry_type.value == BankViewerTableType.AUDIO_SOURCE or \
       hirc_view.hirc_entry_type.value == BankViewerTableType.RANDOM_SEQ_CNTR:
       imgui.push_item_width(-imgui.FLT_MIN)
       imgui.push_id(f"{bsid}_user_defined_label_{hvid}")
       changed, next = imgui.input_text("", hirc_view.user_defined_label)
       if changed:
           hirc_view.user_defined_label = next
           bank_state.changed_hirc_views[hirc_view.hirc_ul_ID] = hirc_view
       imgui.pop_id()
    else:
        imgui.text(hirc_view.user_defined_label)
    # [End]

    # [Column 5: Hirc. Type]
    imgui.table_next_column()
    imgui.text(hirc_view.hirc_entry_type.value)
    # [End]

    if not expand:
        return

    for c_hirc_view in hirc_view.children:
        gui_bank_viewer_table_row_hirc_view(app_state, bank_state, c_hirc_view)

    imgui.tree_pop()


def gui_bank_table_item_ctx_menu(
        hirc_view: HircView, bank_state: BankViewerState):
    if not imgui.begin_popup_context_item():
        return
    
    if imgui.begin_menu("Copy"):
        if imgui.menu_item_simple("As .CSV"):
            pass
        if imgui.begin_menu("As Plain Text"):
            if imgui.menu_item_simple("Audio Source Only"):
                copy_audio_entry(hirc_view, bank_state, True)
            if imgui.menu_item_simple("Audio Source Only (ID only)"):
                copy_audio_entry(hirc_view, bank_state)
            if imgui.menu_item_simple("Tree Structure With Descendant"):
                pass
            if imgui.menu_item_simple("Tree Structure With No Descendant"):
                pass
            imgui.end_menu()
        imgui.end_menu()

    if imgui.begin_menu("Export"):
        if imgui.begin_menu("As .wav"):
            if imgui.begin_menu("With Sound"):
                if imgui.menu_item_simple("Without Sequence Suffix"):
                    pass
                if imgui.menu_item_simple("With Sequence Suffix"):
                    pass
                imgui.end_menu()
            if imgui.begin_menu("Slient"):
                if imgui.menu_item_simple("Without Sequence Suffix"):
                    pass
                if imgui.menu_item_simple("With Sequence Suffix"):
                    pass
                imgui.end_menu()
            imgui.end_menu()
        imgui.end_menu()

    imgui.end_popup()
