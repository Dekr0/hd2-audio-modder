# Module import
import os
import posixpath
import sqlite3
import subprocess
from imgui_bundle import imgui, imgui_ctx

from backend import env
from backend.core import AudioSource
from fileutil import to_posix
from ui.bank_viewer.tree_selection_impl import apply_selection_reqs 
from ui.ui_flags import * 
from ui.ui_keys import *
from ui.app_state import AppState
from ui.bank_viewer.state import BankViewerTableHeader, BankViewerTableType
from ui.bank_viewer.state import BankViewerState, HircView

from log import logger


def gui_bank_viewer(
        app_state: AppState, bank_state: BankViewerState):
    """
    @exception
    - AssertionError
    """
    window_name = "Bank Viewer"
    file_reader = bank_state.file_handler.file_reader
    if file_reader.path != "":
        window_name = f"{posixpath.basename(file_reader.path)} ({file_reader.path})"

    view_port = imgui.get_main_viewport()
    imgui.set_next_window_viewport(view_port.id_)
    ok, is_open = imgui.begin(window_name, True, imgui.WindowFlags_.menu_bar.value)
    if not ok:
        imgui.end()
        return is_open

    gui_bank_viewer_menu(app_state, bank_state)
    gui_bank_viewer_table(app_state, bank_state)

    imgui.end()

    return is_open


def gui_bank_viewer_menu(app_state: AppState, bank_state: BankViewerState):
    if not imgui.begin_menu_bar():
        return

    gui_bank_viewer_load_menu(app_state, bank_state)
    gui_bank_viewer_automation_menu(app_state, bank_state)

    imgui.end_menu_bar()


def gui_bank_viewer_load_menu(app_state: AppState, bank_state: BankViewerState):
    if not imgui.begin_menu("Load"):
        return

    gui_bank_viewer_load_archive_menu(app_state, bank_state)

    imgui.end_menu()


def gui_bank_viewer_load_archive_menu(app_state: AppState, bank_state: BankViewerState):
    if not imgui.begin_menu("Archive"):
        return

    gui_bank_viewer_load_recent_archive_menu(app_state, bank_state)

    if imgui.menu_item_simple("From Helldivers 2 Data Folder"):
        if bank_state.file_picker_task != None:
            app_state.queue_warning_modal(
                "Please finish the current archive selection."
            )
        else:
            if os.path.exists(env.get_data_path()):

                def callback(file_path: str):
                    file_path = to_posix(file_path)
                    try:
                        app_state.load_archive_exist_viewer(bank_state, file_path)
                    except OSError as err:
                        logger.error(err)
                    except sqlite3.Error as err:
                        logger.error(err)
                    except AssertionError as err:
                        app_state.queue_critical_modal("Assertion Error", err)
                    except Exception as err:
                        app_state.queue_critical_modal("Unhandle exception", err)

                app_state.queue_file_picker_task(
                    "Select An Archive",
                    lambda paths: callback(paths[0]),
                    env.get_data_path(),
                    multi = False
                )
            else:
                app_state.queue_warning_modal(
                    "Incorrect Helldivers 2 data directory path.\n"
                    "Please set it in the \"Setting\""
                )

    if imgui.menu_item_simple("From File Explorer"):
        if bank_state.file_picker_task != None:
            app_state.queue_warning_modal(
                "Please finish the current archive selection."
            )
        else:
            def callback(file_path: str):
                file_path = to_posix(file_path)
                try:
                    app_state.load_archive_exist_viewer(bank_state, file_path)
                except OSError as err:
                    logger.error(err)
                except sqlite3.Error as err:
                    logger.error(err)
                except AssertionError as err:
                    app_state.queue_critical_modal("Assertion Error", err)
                except Exception as err:
                    app_state.queue_critical_modal("Unhandle exception", err)

            app_state.queue_file_picker_task(
                "Select An Archive",
                lambda paths: callback(paths[0]),
                multi = False
            )

    imgui.end_menu()


def gui_bank_viewer_automation_menu(app_state: AppState, bank_state: BankViewerState):
    if not imgui.begin_menu("Automation"):
        return

    gui_bank_viewer_target_import_menu(app_state, bank_state)

    imgui.end_menu()


