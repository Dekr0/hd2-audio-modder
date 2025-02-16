import unittest

from jsonschema import ValidationError
from jsonschema import validate

from backend import patch_automate_schema

from log import logger


class TestPatchAutomateSchema(unittest.TestCase):

    def test_patch_task_schema_ok(self):
        logger.info("Running patch_task_schema test (passing)...")
        test_cases = [
            {
                "archives": [ "123", "234" ],
                "workspace": "",
                "includes": [ "manifest_1.json", "manifest_2.json" ],
                "merge": False,
            },
            {
                "includes": [ "manifest_2.json", "manifest_3.json" ],
                "workspace": "",
                "archives": [ "123" ],
                "merge": True,
            },
            {
                "includes": [ "manifest_3.json" ],
                "workspace": "",
                "archives": [ "123" ],
                "merge": False,
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
                "includes": [ "manifest_3.json" ],
                "archives": [ "123" ],
                "merge": False,
            },
            # Missing includes
            {
                "workspace": "",
                "archives": [ "123" ],
                "merge": False,
            },
            # Empty archive file
            {
                "workspace": "",
                "includes": [ "manifest_2.json", "manifest_3.json" ],
                "archives": [],
                "merge": False,
            },
            # Empty includes 
            {
                "workspace": "",
                "includes": [  ],
                "archives": [ "123" ],
                "merge": False,
            },
            # Missing merge
            {
                "archives": [ "123", "234" ],
                "workspace": "",
                "includes": [ "manifest_1.json", "manifest_2.json" ],
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
                        "archives": [ "123", "234" ],
                        "includes": [ "target_import_manifest_1.json", "target_import_manifest_2.json" ],
                        "merge": False
                    }
                ]
            },
            {
                "version": patch_automate_schema.VERSION,
                "tasks": [
                    {
                        "workspace": "",
                        "includes": [ "manifest_3.json" ],
                        "archives": [ "123" ],
                        "merge": False
                    }
                ]
            },
            {
                "version": patch_automate_schema.VERSION,
                "tasks": [
                    {
                        "includes": [ "manifest_2.json", "manifest_3.json" ],
                        "archives": [ "123" ],
                        "workspace": "",
                        "merge": False
                    },
                ]
            }
        ]

        for test_case in test_cases:
            logger.info(f"Validating {test_case}")
            validate(test_case, patch_automate_schema.manifest_schema)


if __name__ == "__main__":
    unittest.main()
