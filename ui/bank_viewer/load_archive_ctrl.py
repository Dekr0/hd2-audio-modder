from ui.bank_viewer.view_ctrl import create_bank_hierarchy_view, fetch_bank_hierarchy_object_view

from ui.view_data import AppState, BankViewerState
from ui.view_data import new_bank_viewer_state


def open_archive_new_viewer(app_state: AppState, file_path: str):
    """
    @description
    Use on creating a new bank viewer

    @exception
    - OSError
    - sqlite3.Error
    - AssertionError
    """
    if file_path in app_state.loaded_files:
        return None

    new_state = new_bank_viewer_state(app_state.sound_handler)

    file_handler = new_state.file_handler
    file_handler.load_archive_file(file_path)
    if file_handler.file_reader.path != file_path:
        raise AssertionError("Path is not being normalized to POSIX standard."
                             f"Input: {file_path}; Stored: {file_handler.file_reader.path}")

    fetch_bank_hierarchy_object_view(app_state, new_state)
    create_bank_hierarchy_view(app_state, new_state)

    app_state.loaded_files.add(file_path)

    return new_state


def open_archive_exist_viewer(
        app_state: AppState, bank_state: BankViewerState, file_path: str):
    file_handler = bank_state.file_handler
    """
    @description
    Use on existing bank viewer.

    @exception
    - OSError
    - sqlite3.Error
    - Exception
    """
    loaded_files = app_state.loaded_files

    if file_path in loaded_files:
        return

    file_handler = bank_state.file_handler
    file_reader = file_handler.file_reader

    old_loaded_file_path = file_reader.path
    if old_loaded_file_path != "" and old_loaded_file_path not in loaded_files:
        raise AssertionError(f"File {old_loaded_file_path} is not being "
                             "tracked in the set of loaded file.")

    file_handler.load_archive_file(file_path)
    if file_handler.file_reader.path != file_path:
        raise AssertionError("Path is not being normalized to POSIX standard."
                             f"Input: {file_path}; Stored: {file_reader.path}")

    if old_loaded_file_path != "":
        loaded_files.remove(old_loaded_file_path)

    fetch_bank_hierarchy_object_view(app_state, bank_state)
    create_bank_hierarchy_view(app_state, bank_state)

    loaded_files.add(file_path)


def close_bank_state(app_state: AppState, bank_state_id: str):
    if bank_state_id not in app_state.bank_states:
        raise AssertionError(f"{bank_state_id} does not have an associate bank"
                             " state.")

    bank_state = app_state.bank_states.pop(bank_state_id)
    file_path = bank_state.file_handler.file_reader.path

    if file_path == "":
        return

    if file_path not in app_state.loaded_files:
        raise AssertionError(f"File {file_path} is not being tracked in the list"
                             " of loaded file.")

    app_state.loaded_files.remove(file_path)
