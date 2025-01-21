import os
import pickle
import shutil
import setting
import backend.env as env

# Module import
from imgui_bundle import hello_imgui, imgui

from backend.db.db_access import config_sqlite_conn
from fileutil import to_posix
from log import logger
from ui.bank_viewer.draw_gui import gui_bank_viewer
from ui.app_state import AppState


NTHREAD = 8


def main():
    hello_imgui.set_assets_folder(".")

    app_state = AppState()

    runner_params = hello_imgui.RunnerParams()
    runner_params.app_window_params.window_title = "Shovel"
    runner_params.app_window_params.window_geometry.size = (1280, 720)
    runner_params.app_window_params.restore_previous_geometry = True
    runner_params.app_window_params.borderless = True
    runner_params.app_window_params.borderless_movable = True
    runner_params.app_window_params.borderless_resizable = True
    runner_params.app_window_params.borderless_closable = True

    runner_params.callbacks.load_additional_fonts = lambda: load_fonts(app_state)
    
    runner_params.imgui_window_params.show_menu_bar = True
    runner_params.imgui_window_params.show_menu_app = False
    runner_params.imgui_window_params.show_menu_view = False
    runner_params.callbacks.show_menus = lambda: show_menus(runner_params, app_state)

    runner_params.callbacks.post_init = lambda: post_init(app_state)
    runner_params.callbacks.before_exit = lambda: before_exit(app_state)

    runner_params.imgui_window_params.default_imgui_window_type = (
        hello_imgui.DefaultImGuiWindowType.provide_full_screen_dock_space
    )

    runner_params.callbacks.show_gui = lambda: gui(app_state)
    runner_params.callbacks.pre_new_frame = lambda: app_state.run_logic_loop()

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

    app_state.process_modals()

    gui_debug_state_windows(app_state)

    gui_log_windows(app_state)

    for bank_state_id, bank_state in bank_states.items():
        is_open = gui_bank_viewer(app_state, bank_state)
        if not is_open:
            if app_state.has_issue_db_write(bank_state):
                app_state.queue_warning_modal(
                    "A database write operation is issued by this bank viewer\n"
                    "Please wait for this to finished."
                )
                continue

            bank_state.close()
            if len(bank_state.mut_hirc_views) > 0:
                def callback(save: bool):
                    try:
                        app_state.gc_bank(bank_state_id)

                        if app_state.is_db_enabled and save:
                            app_state.write_hirc_obj_records(bank_state)
                    except AssertionError as err:
                        app_state.queue_critical_modal("Assertion Error", err)

                # TODO, label which bank explorer is closing
                app_state.queue_confirm_modal(
                    "There are unsave changes.\n"
                    "Save before closing this bank viewer?",
                    callback = callback
                )
            else:
                app_state.gc_bank(bank_state_id)


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
        imgui.text(app_state.__str__())
        imgui.text(app_state.logic_loop.__str__())
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
    if not imgui.begin_menu("Load Archive"):
        return

    gui_archive_menu_recent(app_state)

    if imgui.menu_item_simple("From Helldivers 2 Data Folder"):
        if os.path.exists(env.get_data_path()):

            def callback(paths: list[str]):
                for p in paths:
                    try:
                        app_state.load_archive_new_viewer(to_posix(p))
                    except OSError as err:
                        app_state.queue_warning_modal(
                            f"Failed to load archive {p}\n"
                            "Check \"Log\" window."
                        )
                        logger.error(err)
                    except AssertionError as err:
                        app_state.queue_critical_modal(f"Assertion Error", err)
                    except Exception as err:
                        app_state.queue_critical_modal(f"Unhandle exception", err)


            app_state.queue_file_picker_task(
                "Select An Archive",
                lambda paths: callback(paths),
                env.get_data_path(),
                multi = True
            )
        else:
            app_state.queue_warning_modal(
                "Incorrect Helldivers 2 data directory path.\n"
                "Please set it in the \"Setting\""
            )

    if imgui.menu_item_simple("From File Explorer"):
        def callback(paths: list[str]):
            for p in paths:
                try:
                    app_state.load_archive_new_viewer(to_posix(p))
                except OSError as err:
                    app_state.queue_warning_modal(
                        f"Failed to load archive {p}\n"
                        "Check \"Log\" window."
                    )
                    logger.error(err)
                except AssertionError as err:
                    app_state.queue_critical_modal(f"Assertion Error", err)
                except Exception as err:
                    app_state.queue_critical_modal(f"Unhandle exception", err)


        app_state.queue_file_picker_task(
            "Select An Archive",
            lambda paths: callback(paths),
            env.get_data_path(),
            multi = True
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

            def callback():
                try:
                    app_state.load_archive_new_viewer(recent_file)
                except OSError as err:
                    app_state.queue_warning_modal(
                        f"Failed to load archive {recent_file}\n"
                        "Check \"Log\" window."
                    )
                    logger.error(err)
                except AssertionError as err:
                    app_state.queue_critical_modal(f"Assertion Error", err)
                except Exception as err:
                    app_state.queue_critical_modal(f"Unhandle exception", err)

            app_state.queue_macro_task(callback)

            break

    imgui.end_menu()


def gui_setting_menu(app_state: AppState):
    if not imgui.begin_menu("Setting"):
        return

    if imgui.menu_item_simple("Set Helldivers 2 Data Folder Directory Path"):
        app_state.queue_folder_picker_task(
            "Set Helldivers 2 Data Folder Directory Path",
            lambda path: env.set_data_path(path)
        )

    imgui.end_menu()


def post_init(app_state: AppState):
    try:
        setup_app_storage()
    except OSError as err:
        app_state.queue_critical_modal(
            "Failed to create temporary data storage location.", err
        )

    try:
        logger.info("Loading application user setting...")

        app_state.setting = setting.load_setting()
        env.set_data_path(app_state.setting.data)
        if not os.path.exists(env.get_data_path()):
            app_state.queue_warning_modal(
                "Incorrect Helldivers 2 data directory path.\n"
                "Please set it in the \"Setting\""
            )

        logger.info("Loaded application user setting")
    except (OSError, pickle.PickleError) as err:
        app_state.queue_critical_modal(
            "Failed to load user setting.\n"
            "Try removing \"setting.pickle\" and restart.",
            err
        )
    try:
        logger.info("Testing local database connection...")
        app_state.db_conn_config = config_sqlite_conn("database")
        logger.info("Connection test success. Please do not remove `database`.")
    except OSError as err:
        logger.error("Failed to locate database. Database access is disabled.")


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
