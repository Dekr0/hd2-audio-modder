# Module import
import os
import sqlite3
import subprocess
from imgui_bundle import imgui

from backend.core import AudioSource
from backend.env import get_data_path
from ui.ui_bank_explorer_controller import *
from ui.ui_bank_explorer_callback import *
from ui.ui_bank_explorer_tree_node_selection import apply_selection_reqs
from ui.ui_flags import * 
from ui.ui_keys import *
from ui.view_data import BankExplorerTableHeader
from ui.view_data import AppState, BankViewerState, MessageModalState

from log import logger


def gui_bank_explorer(app_state: AppState, bank_state: BankViewerState):
    file_handler = bank_state.file_handler
    title = "Bank Explorer"
    if hasattr(file_handler.file_reader, "name"):
        title += f" ({file_handler.file_reader.name})"

    ok, p_open = imgui.begin(title, True, imgui.WindowFlags_.menu_bar.value)
    if not ok:
        imgui.end()
        return p_open

    gui_bank_explorer_menu(app_state, bank_state)

    archive_picker = bank_state.archive_picker
    file_handler = bank_state.file_handler

    gui_bank_explorer_table(app_state, bank_state)

    if archive_picker.is_ready():
        result = archive_picker.get_result()

        if len(result) == 1:
            try:
                file_handler.load_archive_file(result[0])
                fetch_bank_hierarchy_object_view(app_state, bank_state)
                # create_bank_source_view(bank_state)
                create_bank_hierarchy_view(bank_state)
            except OSError as e:
                # show modal or display on the logger
                logger.error(e)
            except sqlite3.Error as e:
                # show modal or display on the logger
                logger.error(e)
            except Exception as e:
                # show modal or display on the logger
                logger.error(e)

        archive_picker.reset()

    imgui.end()

    return p_open


def gui_bank_explorer_menu(app_state: AppState, bank_state: BankViewerState):
    if not imgui.begin_menu_bar():
        return

    # gui_bank_explorer_view_menu(app_state, bank_state)
    gui_bank_explorer_load_menu(app_state, bank_state)

    imgui.end_menu_bar()


def gui_bank_explorer_load_menu(app_state: AppState, bank_state: BankViewerState):
    if not imgui.begin_menu("Load"):
        return

    gui_bank_explorer_load_archive_menu(app_state, bank_state)
    gui_bank_explorer_load_patch_menu(app_state, bank_state)

    imgui.end_menu()


def gui_bank_explorer_load_archive_menu(app_state: AppState, bank_state: BankViewerState):
    if not imgui.begin_menu("Archive"):
        return

    archive_picker = bank_state.archive_picker

    if imgui.menu_item_simple("From Helldivers 2 Data Folder"):
        if os.path.exists(get_data_path()):
            try:
                archive_picker.schedule("Select An Archive", get_data_path())
            except AssertionError:
                app_state.warning_modals.append(
                    MessageModalState("Please finish the current archive selection.")
                )
        else:
            app_state.warning_modals.append(MessageModalState(
                f"The directory path for Helldivers 2 data folder in the setting "
                " is not correct. Please set the correct path in the Setting."
            ))

    if imgui.menu_item_simple("From File Explorer"):
        try:
            archive_picker.schedule("Select An Archive")
        except AssertionError:
            app_state.warning_modals.append(
                MessageModalState("Please finish the current archive selection.")
            )

    imgui.end_menu()


def gui_bank_explorer_load_patch_menu(app_state: AppState, bank_state: BankViewerState):
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


def gui_bank_explorer_table(app_state: AppState, bank_viewer_state: BankViewerState):
    if len(bank_viewer_state.file_handler.get_wwise_banks()) == 0:
        return

    bsid = bank_viewer_state.id
    imgui.push_id(bsid + "source_view")
    if imgui.button("\ue8fe") and not bank_viewer_state.source_view:
        bank_viewer_state.source_view = True
        bank_viewer_state.imgui_selection_store.clear()
    imgui.pop_id()

    imgui.same_line()

    imgui.push_id(bsid + "hirc_view")
    if imgui.button("\ue97a") and bank_viewer_state.source_view:
        bank_viewer_state.source_view = False
        bank_viewer_state.imgui_selection_store.clear()
    imgui.pop_id()

    imgui.same_line()

    imgui.push_id(bsid + "save_label")
    if imgui.button("\ue161"):
        try:
            save_hierarchy_object_views_change(app_state, bank_viewer_state)
        except NotImplementedError as err:
            app_state.warning_modals.append(MessageModalState(str(err)))
        except sqlite3.Error as err:
            app_state.warning_modals.append(MessageModalState(
                f"Failed to save labels change. Reason: {err}."
            ))
        except AssertionError as err:
            if app_state.critical_modal == None:
                app_state.critical_modal = MessageModalState(str(err))
        except Exception as err:
            if app_state.critical_modal == None:
                app_state.critical_modal = MessageModalState(str(err))
    imgui.pop_id()

    if not imgui.begin_table(WidgetKey.BANK_HIERARCHY_TABLE, 6, TABLE_FLAGS):
        return

    tree = bank_viewer_state.hirc_view_root

    linear_mapping = bank_viewer_state.hirc_views_linear
    imgui_selection_store = bank_viewer_state.imgui_selection_store

    bank_hirc_views = tree.children

    # [Table Column Setup]
    imgui.table_setup_scroll_freeze(0, 1)
    imgui.table_setup_column(BankExplorerTableHeader.FAV.value, 
                             TABLE_COLUMN_FLAGS_FIXED)
    imgui.table_setup_column("", TABLE_COLUMN_FLAGS_FIXED)
    imgui.table_setup_column(BankExplorerTableHeader.PLAY.value, 
                             TABLE_COLUMN_FLAGS_FIXED)
    imgui.table_setup_column(BankExplorerTableHeader.DEFAULT_LABEL.value, 
                             TABLE_COLUMN_FLAGS_INDENT)
    imgui.table_setup_column(BankExplorerTableHeader.USER_DEFINED_LABEL)
    imgui.table_setup_column(BankExplorerTableHeader.HIRC_ENTRY_TYPE)
    imgui.table_headers_row()
    # [End]

    ms_io = imgui.begin_multi_select(MULTI_SELECT_FLAGS, imgui_selection_store.size, len(linear_mapping))
    apply_selection_reqs(ms_io, bank_viewer_state)

    if bank_viewer_state.source_view:
        for bank_hirc_view in bank_hirc_views:
            gui_bank_explorer_table_row_source_view(app_state, bank_viewer_state, bank_hirc_view)
    else:
        for bank_hirc_view in bank_hirc_views:
            gui_bank_explorer_table_row_hirc_view(app_state, bank_viewer_state, bank_hirc_view)

    ms_io = imgui.end_multi_select()
    apply_selection_reqs(ms_io, bank_viewer_state)

    imgui.end_table()


