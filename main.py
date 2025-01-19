import gc
import os
import pickle
import sqlite3
import shutil

import setting
import backend.env as env

# Module import
from imgui_bundle import hello_imgui, imgui

from backend.db.db_access import config_sqlite_conn, SQLiteDatabase
from log import logger, std_formatter
from ui.bank_viewer.load_archive_ctrl import kill_bank_state, \
        load_archive_new_viewer_helper
from ui.bank_viewer.draw_gui import gui_bank_viewer
from ui.bank_viewer.view_ctrl import write_hirc_obj_record_changes
from ui.view_data import AppState, ConfirmModalState, CriticalModalState, MsgModalState
from ui.view_data import new_app_state

NTHREAD = 8


def main():
    hello_imgui.set_assets_folder(".")

    app_state = new_app_state() 

    app_state.gui_log_handler.setFormatter(std_formatter)
    logger.addHandler(app_state.gui_log_handler)

    runner_params = hello_imgui.RunnerParams()
    runner_params.app_window_params.window_title = "Shovel"
    runner_params.app_window_params.window_geometry.size = (1280, 720)
    runner_params.app_window_params.restore_previous_geometry = True
    runner_params.app_window_params.borderless = True
    runner_params.app_window_params.borderless_movable = True
    runner_params.app_window_params.borderless_resizable = True
    runner_params.app_window_params.borderless_closable = True

    runner_params.callbacks.load_additional_fonts = \
            lambda: load_fonts(app_state)
    
    runner_params.imgui_window_params.show_menu_bar = True
    runner_params.imgui_window_params.show_menu_app = False
    runner_params.imgui_window_params.show_menu_view = False
    runner_params.callbacks.show_menus = \
            lambda: show_menus(runner_params, app_state)

    runner_params.callbacks.post_init = lambda: post_init(app_state)
    runner_params.callbacks.before_exit = lambda: before_exit(app_state)

    runner_params.imgui_window_params.default_imgui_window_type = (
        hello_imgui.DefaultImGuiWindowType.provide_full_screen_dock_space
    )

    runner_params.callbacks.show_gui = lambda: gui(app_state)
    runner_params.callbacks.pre_new_frame = lambda: run_task(app_state)

    hello_imgui.run(
        runner_params
    )


def load_fonts(app_state: AppState):
    """
    @exception
    - ???
    """

    logger.info("Loading application fonts...")

    app_state.font = hello_imgui.load_font("fonts/blex_mono_nerd_font.ttf", 18)

    symbol_font_params = hello_imgui.FontLoadingParams()
    symbol_font_params.merge_to_last_font = True
    symbol_font_params.glyph_ranges = [ (0xe003, 0xf8ff) ]
    app_state.symbol_font = hello_imgui.load_font("fonts/symbol_font.ttf", 18, symbol_font_params)

    logger.info("Loaded application fonts")


def show_menus(
        runner_params: hello_imgui.RunnerParams, app_state: AppState):
    hello_imgui.show_view_menu(runner_params)

    gui_file_menu(app_state)
    gui_setting_menu(app_state)


def gui(app_state: AppState):
    """
    @exception
    - AssertionError
    """
    bank_states = app_state.bank_states

    run_critical_modal(app_state)
    run_warning_modal(app_state)
    run_confirm_modal(app_state)

    # gui_debug_state_windows(app_state)

    gui_log_windows(app_state)

    close_archives_queue = app_state.killed_banks
    for bank_state_id, bank_state in bank_states.items():
        is_close = gui_bank_viewer(app_state, bank_state)
        if not is_close:
            close_archives_queue.append(bank_state_id)


def gui_log_windows(app_state: AppState):
    ok, _ = imgui.begin("Logs")
    if not ok:
        imgui.end()

        return

    imgui.text_wrapped(app_state.gui_log_handler.to_string())
    imgui.end()

    return


def gui_debug_state_windows(app_state: AppState):
    ok, _ = imgui.begin("Debug State")
    if ok:
        if imgui.tree_node(f"Bank states ({len(app_state.bank_states)})"):
            for bid, state in app_state.bank_states.items():
                imgui.text(f"{bid}: {state.file_handler.file_reader.path}")
            imgui.tree_pop()

        if imgui.tree_node(f"Loaded files ({len(app_state.loaded_files)})"):
            for path in app_state.loaded_files:
                imgui.text(path)
            imgui.tree_pop()

        imgui.text(f"Closed archives in queue count: {len(app_state.killed_banks)}")

        imgui.end()
        return

    imgui.end()


