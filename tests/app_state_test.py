import time
import unittest

from backend.db.db_access import config_sqlite_conn
from backend.env import get_data_path, set_data_path
from log import logger
from ui.app_state import AppState
from ui.task_def import State


class TestAppState(unittest.TestCase):

    def test_load_archives_as_single_new_mod_dry(self):
        logger.info("test_load_archives_as_single_new_mod_dry")
        set_data_path("D:/Program Files/Steam/steamapps/common/Helldivers 2/data")

        def on_cancel():
            logger.warning("Task cancel")

        def on_reject(err: BaseException | Exception | None):
            logger.critical(err)

        game_archives = [
            "2e24ba9dd702da5c",
            "e75f556a740e00c9",
            "8f295b4d04c3a06c",
            "94b554570b12c088",
            "a66d7cf238070ca7",
            "bf2250de0b17285c",
            "c024a2e8ae639757",
        ]

        game_archives = [f"{get_data_path()}/{game_archive}" for game_archive in game_archives]

        app_state = AppState()
        app_state.db_conn_config = config_sqlite_conn("database")

        app_state.load_archives_as_single_new_mod(
            game_archives,
            on_cancel,
            on_reject
        )

        while not app_state.logic_loop.is_idle():
            app_state.start_timer()
            app_state.run_logic_loop()

        self.assertEqual(len(app_state.mod_states), 1)
        self.assertEqual(len(list(app_state.mod_states.values())[0].mod.game_archives), 7)

    def test_load_archives_as_separate_new_mods_dry(self):
        logger.info("test_load_archives_as_separate_new_mods_dry")
        set_data_path("D:/Program Files/Steam/steamapps/common/Helldivers 2/data")

        def on_cancel():
            logger.warning("Task cancel")

        def on_reject(err: BaseException | Exception | None):
            logger.critical(err)

        game_archives = [
            "2e24ba9dd702da5c",
            "e75f556a740e00c9",
            "8f295b4d04c3a06c",
            "94b554570b12c088",
            "a66d7cf238070ca7",
            "bf2250de0b17285c",
            "c024a2e8ae639757",
        ]

        game_archives = [f"{get_data_path()}/{game_archive}" for game_archive in game_archives]

        app_state = AppState()
        app_state.db_conn_config = config_sqlite_conn("database")

        app_state.load_archive_as_separate_new_mods(
            game_archives,
            on_cancel,
            on_reject
        )

        while not app_state.logic_loop.is_idle():
            app_state.start_timer()
            app_state.run_logic_loop()

        self.assertEqual(len(app_state.mod_states), 7)

    def test_load_archives_as_single_new_mod_cancel(self):
        logger.info("test_load_archives_as_single_new_mod_cancel")
        set_data_path("D:/Program Files/Steam/steamapps/common/Helldivers 2/data")

        obj = { "cancel": 0 }

        def on_cancel():
            obj["cancel"] += 1
            logger.warning("Task cancel")

        def on_reject(err: BaseException | Exception | None):
            logger.critical(err)

        game_archives = [
            "2e24ba9dd702da5c",
            "e75f556a740e00c9",
            "8f295b4d04c3a06c",
            "94b554570b12c088",
            "a66d7cf238070ca7",
            "bf2250de0b17285c",
            "c024a2e8ae639757",
        ]

        game_archives = [f"{get_data_path()}/{game_archive}" for game_archive in game_archives]

        app_state = AppState()
        app_state.db_conn_config = config_sqlite_conn("database")

        action = app_state.load_archives_as_single_new_mod(
            game_archives,
            on_cancel,
            on_reject
        )

        while not app_state.logic_loop.is_idle():
            app_state.start_timer()
            app_state.run_logic_loop()
            action.state = State.cancel

        self.assertEqual(len(app_state.mod_states), 0)
        self.assertTrue(obj["cancel"] > 0)

        logger.info(obj["cancel"])

    def test_load_archives_as_single_new_mod_reject(self):
        logger.info("test_load_archives_as_single_new_mod_reject")
        set_data_path("D:/Program Files/Steam/steamapps/common/Helldivers 2/data")

        obj = { "reject": 0 }

        def on_cancel():
            logger.warning("Task cancel")

        def on_reject(err: BaseException | Exception | None):
            obj["reject"] += 1
            logger.critical(err)

        game_archives = [
            "2e24ba9dd702da5c",
            "e75f556a740e00c9",
            "8f295b4d04c3a06c",
            "94b554570b12c088",
            "a66d7cf238070ca7",
            "bf2250de0b17285c",
            "c024a2e8ae639757",
        ]

        game_archives = [f"{get_data_path()}/{game_archive}" for game_archive in game_archives]

        app_state = AppState()
        app_state.db_conn_config = config_sqlite_conn("database")

        action = app_state.load_archives_as_single_new_mod(
            game_archives,
            on_cancel,
            on_reject
        )

        while not app_state.logic_loop.is_idle():
            app_state.start_timer()
            app_state.run_logic_loop()
            action.state = State.reject

        self.assertEqual(len(app_state.mod_states), 0)
        self.assertTrue(obj["reject"] > 0)

        logger.info(obj["reject"])

    def test_load_archive_on_exist_mod(self):
        logger.info("test_load_archives_as_single_new_mod_cancel")
        set_data_path("D:/Program Files/Steam/steamapps/common/Helldivers 2/data")

        def on_cancel():
            logger.warning("Task cancel")

        def on_reject(err: BaseException | Exception | None):
            logger.critical(err)


        game_archives_p1 = [
            "2e24ba9dd702da5c",
            "e75f556a740e00c9",
            "8f295b4d04c3a06c",
        ]

        game_archives_p2 = [
            "94b554570b12c088",
            "a66d7cf238070ca7",
            "bf2250de0b17285c",
            "c024a2e8ae639757",
        ]

        game_archives_p1 = [f"{get_data_path()}/{game_archive}" for game_archive in game_archives_p1]
        game_archives_p2 = [f"{get_data_path()}/{game_archive}" for game_archive in game_archives_p2]

        app_state = AppState()
        app_state.db_conn_config = config_sqlite_conn("database")

        app_state.load_archives_as_single_new_mod(
            game_archives_p1, on_cancel, on_reject
        )

        while not app_state.logic_loop.is_idle():
            app_state.start_timer()
            app_state.run_logic_loop()

        self.assertEqual(len(app_state.mod_states), 1)
        self.assertEqual(len(list(app_state.mod_states.values())[0].mod.game_archives), 3)

        app_state.load_archives_as_single_new_mod
