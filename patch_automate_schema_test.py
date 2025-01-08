import unittest

from jsonschema import ValidationError
from jsonschema import validate

import patch_automate_schema

from log import logger


class TestPatchAutomateSchema(unittest.TestCase):

    def test_patch_task_schema_ok(self):
        logger.info("Running patch_task_schema test (passing)...")
        test_cases = [
            {
                "archive_files": [ "123", "234" ],
                "workspace": "",
                "using": [ "manifest_1.json", "manifest_2.json" ]
            },
            {
                "using": [ "manifest_2.json", "manifest_3.json" ],
                "workspace": "",
                "archive_files": [ "123" ]
            },
            {
                "using": [ "manifest_3.json" ],
                "workspace": "",
                "archive_files": [ "123" ]
            }
        ]
        for test_case in test_cases:
            logger.info(f"Validating {test_case}")
            validate(test_case, patch_automate_schema.task)

    def test_patch_task_schema_fail(self):
        logger.info("Running patch_task_schema test (passing)...")
        test_cases = [
            # Missing workspace
            {
                "using": [ "manifest_3.json" ],
                "archive_files": [ "123" ]
            },
            # Missing using
            {
                "workspace": "",
                "archive_files": [ "123" ]
            },
            # Empty archive file
            {
                "workspace": "",
                "using": [ "manifest_2.json", "manifest_3.json" ],
                "archive_files": []
            },
            # Empty using 
            {
                "workspace": "",
                "using": [  ],
                "archive_files": [ "123" ]
            },
        ]
        for test_case in test_cases:
            logger.info(f"Validating {test_case}")
            self.assertRaises(
                ValidationError,
                lambda: validate(test_case, patch_automate_schema.task)
            )

    def test_patch_manifest_schema_ok(self):
        logger.info("Running patch_manifest_schema test (passing)...")
        test_cases = [
            {
                "version": patch_automate_schema.VERSION,
                "tasks": [
                    {
                        "workspace": "",
                        "archive_files": [ "123", "234" ],
                        "using": [ "target_import_manifest_1.json", "target_import_manifest_2.json" ]
                    }
                ]
            },
            {
                "version": patch_automate_schema.VERSION,
                "tasks": [
                    {
                        "workspace": "",
                        "using": [ "manifest_3.json" ],
                        "archive_files": [ "123" ]
                    }
                ]
            },
            {
                "version": patch_automate_schema.VERSION,
                "tasks": [
                    {
                        "using": [ "manifest_2.json", "manifest_3.json" ],
                        "archive_files": [ "123" ],
                        "workspace": ""
                    },
                ]
            }
        ]

        for test_case in test_cases:
            logger.info(f"Validating {test_case}")
            validate(test_case, patch_automate_schema.manifest_schema)


if __name__ == "__main__":
    unittest.main()