def gui_file_menu(app_state: AppState):
    if not imgui.begin_menu("File"):
        return

    gui_archive_menu(app_state)

    imgui.end_menu()


def gui_archive_menu(app_state: AppState):
    """
    @exception
    - ???
    """
    archive_picker = app_state.archive_picker

    if not imgui.begin_menu("Load Archive"):
        return

    gui_archive_menu_recent(app_state)

    if imgui.menu_item_simple("From Helldivers 2 Data Folder"):
        if os.path.exists(env.get_data_path()):
            try:
                archive_picker.schedule("Select An Archive", env.get_data_path(), True)
            except AssertionError:
                app_state.warning_modals.append(
                    MsgModalState("Please finish the current archive selection.")
                )
        else:
            app_state.warning_modals.append(MsgModalState(
                "Incorrect Helldivers 2 data directory path.\n"
                "Please set it in the \"Setting\""
            ))

    if imgui.menu_item_simple("From File Explorer"):
        try:
            archive_picker.schedule("Select An Archive", multi=True)
        except AssertionError:
            app_state.warning_modals.append(
                MsgModalState("Please finish the current archive selection.")
            )


    imgui.end_menu()


def gui_archive_menu_recent(app_state: AppState):
    recent_files = app_state.setting.recent_files

    if len(recent_files) <= 0:
        imgui.menu_item_simple("From Recent", enabled=False)
        return

    if not imgui.begin_menu("From Recent"):
        return

    for recent_file in recent_files:
        if imgui.menu_item_simple(recent_file):
            app_state.io_task_queue \
                    .append(lambda: load_archive_new_viewer_helper(app_state, 
                                                                   recent_file))
            break

    imgui.end_menu()


def gui_setting_menu(app_state: AppState):
    data_folder_picker = app_state.data_folder_picker

    if not imgui.begin_menu("Setting"):
        return

    if imgui.menu_item_simple("Set Helldivers 2 Data Folder Directory Path"):
        try:
            data_folder_picker.schedule("Set Helldivers 2 Data Folder Directory Path")
        except AssertionError:
            app_state.warning_modals.append(
                MsgModalState("Please finish the current selection.")
            )

    imgui.end_menu()


def run_critical_modal(app_state: AppState):
    critical_modal = app_state.critical_modal
    if critical_modal == None:
        return

    if not critical_modal.is_trigger:
        imgui.open_popup("Critical")
        critical_modal.is_trigger = True

    ok, _ = imgui.begin_popup_modal(
            "Critical", flags = imgui.WindowFlags_.always_auto_resize.value)
    if not ok:
        return

    imgui.text(critical_modal.msg + "\nPlease check log.txt")
    if imgui.button("Exit", imgui.ImVec2(imgui.FLT_MAX, 0)):
        logger.critical(critical_modal.err)
        imgui.close_current_popup()
        imgui.end_popup()

    imgui.end_popup()
        

def run_warning_modal(app_state: AppState):
    warning_modals = app_state.warning_modals
    if len(warning_modals) <= 0:
        return

    top = warning_modals[0]
    if not top.is_trigger:
        imgui.open_popup("Warning")
        top.is_trigger = True

    ok, _ = imgui.begin_popup_modal("Warning",
                                    flags = imgui.WindowFlags_.always_auto_resize.value)
    if not ok:
        return

    imgui.text(top.msg)
    if imgui.button("OK", imgui.ImVec2(-imgui.FLT_MIN, 0)):
        imgui.close_current_popup()
        imgui.end_popup()
        warning_modals.popleft()
        return
    imgui.end_popup()


def run_confirm_modal(app_state: AppState):
    confirm_modals = app_state.confirm_modals
    if len(confirm_modals) <= 0:
        return

    top = confirm_modals[0]
    if not top.is_trigger:
        imgui.open_popup("Required Action")
        top.is_trigger = True

    ok, _ = imgui.begin_popup_modal(
            "Required Action", 
            flags = imgui.WindowFlags_.always_auto_resize.value)
    if not ok:
        return

    imgui.text(top.msg)
    callback = top.callback

    if imgui.button("Yes", imgui.ImVec2(128.0, 0)):
        if callback != None:
            callback(True)
        imgui.close_current_popup()
        imgui.end_popup()
        confirm_modals.popleft()
        return

    imgui.set_item_default_focus()

    imgui.same_line()
    if imgui.button("No", imgui.ImVec2(128.0, 0)):
        if callback != None:
            callback(False)
        imgui.close_current_popup()
        imgui.end_popup()
        confirm_modals.popleft()
        return

    imgui.same_line()
    if imgui.button("Cancel", imgui.ImVec2(128.0, 0)):
        imgui.close_current_popup()
        imgui.end_popup()
        confirm_modals.popleft()
        return

    imgui.end_popup()


