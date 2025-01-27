import os
import pickle
import shutil
import setting
import backend.env as env

# Module import
from imgui_bundle import hello_imgui, imgui

from backend.db.db_access import config_sqlite_conn
from log import logger
from ui.app_state import AppState
from ui.task_def import Action


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
    runner_params.imgui_window_params.show_status_bar = True
    runner_params.imgui_window_params.show_menu_app = False
    runner_params.imgui_window_params.show_menu_view = False
    runner_params.callbacks.show_menus = lambda: show_menus(runner_params, app_state)
    runner_params.callbacks.show_status = lambda: show_status(app_state)

    runner_params.callbacks.post_init = lambda: post_init(app_state)
    runner_params.callbacks.before_exit = lambda: before_exit(app_state)

    runner_params.imgui_window_params.default_imgui_window_type = (
        hello_imgui.DefaultImGuiWindowType.provide_full_screen_dock_space
    )

    def show_gui():
        gui(app_state)

    def pre_new_frame():
        app_state.run_logic_loop()

    runner_params.callbacks.show_gui = show_gui 
    runner_params.callbacks.pre_new_frame = pre_new_frame 

    hello_imgui.run(runner_params)


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

    logger.info("Loaded application fonts.")


def show_menus(runner_params: hello_imgui.RunnerParams, app_state: AppState):
    hello_imgui.show_view_menu(runner_params)

    gui_file_menu(app_state)
    gui_setting_menu(app_state)


def show_status(app_state: AppState):
    if app_state.logic_loop.is_db_write_busy():
        imgui.text("Database write operation status: Active")


def gui(app_state: AppState):
    """
    @exception
    - AssertionError
    """
    app_state.start_timer()


    app_state.process_modals()

    gui_debug_state_windows(app_state)

    gui_log_windows(app_state)

    """
    bank_states = app_state.bank_states
    for bank_state_id, bank_state in bank_states.items():
        is_open = gui_bank_viewer(app_state, bank_state)
        if not is_open:
            if app_state.logic_loop.has_issue_db_write_action(bank_state):
                app_state.queue_warning_modal(
                    "A database write operation is issued by this bank viewer\n"
                    "Please wait for this to finished."
                )
                continue
            if app_state.logic_loop.has_issue_file_picker(bank_state):
                app_state.queue_warning_modal(
                    "Please finish the active file picker."
                )
                continue

            bank_state.close()

            if not bank_state.is_mut():
                app_state.gc_bank(bank_state_id)

            def on_click(save: bool):

                def task(_):
                    app_state.gc_bank(bank_state_id)
                    if app_state.is_db_enabled and save:
                        app_state.write_hirc_obj_records(bank_state)

                def on_reject(err: Exception | None):
                    if err == None:
                        return
                    app_state.queue_critical_modal("Assertion Error", err)
                    
                event = Event[AppState, None](app_state, task, on_reject = on_reject)

                app_state.logic_loop.queue_event(event)

            # TODO, label which bank explorer is closing
            app_state.queue_confirm_modal(
                "There are unsave changes.\n"
                "Save before closing this bank viewer?",
                callback = on_click
            )
    """


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
        imgui.end()
        return

    imgui.end()


def gui_file_menu(app_state: AppState):
    if not imgui.begin_menu("Mod"):
        return

    gui_new_mod(app_state)

    imgui.end_menu()


def gui_new_mod(app_state: AppState):
    if not imgui.begin_menu("New Mod"):
        return

    if imgui.menu_item_simple("Blank Mod"):
        def event():
            app_state.create_blank_mod()

        def on_cancel():
            logger.warning("Creating new blank mod is canceled.")

        def on_reject(err: BaseException | None):
            if isinstance(err, AssertionError):
                app_state.queue_critical_modal("AssertionError", err)
            else:
                app_state.queue_warning_modal(
                    "Failed to create a new blank mod.\n"
                    "Check \"Log\" window."
                )
                logger.error(err)

        app_state.logic_loop.queue_event(Action[AppState, None](
            app_state, event, on_cancel = on_cancel, on_reject = on_reject
        ))

    gui_load_archives_as_single_mod(app_state)
    gui_load_archives_as_separate_mods(app_state)

    imgui.end_menu()


