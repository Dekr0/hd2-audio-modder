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
    - Exception
    """
    new_state = new_bank_viewer_state(app_state.sound_handler)

    new_state.file_handler.load_archive_file(file_path)

    fetch_bank_hierarchy_object_view(app_state, new_state)
    create_bank_hierarchy_view(new_state)

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
    file_handler.load_archive_file(file_path)
    fetch_bank_hierarchy_object_view(app_state, bank_state)
    create_bank_hierarchy_view(bank_state)


def update_bank_state_window_name(
        app_state: AppState, bank_state: BankViewerState):
    """
    @exception
    - AssertionError
    """
    bank_id_to_window_name = app_state.bank_id_to_window_name
    if bank_state.id not in bank_id_to_window_name:
        raise AssertionError(f"Bank state {id} does not has an associative "
                             "docking window.")
    old_window_name = app_state.bank_id_to_window_name.pop(bank_state.id)

    bank_states = app_state.bank_states
    if old_window_name not in bank_states: 
        raise AssertionError(f"Docking window name {old_window_name} does not has an "
                             "associative BankViewerState")
    app_state.bank_states.pop(old_window_name)

    file_reader = bank_state.file_handler.file_reader
    window_name = "Bank Viewer"
    if hasattr(file_reader, "name"):
        window_name = f"{file_reader.name}"

    counter = 1
    while window_name in app_state.bank_states:
        window_name += f" ({counter})"

    bank_states[window_name] = bank_state
    app_state.bank_id_to_window_name[bank_state.id] = window_name
