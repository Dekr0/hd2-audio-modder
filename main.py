import gc
import os
import pickle
import shutil

import setting

# Module import
from imgui_bundle import hello_imgui, imgui

from backend.db.db_access import config_sqlite_conn
from backend.env import *
from log import logger
from ui.ui_flags import *
from ui.ui_bank_explorer import *
from ui.view_data import *

NTHREAD = 8


def main():
    hello_imgui.set_assets_folder(".")

    app_state = new_app_state() 

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

    hello_imgui.run(
        runner_params
    )


def load_fonts(app_state: AppState):

    app_state.font = hello_imgui.load_font("fonts/blex_mono_nerd_font.ttf", 18)

    symbol_font_params = hello_imgui.FontLoadingParams()
    symbol_font_params.merge_to_last_font = True
    symbol_font_params.glyph_ranges = [ (0xe003, 0xf8ff) ]
    app_state.symbol_font = hello_imgui.load_font("fonts/symbol_font.ttf", 18, symbol_font_params)


def show_menus(
        runner_params: hello_imgui.RunnerParams, app_state: AppState):
    hello_imgui.show_view_menu(runner_params)

    gui_file_menu(app_state)
    gui_setting_menu(app_state)


def gui(app_state: AppState):
    archive_picker = app_state.archive_picker
    data_folder_picker = app_state.data_folder_picker

    bank_states = app_state.bank_states

    if run_critical_modal(app_state):
        exit(1)
    run_warning_modal(app_state)
    run_confirm_modal(app_state)

    closed_banks: list[BankViewerState] = []
    for bank_state in bank_states:
        is_close = gui_bank_explorer(app_state, bank_state)
        if not is_close:
            closed_banks.append(bank_state)

    num_closed_bank = len(closed_banks)
    for bank_state in closed_banks:
        if len(bank_state.changed_hierarchy_views.items()) <= 0:
            bank_states.remove(bank_state)
            continue

        def callback(save: bool):
            if save:
                save_hierarchy_object_views_change_with_modal(app_state,
                                                              bank_state)
            bank_states.remove(bank_state)

        app_state.confirm_modals.append(ConfirmModalState(
            "There are unsave changes. Do you want to save before closing "
            "this bank explorer?",
            callback = callback
        ))

        break

    closed_banks.clear()
    if num_closed_bank > 0:
        gc.collect()

    if archive_picker.is_ready():
        result = archive_picker.get_result()
        for archive in result:
            new_bank_explorer_state = new_bank_explorer_states(app_state.sound_handler)
            try:
                new_bank_explorer_state.file_handler.load_archive_file(archive)
                bank_states.append(new_bank_explorer_state)
                fetch_bank_hierarchy_object_view(app_state, new_bank_explorer_state)
                create_bank_hierarchy_view(new_bank_explorer_state)
                gui_bank_explorer(app_state, new_bank_explorer_state)
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

    if data_folder_picker.is_ready():
        result = data_folder_picker.get_result() 
        if app_state.setting == None:
            raise AssertionError("setting is None")
        app_state.setting.data = result
        set_data_path(result)
        data_folder_picker.reset()


def gui_file_menu(app_state: AppState):
    if not imgui.begin_menu("File"):
        return

    gui_archive_menu(app_state)

    imgui.end_menu()


def gui_archive_menu(app_state: AppState):
    archive_picker = app_state.archive_picker

    if not imgui.begin_menu("Load Archive"):
        return

    if imgui.menu_item_simple("From Helldivers 2 Data Folder"):
        if os.path.exists(get_data_path()):
            try:
                archive_picker.schedule("Select An Archive", get_data_path(), True)
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


def gui_setting_menu(app_state: AppState):
    data_folder_picker = app_state.data_folder_picker

    if not imgui.begin_menu("Setting"):
        return

    if imgui.menu_item_simple("Set Helldivers 2 Data Folder Directory Path"):
        try:
            data_folder_picker.schedule("Set Helldivers 2 Data Folder Directory Path")
        except AssertionError:
            app_state.warning_modals.append(
                MessageModalState("Please finish the current selection.")
            )

    imgui.end_menu()


def run_critical_modal(app_state: AppState) -> bool:
    critical_modal = app_state.critical_modal
    if critical_modal == None:
        return False

    if not critical_modal.is_trigger:
        imgui.open_popup("Critical")
        critical_modal.is_trigger = True

    ok, _ = imgui.begin_popup_modal("Critical", flags = imgui.WindowFlags_.always_auto_resize.value)
    if not ok:
        return False

    imgui.text(critical_modal.msg)
    if imgui.button("Exit"):
        imgui.close_current_popup()
        imgui.end_popup()
        return True

    imgui.end_popup()

    return False
        

def run_warning_modal(app_state: AppState):
    warning_modals = app_state.warning_modals
    if len(warning_modals) <= 0:
        return

    top = warning_modals[0]
    if not top.is_trigger:
        imgui.open_popup("Warning")
        top.is_trigger = True

    ok, _ = imgui.begin_popup_modal("Warning", flags = imgui.WindowFlags_.always_auto_resize.value)
    if not ok:
        return

    imgui.text(top.msg)
    if imgui.button("OK"):
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

    ok, _ = imgui.begin_popup_modal("Required Action", flags = imgui.WindowFlags_.always_auto_resize.value)
    if not ok:
        return

    imgui.text(top.msg)
    callback = top.callback

    if imgui.button("Yes"):
        if callback != None:
            callback(True)
        imgui.close_current_popup()
        imgui.end_popup()
        confirm_modals.popleft()
        return

    if imgui.button("No"):
        if callback != None:
            callback(False)
        imgui.close_current_popup()
        imgui.end_popup()
        confirm_modals.popleft()
        return

    imgui.end_popup()


def post_init(app_state: AppState):
    try:
        setup_app_data()
    except OSError as err:
        app_state.critical_modal = MessageModalState(
            f"Failed to create temporary data storage location. Reason: {err}."
            "Please report this to the developers.")

    try:
        app_state.setting = setting.load_setting()
        set_data_path(app_state.setting.data)
        if not os.path.exists(get_data_path()):
            app_state.warning_modals.append(MessageModalState(
                f"The directory path for Helldivers 2 data folder in the setting "
                "is not correct. Please set that in the Setting."
            ))
    except (OSError, pickle.PickleError) as err:
        if app_state.critical_modal == None:
            app_state.critical_modal = MessageModalState(
                "Failed to load user setting. Try removing `setting.pickle`"
                f" and restart. Reason: {err}."
            )

    try:
        app_state.db = SQLiteDatabase(config_sqlite_conn("database"))
    except sqlite3.Error as err:
        app_state.warning_modals.append(MessageModalState(
            f"Failed to load database. Reason: {err}"))


def setup_app_data():
    """
    @exception
    - OSError
    """
    if os.path.exists(TMP):
        # Try-Except Block
        shutil.rmtree(TMP)
    os.mkdir(TMP)


def before_exit(app_state: AppState):
    app_state.setting != None and app_state.setting.save()


if __name__ == "__main__":
    """
    !!! Remove this once the UI is stable enough.
    """
    try:
        main()
    except Exception as err:
        logger.critical(err)
