import sqlite3

import fileutil
from log import logger

from ui.bank_viewer.load_archive_ctrl import open_archive_new_viewer
from ui.view_data import AppState


def main_open_archive_new_viewer(app_state: AppState, file_path: str):
    """
    @description
    - Calls for open_archive_new_viewer with 
        - AppState.bank_states appending
        - AppState.bank_states window name collision check
        - exception handling and modal
    """

    file_path = fileutil.to_posix(file_path)
    try:
        new_state = open_archive_new_viewer(app_state, file_path)

        if new_state == None:
            return

        bank_states = app_state.bank_states
        if new_state.id in bank_states:
            raise AssertionError("Bank state ID collision")

        app_state.bank_states[new_state.id] = new_state
        app_state.setting.update_recent_file(file_path)
    except OSError as e:
        # show modal or display on the logger
        logger.error(e)
    except sqlite3.Error as e:
        # show modal or display on the logger
        logger.error(e)
