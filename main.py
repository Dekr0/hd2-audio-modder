import os
import glfw
import shutil
import OpenGL.GL

# Module import
from imgui_bundle import imgui

# Definition import
from imgui_bundle.python_backends.glfw_backend import GlfwRenderer

from audio_modder import SoundHandler
from backend.env import *
from log import logger
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
    file_picker = app_state.file_picker
    bank_states = app_state.bank_states

    closed_banks: list[BankViewerState] = []
    for bank_state in bank_states:
        is_close = gui_bank_explorer(bank_state)
        if not is_close:
            closed_banks.append(bank_state)

    for bank_state in closed_banks:
        bank_states.remove(bank_state)

    # imgui.show_metrics_window()
    # imgui.show_debug_log_window()

    if file_picker.is_load_archive_file_ready():
        result = file_picker.archive_picker.result() # type: ignore

        if len(result) == 1:
            new_bank_explorer_state = new_bank_explorer_states(app_state.sound_handler)
            try:
                new_bank_explorer_state.file_handler.load_archive_file(archive_file=result[0])
                bank_states.append(new_bank_explorer_state)
                if new_bank_explorer_state.source_view:
                    create_bank_source_view(new_bank_explorer_state)
                else:
                    create_bank_hierarchy_view(new_bank_explorer_state)
                gui_bank_explorer(new_bank_explorer_state)
            except OSError as e:
                # Show popup window
                logger.error(e)
            except Exception as e:
                # Show popup window
                logger.error(e)

        file_picker.archive_picker = None

    OpenGL.GL.glClearColor(0, 0, 0, 1)
    OpenGL.GL.glClear(OpenGL.GL.GL_COLOR_BUFFER_BIT)

    imgui.render()
    impl.render(imgui.get_draw_data())
    glfw.swap_buffers(window)


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

    gui_file_menu(app_state.file_picker)

    imgui.end_menu_bar()


def gui_file_menu(file_picker: FilePicker):
    if not imgui.begin_menu("File"):
        return

    gui_archive_menu(file_picker)

    imgui.end_menu()


def gui_archive_menu(file_picker: FilePicker):
    if not imgui.begin_menu("Load Archive"):
        return

    if imgui.menu_item_simple("From HD2 Data Folder"):
        file_picker.schedule_load_archive_file(get_data_path())
    if imgui.menu_item_simple("From File Explorer"):
        file_picker.schedule_load_archive_file()

    imgui.end_menu()


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
    setup_app_data()

    window, impl, font, symbol_font = init()

    app_state = new_app_state(SoundHandler(), FilePicker(), font, symbol_font)
    while not glfw.window_should_close(window):
        render(window, impl, app_state)

    impl.shutdown()
    glfw.terminate()


if __name__ == "__main__":
    main()