def gui_bank_explorer_table_row_source_view(
    app_state: AppState,
    bank_viewer_state: BankViewerState,
    hirc_view: HierarchyView,
):
    selection: imgui.SelectionBasicStorage = bank_viewer_state.imgui_selection_store

    bsid = bank_viewer_state.id
    hvid = hirc_view.view_id
    flags = TREE_NODE_FLAGS

    if hirc_view.hirc_entry_type == BankExplorerTableType.SOUNDBANK:
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
        gui_bank_table_item_ctx_menu(hirc_view, bank_viewer_state)
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
            gui_bank_explorer_table_row_source_view(app_state, bank_viewer_state, c_hirc_view)

        imgui.tree_pop()

        return
    elif hirc_view.hirc_entry_type == BankExplorerTableType.AUDIO_SOURCE:
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
                bank_viewer_state \
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
        gui_bank_table_item_ctx_menu(hirc_view, bank_viewer_state)
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
           bank_viewer_state.changed_hierarchy_views[hirc_view.hirc_ul_ID] = hirc_view
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
            gui_bank_explorer_table_row_source_view(app_state, bank_viewer_state, c_hirc_view)


def gui_bank_explorer_table_row_hirc_view(
        app_state: AppState,
        bank_viewer_state: BankViewerState,
        hirc_view: HierarchyView):
    selection: imgui.SelectionBasicStorage = bank_viewer_state.imgui_selection_store

    bsid = bank_viewer_state.id
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
    if hirc_view.hirc_entry_type == BankExplorerTableType.AUDIO_SOURCE or \
       hirc_view.hirc_entry_type == BankExplorerTableType.AUDIO_SOURCE_MUSIC:
        if imgui.arrow_button(f"{bsid}_play_{hvid}", imgui.Dir.right):
            audio = hirc_view.data
            if not isinstance(audio, AudioSource):
                raise AssertionError("Entry is marked as type audio source but "
                                     "binding data is not an instance of Audio "
                                     f"Source ({type(audio)}).")
            try:
                bank_viewer_state \
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
    gui_bank_table_item_ctx_menu(hirc_view, bank_viewer_state)
    imgui.pop_id()
    # [End]

    # [Column 4: User Defined Label] I want to future proof this but I won't do it.
    imgui.table_next_column()
    if hirc_view.hirc_entry_type.value == BankExplorerTableType.AUDIO_SOURCE or \
       hirc_view.hirc_entry_type.value == BankExplorerTableType.RANDOM_SEQ_CNTR:
       imgui.push_item_width(-imgui.FLT_MIN)
       imgui.push_id(f"{bsid}_user_defined_label_{hvid}")
       changed, next = imgui.input_text("", hirc_view.user_defined_label)
       if changed:
           hirc_view.user_defined_label = next
           bank_viewer_state.changed_hierarchy_views[hirc_view.hirc_ul_ID] = hirc_view
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
        gui_bank_explorer_table_row_hirc_view(app_state, bank_viewer_state, c_hirc_view)

    imgui.tree_pop()


def gui_bank_table_item_ctx_menu(hirc_view: HierarchyView, 
                                 bank_viewer_state: BankViewerState):
    if not imgui.begin_popup_context_item():
        return
    
    if imgui.begin_menu("Copy"):
        if imgui.menu_item_simple("As .CSV"):
            pass
        if imgui.begin_menu("As Plain Text"):
            if imgui.menu_item_simple("Audio Source Only"):
                copy_audio_entry(hirc_view, bank_viewer_state, True)
            if imgui.menu_item_simple("Audio Source Only (ID only)"):
                copy_audio_entry(hirc_view, bank_viewer_state)
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


