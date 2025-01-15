import gc
import os
import glfw
import shutil
import OpenGL.GL

# Module import
from imgui_bundle import imgui

# Definition import
from imgui_bundle.python_backends.glfw_backend import GlfwRenderer

from backend.env import *
from log import logger
from setting import *
from ui.ui_flags import *
from ui.ui_bank_explorer import *
from ui.view_data import *

NTHREAD = 8


def render(window, impl, app_state: AppState):
    if window == None:
        raise RuntimeError("Assertion error. GLFW window is None.")
    if impl == None:
        raise RuntimeError("Assertion error. GlfwRenderer is None.")

    glfw.poll_events()
    impl.process_inputs()
    
    imgui.new_frame()

    gui_docking_window(app_state)

    archive_picker = app_state.archive_picker
    data_folder_picker = app_state.data_folder_picker

    bank_states = app_state.bank_states

    if run_critical_modal(app_state):
        return False
    run_warning_modal(app_state)

    closed_banks: list[BankViewerState] = []
    for bank_state in bank_states:
        is_close = gui_bank_explorer(app_state, bank_state)
        if not is_close:
            closed_banks.append(bank_state)

    num_closed_bank = len(closed_banks)
    for bank_state in closed_banks:
        bank_states.remove(bank_state)
    closed_banks.clear()
    if num_closed_bank > 0:
        gc.collect()

    # imgui.show_metrics_window()
    # imgui.show_debug_log_window()

    if archive_picker.is_ready():
        result = archive_picker.get_result()
        for archive in result:
            new_bank_explorer_state = new_bank_explorer_states(app_state.sound_handler)
            try:
                new_bank_explorer_state.file_handler.load_archive_file(archive_file=archive)
                bank_states.append(new_bank_explorer_state)
                if new_bank_explorer_state.source_view:
                    create_bank_source_view(new_bank_explorer_state)
                else:
                    create_bank_hierarchy_view(new_bank_explorer_state)
                gui_bank_explorer(app_state, new_bank_explorer_state)
            except OSError as e:
                # Show popup window
                logger.error(e)
            except Exception as e:
                # Show popup window
                logger.error(e)

        archive_picker.reset()

    if data_folder_picker.is_ready():
        result = data_folder_picker.get_result() 
        if app_state.setting == None:
            raise AssertionError("setting is None")
        app_state.setting.data = result
        set_data_path(result)
        data_folder_picker.reset()

    OpenGL.GL.glClearColor(0, 0, 0, 1)
    OpenGL.GL.glClear(OpenGL.GL.GL_COLOR_BUFFER_BIT)

    imgui.render()
    impl.render(imgui.get_draw_data())
    glfw.swap_buffers(window)

    return True


def gui_docking_window(app_state: AppState):
    viewport = imgui.get_main_viewport()
    imgui.set_next_window_pos(viewport.work_pos)
    imgui.set_next_window_size(viewport.work_size)
    imgui.set_next_window_viewport(viewport.id_)
    imgui.push_style_var(imgui.StyleVar_.window_rounding.value, 0.0)
    imgui.push_style_var(imgui.StyleVar_.window_border_size.value, 0.0)
    imgui.push_style_var(imgui.StyleVar_.window_padding.value, imgui.ImVec2(0, 0))

    imgui.begin("Shovel", False, DOCKING_WINDOW_FLAGS)
    imgui.pop_style_var(3)

    dockspace_id = imgui.get_id("main")
    imgui.dock_space(dockspace_id, imgui.ImVec2(0, 0), DOCKSPACE_FLAGS)

    gui_menu_bar(app_state)

    imgui.end()


def gui_menu_bar(app_state: AppState):
    if not imgui.begin_menu_bar():
        return

    gui_file_menu(app_state)
    gui_setting_menu(app_state)

    imgui.end_menu_bar()


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
    if critical_modal != None:
        if not critical_modal.is_trigger:
            imgui.open_popup("Critical")
            critical_modal.is_trigger = True
        ok, _ = imgui.begin_popup_modal("Critical")
        if ok:
            imgui.text(critical_modal.msg)
            if imgui.button("Exit"):
                imgui.close_current_popup()
                imgui.end_popup()
                return True
            imgui.end_popup()
    return False


def run_warning_modal(app_state: AppState):
    warning_modals = app_state.warning_modals
    if len(warning_modals) > 0:
        top = warning_modals[0]
        if not top.is_trigger:
            imgui.open_popup("Warning")
            top.is_trigger = True
        ok, _ = imgui.begin_popup_modal("Warning")
        if ok:
            imgui.text(top.msg)
            if imgui.button("OK"):
                imgui.close_current_popup()
                imgui.end_popup()
                warning_modals.popleft()
                return
            imgui.end_popup()


def impl_glfw_init():
    """
    @return
    window - Guarantee is not None
    """
    width, height = 1280, 720
    window_name = "Shovel"

    if not glfw.init():
        # Logging
        exit(1)

    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)

    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, OpenGL.GL.GL_TRUE)

    window = glfw.create_window(width, height, window_name, None, None)
    glfw.make_context_current(window)

    if window == None:
        glfw.terminate()
        # Logging
        exit(1)

    return window


def init():
    """
    @return 
    window - Guarantee is not None
    impl - Guarantee is not None
    """
    imgui.create_context()
    imgui.get_io().config_flags |= imgui.ConfigFlags_.docking_enable.value

    font = imgui.get_io().fonts.add_font_from_file_ttf(
            "fonts/blex_mono_nerd_font.ttf", 18)
    cfg = imgui.ImFontConfig()
    cfg.merge_mode = True
    symbol_font = imgui.get_io().fonts.add_font_from_file_ttf(
            "fonts/symbol_font.ttf", 18, cfg, [ 0xe003, 0xf8ff, 0 ])

    window = impl_glfw_init()
    if window == None:
        raise RuntimeError("Assertion error. GLFW window is None.")

    impl = GlfwRenderer(window)
    if impl == None:
        raise RuntimeError("Assertion error. GlfwRenderer is None.")

    return window, impl, font, symbol_font


def setup_app_data():
    """
    @exception
    - OSError
    """
    if os.path.exists(TMP):
        # Try-Except Block
        shutil.rmtree(TMP)
    os.mkdir(TMP)


def main():

    window, impl, font, symbol_font = init()

    app_state = new_app_state(font, symbol_font)

    try:
        setup_app_data()
    except OSError as err:
        app_state.critical_modal = MessageModalState(
            f"Failed to create temporary data storage location. Reason: {err}."
            "Please report this to the developers.")

    try:
        app_state.setting = load_setting()
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

    while not glfw.window_should_close(window):
        if not render(window, impl, app_state):
            break

    app_state.setting != None and app_state.setting.save() # type: ignore

    impl.shutdown()
    glfw.terminate()


if __name__ == "__main__":
    main()