def gui_load_archives_as_single_mod(app_state: AppState):
    if not imgui.begin_menu("Load Archives As New Mod"):
        return

    gui_load_archives_as_single_mod_recent(app_state)

    if imgui.menu_item_simple("From Helldivers 2 Data Folder"):
        if os.path.exists(env.get_data_path()):
            def on_cancel():
                logger.warning("Loading archives as a single new mod is canceled.")

            def on_reject(err: BaseException | None):
                if isinstance(err, AssertionError):
                    app_state.queue_critical_modal("AssertionError", err)
                else:
                    app_state.queue_warning_modal(
                        "Failed to load archiveas a single new mod\n"
                        "Check \"Log\" window."
                    )
                    logger.error(err)

            def on_files_selected(file_paths: list[str]):
                app_state.load_archives_as_single_new_mod(
                    file_paths, on_cancel, on_reject
                )

            app_state.logic_loop.queue_file_picker_action(
                app_state,
                "Select Archives",
                lambda file_paths: on_files_selected(file_paths),
                env.get_data_path(),
                multi = True
            )
        else:
            app_state.queue_warning_modal(
                "Incorrect Helldivers 2 data directory path.\n"
                "Please set it in the \"Setting\"."
            )
    if imgui.menu_item_simple("From File Explorer"):
        def on_cancel():
            logger.warning("Loading archives as a single new mod is canceled.")

        def on_reject(err: BaseException | None):
            if isinstance(err, AssertionError):
                app_state.queue_critical_modal("AssertionError", err)
            else:
                app_state.queue_warning_modal(
                    "Failed to load archiveas a single new mod.\n"
                    "Check \"Log\" window."
                )
                logger.error(err)

        def on_files_selected(file_paths: list[str]):
            app_state.load_archives_as_single_new_mod(
                file_paths, on_cancel, on_reject
            )

        app_state.logic_loop.queue_file_picker_action(
            app_state,
            "Select Archives",
            lambda file_paths: on_files_selected(file_paths),
            multi = True
        )

    imgui.end_menu()


def gui_load_archives_as_separate_mods(app_state: AppState):
    if not imgui.begin_menu("Load Archives As Multiple Mods"):
        return

    if imgui.menu_item_simple("From Helldivers 2 Data Folder"):
        if os.path.exists(env.get_data_path()):
            def on_cancel():
                logger.warning("Loading archives as a single new mod is canceled.")

            def on_reject(err: BaseException | None):
                if isinstance(err, AssertionError):
                    app_state.queue_critical_modal("AssertionError", err)
                else:
                    app_state.queue_warning_modal(
                        "Failed to load archiveas a single new mod.\n"
                        "Check \"Log\" window."
                    )
                    logger.error(err)

            def on_files_selected(file_paths: list[str]):
                app_state.load_archive_as_separate_new_mods(
                    file_paths, on_cancel, on_reject
                )

            app_state.logic_loop.queue_file_picker_action(
                app_state,
                "Select Archives",
                lambda file_paths: on_files_selected(file_paths),
                env.get_data_path(),
                multi = True
            )
        else:
            app_state.queue_warning_modal(
                "Incorrect Helldivers 2 data directory path.\n"
                "Please set it in the \"Setting\"."
            )
    if imgui.menu_item_simple("From File Explorer"):
        def on_cancel():
            logger.warning("Loading archives as a single new mod is canceled.")

        def on_reject(err: BaseException | None):
            if isinstance(err, AssertionError):
                app_state.queue_critical_modal("AssertionError", err)
            else:
                app_state.queue_warning_modal(
                    "Failed to load archiveas a single new mod.\n"
                    "Check \"Log\" window."
                )
                logger.error(err)

        def on_files_selected(file_paths: list[str]):
            app_state.load_archive_as_separate_new_mods(
                file_paths, on_cancel, on_reject
            )

        app_state.logic_loop.queue_file_picker_action(
            app_state,
            "Select Archives",
            lambda file_paths: on_files_selected(file_paths),
            multi = True
        )

    imgui.end_menu()


def gui_load_archives_as_single_mod_recent(app_state: AppState):
    recent_files = app_state.setting.recent_files

    if len(recent_files) <= 0:
        imgui.menu_item_simple("From Recent", enabled=False)
        return

    if not imgui.begin_menu("From Recent"):
        return

    for recent_file in recent_files:
        if imgui.menu_item_simple(recent_file):
            def on_cancel():
                logger.warning("Loading archives as a single new mod is canceled.")

            def on_reject(err: BaseException | None):
                if isinstance(err, AssertionError):
                    app_state.queue_critical_modal("AssertionError", err)
                else:
                    app_state.queue_warning_modal(
                        "Failed to load archiveas a single new mod.\n"
                        "Check \"Log\" window."
                    )
                    logger.error(err)

            app_state.load_archives_as_single_new_mod(
                [recent_file], on_cancel, on_reject
            )

            break

    imgui.end_menu()


def gui_setting_menu(app_state: AppState):
    if not imgui.begin_menu("Setting"):
        return

    if imgui.menu_item_simple("Set Helldivers 2 Data Folder Directory Path"):
        app_state.logic_loop.queue_folder_picker_action(
            None,
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
        app_state.queue_warning_modal(
            "Failed to locate database. Database access is disabled.")
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
        logger.warning("Removed temporary storage.")

    logger.info("Creating temporary storage...")
    os.mkdir(env.TMP)
    logger.info("Created temporary storage.")

    logger.info("Application storage setup completed.")


def before_exit(app_state: AppState):
    if app_state.setting != None:
        app_state.setting.save()
    if os.path.exists(env.TMP):
        shutil.rmtree(env.TMP)
        logger.warning("Removed temporary storage.")


if __name__ == "__main__":
    """
    !!! Remove this once the UI is stable enough.
    """
    main()
