import os
import unittest

import config as cfg

from audio_modder import FileHandler
from fileutil import std_path
from log import logger


class TestPatchAutomation(unittest.TestCase):

    def test_validate_patch_automation_task(self):
        logger.info("Testing validate patch automation task (passing)...")

        handler = FileHandler()

        test_cases = [
            (
                {
                    "data": "test_mockup/archive_files",
                    "workspace": "test_mockup/target_import_manifest",
                    "archive_files": [
                        "a66d7cf238070ca7"
                    ],
                    "using": [
                        "adjudicator.json"
                    ]
                },
                FileHandler.PatchAuotmationTask(
                    set([
                        std_path(os.path.abspath("test_mockup/archive_files/a66d7cf238070ca7"))
                    ]),
                    set([
                        std_path(os.path.abspath("test_mockup/target_import_manifest/adjudicator.json"))
                    ])
                )
            )
        ]
        
        for test_case in test_cases:
            safe = handler.validate_task(test_case[0])
            self.assertIsNotNone(safe)
            self.assertEqual(safe, test_case[1])

    def test_validate_patch_automation_task_data(self):
        logger.info("Testing validate patch automation task (using user config)")

        app_state: cfg.Config | None = cfg.load_config()
        if app_state == None:
            raise RuntimeError("(Before test) Failed to load user configuration")

        os.environ["HD2DATA"] = app_state.game_data_path

        handler = FileHandler()

        test_cases = [
            (
                {
                    "workspace": "test_mockup/target_import_manifest",
                    "archive_files": [
                        "a66d7cf238070ca7"
                    ],
                    "using": [
                        "adjudicator.json"
                    ]
                },
                FileHandler.PatchAuotmationTask(
                    set([
                        std_path(os.path.join(os.environ["HD2DATA"], "a66d7cf238070ca7"))
                    ]),
                    set([
                        std_path(os.path.abspath("test_mockup/target_import_manifest/adjudicator.json"))
                    ])
                )
            )
        ]

        for test_case in test_cases:
            safe = handler.validate_task(test_case[0])
            self.assertIsNotNone(safe)
            self.assertEqual(safe, test_case[1])

    def test_validate_patch_automation_task_fail(self):
        logger.info("Testing validate patch automation task (failing)...")

        handler = FileHandler()

        test_cases = [
            {
                "data": "test_mockup/archive_files",
                "workspace": "test_mockup/target_import_manifest",
                "archive_files": [
                    "a66d7cf238070ca7"
                ],
                "using": [
                    "amr.json", "diligence.json"
                ]
            },
            {
                "data": "test_mockup/archive_files",
                "workspace": "test_mockup/target_import_manifest",
                "archive_files": [
                    "a66d7cf238070ca"
                ],
                "using": [
                    "amr.json", "diligence.json"
                ]
            },
            {
                "workspace": "test_mockup/target_import_manifest",
                "archive_files": [
                    "a66d7cf238070ca7"
                ],
                "using": [
                    "amr.json", "diligence.json"
                ]
            }
        ]
        
        for test_case in test_cases:
            safe = handler.validate_task(test_case)
            self.assertIsNone(safe)

    def test_patch_automation(self):
        pass
        # logger.info("Testing validate patch automation task (failing)...")

        # handler = FileHandler()

        # test_cases = [ "test_mockup/patch_import_manifest/test_case_1.json" ]

        # for test_case in test_cases:
        #     handler.patch_automation(test_case)

def test_multithread_patch_automation():
    app_state: cfg.Config | None = cfg.load_config()
    if app_state == None:
        raise RuntimeError("(Before test) Failed to load user configuration")

    os.environ["HD2DATA"] = app_state.game_data_path
    handler = FileHandler()

    test_cases = [ "test_mockup/patch_import_manifest/test_case_2.json" ]

    for test_case in test_cases:
        handler.patch_automation(test_case)


if __name__ == "__main__":
    # unittest.main()
    test_multithread_patch_automation()