def gui_bank_viewer_target_import_menu(app_state: AppState, bank_state: BankViewerState):
    if not imgui.begin_menu("Target Import"):
        return

    if imgui.menu_item_simple("Using Database Label"):
        pass
    if imgui.menu_item_simple("Using Database Tags", enabled=False):
        pass
    if imgui.menu_item_simple("Using Manifest", enabled=False):
        pass

    imgui.end_menu()


def gui_bank_viewer_load_recent_archive_menu(
        app_state: AppState, bank_state: BankViewerState):
    recent_files = app_state.setting.recent_files

    if len(recent_files) <= 0:
        imgui.menu_item_simple("From Recent", enabled=False)
        return

    if not imgui.begin_menu("From Recent"):
        return

    for recent_file in app_state.setting.recent_files:
        if imgui.menu_item_simple(recent_file):
            def callback():
                normalized = to_posix(recent_file)
                try:
                    app_state.load_archive_exist_viewer(bank_state, normalized)
                except OSError as err:
                    logger.error(err)
                except sqlite3.Error as err:
                    logger.error(err)

            app_state.queue_macro_task(callback)

            break

    imgui.end_menu()


def gui_bank_viewer_table(app_state: AppState, bank_state: BankViewerState):
    if len(bank_state.file_handler.get_wwise_banks()) == 0:
        return

    with imgui_ctx.push_id(bank_state.id):
        if imgui.button("\ue8fe") and not bank_state.src_view:
            bank_state.src_view = True
            bank_state.imgui_selection_store.clear()
        imgui.same_line()

        if imgui.button("\ue97a") and bank_state.src_view:
            bank_state.src_view = False
            bank_state.imgui_selection_store.clear()

        if app_state.is_db_enabled() and \
           not app_state.is_db_write_busy() and \
           not app_state.has_issue_db_write(bank_state): # Shouldn't happen
            imgui.same_line()
            if imgui.button("\ue161"):
                gui_on_save_button_click(app_state, bank_state)

        if not imgui.begin_table(WidgetKey.BANK_HIERARCHY_TABLE, 7, TABLE_FLAGS):
            return

        tree = bank_state.hirc_view_root

        linear_mapping = bank_state.hirc_view_list
        imgui_selection_store = bank_state.imgui_selection_store

        bank_hirc_views = tree.children

        # [Table Column Setup]
        imgui.table_setup_scroll_freeze(0, 1)
        imgui.table_setup_column(BankViewerTableHeader.FAV.value, 
                                 TABLE_COLUMN_FLAGS_FIXED)
        imgui.table_setup_column("", TABLE_COLUMN_FLAGS_FIXED)
        imgui.table_setup_column(BankViewerTableHeader.PLAY.value, 
                                 TABLE_COLUMN_FLAGS_FIXED)
        imgui.table_setup_column(BankViewerTableHeader.REV.value,
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


def gui_on_save_button_click(app_state: AppState, bank_state: BankViewerState):
    if app_state.is_db_write_busy():
        app_state.queue_warning_modal(
            "A database write operation is running.\n"
            "Please wait for it to finish."
        )
    else:
        def callback():
            try:
                app_state.write_hirc_obj_records(bank_state)
            except AssertionError as err:
                app_state.queue_critical_modal("Assertion Error", err)

        app_state.queue_macro_task(callback)


def gui_bank_viewer_table_row_source_view(
    app_state: AppState, bank_state: BankViewerState, hirc_view: HircView):
    selection: imgui.SelectionBasicStorage = bank_state.imgui_selection_store

    hvid = hirc_view.vid
    flags = TREE_NODE_FLAGS

    if hirc_view.hirc_obj_type == BankViewerTableType.SOUNDBANK:
        imgui.table_next_row()

        # [Column 0: Favorite]
        imgui.table_next_column()
        with imgui_ctx.push_id(f"c0_{hvid}"):
            imgui.align_text_to_frame_padding()
            imgui.button("\ue838")
        # [End]

        # [Column 1: Select]
        selected = selection.contains(hvid)
        if selected:
            flags |= imgui.TreeNodeFlags_.selected.value
        imgui.set_next_item_storage_id(hvid)
        imgui.set_next_item_selection_user_data(hvid)

        imgui.table_next_column()
        with imgui_ctx.push_id(f"c1_{hvid}"):
            imgui.checkbox("", selected)
        # [End]

        # [Column 2: Play]
        imgui.table_next_column()
        with imgui_ctx.push_id(f"c2_{hvid}"):
            imgui.text_disabled("--")
        # [End]

        # [Column 3: Rev]
        imgui.table_next_column()
        with imgui_ctx.push_id(f"c3_{hvid}"):
            if hirc_view.modified:
                imgui.align_text_to_frame_padding()
                if imgui.button("\ue889"):
                    logger.info("Undo")
            else:
                imgui.text_disabled("--")

        # [Column 4: Default Label]
        imgui.table_next_column()
        with imgui_ctx.push_id(f"c4_{hvid}"):
            expand = imgui.tree_node_ex(hirc_view.default_label, flags)
            gui_bank_table_item_ctx_menu(hirc_view, bank_state)
        # [End]

        # [Column 5: User Defined Label]
        imgui.table_next_column()
        with imgui_ctx.push_id(f"c5_{hvid}"):
            imgui.text(hirc_view.usr_defined_label)
        # [End]

        # [Column 6: Hirc. Type]
        imgui.table_next_column()
        with imgui_ctx.push_id(f"c6_{hvid}"):
            imgui.text(hirc_view.hirc_obj_type.value)
        # [End]

        if not expand:
            return

        for c_hirc_view in hirc_view.children:
            gui_bank_viewer_table_row_source_view(app_state, bank_state, c_hirc_view)

        imgui.tree_pop()

        return
    elif hirc_view.hirc_obj_type == BankViewerTableType.AUDIO_SOURCE or \
         hirc_view.hirc_obj_type == BankViewerTableType.AUDIO_SOURCE_MUSIC:
        imgui.table_next_row()

        # [Column 0: Favorite]
        imgui.table_next_column()
        with imgui_ctx.push_id(f"c0_{hvid}"):
            imgui.align_text_to_frame_padding()
            imgui.button("\ue838")
        # [End]

        # [Column 1: Select]
        selected = selection.contains(hvid)
        if selected:
            flags |= imgui.TreeNodeFlags_.selected.value
        imgui.set_next_item_storage_id(hvid)
        imgui.set_next_item_selection_user_data(hvid)

        imgui.table_next_column()
        with imgui_ctx.push_id(f"c1_{hvid}"):
            imgui.checkbox("", selected)
        # [End]

        # [Column 2: Play]
        imgui.table_next_column()
        if imgui.arrow_button(f"c2_{hvid}", imgui.Dir.right):
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

        # [Column 3: Rev]
        imgui.table_next_column()
        with imgui_ctx.push_id(f"c3_{hvid}"):
            if hirc_view.modified:
                imgui.align_text_to_frame_padding()
                if imgui.button("\ue889"):
                    logger.info("Undo")
            else:
                imgui.text_disabled("--")

        # [Column 4: Default Label]
        imgui.table_next_column()
        with imgui_ctx.push_id(f"c3_{hvid}"):
            flags |= imgui.TreeNodeFlags_.leaf.value
            expand = imgui.tree_node_ex(hirc_view.default_label, flags)
            gui_bank_table_item_ctx_menu(hirc_view, bank_state)
        # [End]

        # [Column 5: User Defined Label] I want to future proof this but I won't do it.
        imgui.table_next_column()
        imgui.push_item_width(-imgui.FLT_MIN)
        with imgui_ctx.push_id(f"c4_{hvid}"):
            if not app_state.is_db_enabled() or app_state.is_db_write_busy():
                imgui.text_disabled(hirc_view.usr_defined_label)
            else:
                changed, next = imgui.input_text("", hirc_view.usr_defined_label)
                if changed:
                   hirc_view.usr_defined_label = next
                   bank_state.mut_hirc_views[hirc_view.hirc_ul_ID] = hirc_view
        # [End]

        # [Column 6: Hirc. Type]
        imgui.table_next_column()
        with imgui_ctx.push_id(f"c6_{hvid}"):
            imgui.text(hirc_view.hirc_obj_type.value)
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

    hvid = hirc_view.vid
    flags = TREE_NODE_FLAGS

    imgui.table_next_row()

    # [Column 0: Favorite]
    imgui.table_next_column()
    with imgui_ctx.push_id(f"c0_{hvid}"):
        imgui.align_text_to_frame_padding()
        imgui.button("\ue838")
    # [End]

    # [Column 1: Select]
    selected = selection.contains(hvid)
    if selected:
        flags |= imgui.TreeNodeFlags_.selected.value
    imgui.set_next_item_storage_id(hvid)
    imgui.set_next_item_selection_user_data(hvid)

    imgui.table_next_column()
    with imgui_ctx.push_id(f"c1_{hvid}"):
        imgui.checkbox("", selected)
    # [End]

    # [Column 2: Play]
    imgui.table_next_column()
    if hirc_view.hirc_obj_type == BankViewerTableType.AUDIO_SOURCE or \
       hirc_view.hirc_obj_type == BankViewerTableType.AUDIO_SOURCE_MUSIC:
        if imgui.arrow_button(f"c2_{hvid}", imgui.Dir.right):
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

    # [Column 3: Rev]
    imgui.table_next_column()
    with imgui_ctx.push_id(f"c3_{hvid}"):
        if hirc_view.modified:
            imgui.align_text_to_frame_padding()
            if imgui.button("\ue889"):
                logger.info("Undo")
        else:
            imgui.text_disabled("--")

    # [Column 4: Default Label]
    imgui.table_next_column()
    with imgui_ctx.push_id(f"c3_{hvid}"):
        if len(hirc_view.children) <= 0:
            flags |= imgui.TreeNodeFlags_.leaf.value
        expand = imgui.tree_node_ex(hirc_view.default_label, flags)
        gui_bank_table_item_ctx_menu(hirc_view, bank_state)
    # [End]

    # [Column 5: User Defined Label] I want to future proof this but I won't do it.
    imgui.table_next_column()
    with imgui_ctx.push_id(f"c5_{hvid}"):
        if hirc_view.hirc_obj_type.value == BankViewerTableType.AUDIO_SOURCE or \
           hirc_view.hirc_obj_type.value == BankViewerTableType.RANDOM_SEQ_CNTR:

           imgui.push_item_width(-imgui.FLT_MIN)

           if not app_state.is_db_enabled() or app_state.is_db_write_busy():
               imgui.text_disabled(hirc_view.usr_defined_label)
           else:
               changed, next = imgui.input_text("", hirc_view.usr_defined_label)
               if changed:
                  hirc_view.usr_defined_label = next
                  bank_state.mut_hirc_views[hirc_view.hirc_ul_ID] = hirc_view
        else:
            imgui.text(hirc_view.usr_defined_label)
    # [End]

    # [Column 6: Hirc. Type]
    imgui.table_next_column()
    with imgui_ctx.push_id(f"c6_{hvid}"):
        imgui.text(hirc_view.hirc_obj_type.value)
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
                bank_state.copy_audio_entry(hirc_view, True)
            if imgui.menu_item_simple("Audio Source Only (ID only)"):
                bank_state.copy_audio_entry(hirc_view)
            if imgui.menu_item_simple("Tree Structure With Descendant", enabled=False):
                pass
            if imgui.menu_item_simple("Tree Structure With No Descendant", enabled=False):
                pass
            imgui.end_menu()
        imgui.end_menu()

    if imgui.begin_menu("Export", enabled=False):
        if imgui.begin_menu("As .wav", enabled=False):
            if imgui.begin_menu("With Sound", enabled=False):
                if imgui.menu_item_simple("Without Sequence Suffix", enabled=False):
                    pass
                if imgui.menu_item_simple("With Sequence Suffix", enabled=False):
                    pass
                imgui.end_menu()
            if imgui.begin_menu("Slient", enabled=False):
                if imgui.menu_item_simple("Without Sequence Suffix", enabled=False):
                    pass
                if imgui.menu_item_simple("With Sequence Suffix", enabled=False):
                    pass
                imgui.end_menu()
            imgui.end_menu()
        imgui.end_menu()

    imgui.end_popup()