def run_task(app_state: AppState):
    archive_picker = app_state.archive_picker
    data_folder_picker = app_state.data_folder_picker

    if archive_picker.is_ready():
        results = archive_picker.get_result()
        for result in results:
            app_state.io_task_queue \
                     .append(lambda: load_archive_new_viewer_helper(app_state,
                                                                    result))
        archive_picker.reset()

    process_killed_banks(app_state)

    while len(app_state.io_task_queue) > 0:
        app_state.io_task_queue.popleft()()

    if data_folder_picker.is_ready():
        results = data_folder_picker.get_result() 
        app_state.setting.data = results
        env.set_data_path(results)
        data_folder_picker.reset()


def process_killed_banks(app_state: AppState):
    """
    @exception
    - AssertionError
    """
    bank_states = app_state.bank_states

    killed_banks = app_state.killed_banks

    num_closed_bank = len(killed_banks)
    while len(killed_banks) > 0:
        bank_state_id = killed_banks.popleft()

        if bank_state_id not in bank_states:
            app_state.critical_modal = CriticalModalState(
                    "Assertion Error",
                    AssertionError(f"{bank_state_id} does not have an associate "
                                    "bank state."))
            return

        bank_state = bank_states[bank_state_id]
        if len(bank_state.changed_hirc_views.items()) <= 0:
            kill_bank_state(app_state, bank_state_id)
            continue

        def callback(save: bool):
            try:
                if not save:
                    write_hirc_obj_record_changes(app_state, bank_state)
                kill_bank_state(app_state, bank_state_id)
            except NotImplementedError as err:
                app_state.warning_modals.append(MsgModalState(
                    "Database functionalities is disabled."))
            except sqlite3.Error as err:
                app_state.warning_modals.append(MsgModalState(
                    "Failed to save changes\nCheck \"Log\" window"))
                logger.error(err)
            except AssertionError as err:
                app_state.critical_modal = CriticalModalState("Assertion Error",
                                                              err)

        app_state.confirm_modals.append(ConfirmModalState(
            "There are unsave changes.\nSave before closing this bank viewer?",
            callback = callback
        ))

        break

    if num_closed_bank > 0:
        gc.collect()


def post_init(app_state: AppState):
    try:
        setup_app_storage()
    except OSError as err:
        app_state.critical_modal = CriticalModalState(
            "Failed to create temporary data storage location.", err)

    try:
        logger.info("Loading application user setting...")

        app_state.setting = setting.load_setting()
        env.set_data_path(app_state.setting.data)
        if not os.path.exists(env.get_data_path()):
            app_state.warning_modals.append(MsgModalState(
                "Incorrect Helldivers 2 data directory path.\n"
                "Please set it in the \"Setting\""
            ))

        logger.info("Loaded application user setting")
    except (OSError, pickle.PickleError) as err:
        if app_state.critical_modal == None:
            app_state.critical_modal = CriticalModalState(
                "Failed to load user setting.\n"
                "Try removing \"setting.pickle\" and restart.",
                err
            )

    try:
        logger.info("Making local database connection...")

        app_state.db = SQLiteDatabase(config_sqlite_conn("database"))

        logger.info("Connected to local database.")
    except sqlite3.Error as err:
        logger.error("Failed to load database. Database functionalities is disabled. Reason: {err}")
    except OSError as err:
        logger.error("Failed to locate database. Database functionalities is disabled.")


def setup_app_storage():
    """
    @exception
    - OSError
    """
    logger.info("Setting up application storage...")

    if os.path.exists(env.TMP):
        logger.warning("Previous application session didn't clean up temporary"
                       " storage. Removing...")
        shutil.rmtree(env.TMP)
        logger.warning("Removed temporary storage")

    logger.info("Creating temporary storage...")
    os.mkdir(env.TMP)
    logger.info("Created temporary storage")

    logger.info("Application storage setup completed")


def before_exit(app_state: AppState):
    app_state.setting != None and app_state.setting.save()


if __name__ == "__main__":
    """
    !!! Remove this once the UI is stable enough.
    """
    main()
