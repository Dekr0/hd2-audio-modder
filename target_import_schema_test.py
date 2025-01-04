import unittest

from jsonschema import ValidationError

from jsonschema import validate

from log import logger

from target_import_schema import \
        revert_schema, manifest_schema, target_import_pair_schema, \
        target_import_schema, task_schema


class TestTargetImportSchema(unittest.TestCase):

    def test_revert_all_ok(self):
        logger.info("Running revert_all_schema validation test (passing)...")
        test_cases = [
            {"before": True, "after": True },
            {"before": True, "after": False },
            {"before": False, "after": True },
            {"before": False, "after": False },
            {"after": True, "before": True },
            {"after": True, "before": False },
            {"after": False, "before": True },
            {"after": False, "before": False },
        ]

        for test_case in test_cases:
            logger.info(f"Validating {test_case}")
            validate(test_case, revert_schema)

    def test_revert_all_fail(self):
        logger.info("Running revert_all_schema validation test (failing)...")
        test_cases = [
            {"after": True, "after": False},
            {"afer": True, "beore": True},
            {"beore": False, "afer": True},
            {"before": 1, "after": 2},
        ]

        for test_case in test_cases:
            logger.info(f"Validating {test_case}")
            self.assertRaises(
                ValidationError, 
                lambda: validate(test_case, revert_schema)
            )

    def test_target_import_pair_schema_ok(self):
        logger.info("Running target_import_schema_pair validation test (passing)...")
        test_cases = [
            { "from": "audio.wav", "to": [123] },
            { "from": "audio.wav", "to": [123, 345] },
            { "to": [900, -123], "from": "vo.wav" },
        ]

        for test_case in test_cases:
            logger.info(f"Validating {test_case}")
            validate(test_case, target_import_pair_schema)

    def test_target_import_pair_schema_fail(self):
        logger.info("Running target_import_schema_pair validation test (failing)...")
        test_cases = [
            # Missing `to`
            { "from": "audio.wav" },

            # `to` has empty array. Why do you want to have an empty array?
            { "from": "audio.wav", "to": [] },

            # `to` has a decimal audio source ID
            { "to": [9.1, 123], "from": "vo.wav" },

            # `from` is a decimal audio source ID
            { "from": 1, "to": [123, 234] },

            # `to` is using string based integer audio source ID
            { "from": "audio.wav", "to": ["123", "234"] },

            # `wrong keyword`
            { "fro": "audio.wav", "too": ["123", "234"] },
        ]

        for test_case in test_cases:
            logger.info(f"Validating {test_case}")
            self.assertRaises(
                ValidationError, 
                lambda: validate(test_case, target_import_pair_schema)
            )

    def test_target_import_schema_ok(self):
        logger.info("Running target_import_schema validation test (passing)...")
        test_cases = [
            {
                "workspace": "..",
                "folders": [],
                "pairs": [
                    { "from": "audio_01.wav", "to": [123] },
                    { "from": "audio_02.wav", "to": [123, 345] },
                ]
            },

            {
                "workspace": "..",
                "folders": [],
                "pairs": [
                    { "to": [8080, 8888], "from": "audio_03.wav" },
                    { "to": [80, 400], "from": "audio_04.wav" },
                ]
            },

            {
                "workspace": "..",
                "folders": [],
                "pairs": [
                    { "to": [8080, 8888], "from": "audio_03.wav" },
                    { "to": [80, 400], "from": "audio_04.wav" },
                ]
            },

            {
                "workspace": "..",
                "folders": [
                    {
                        "workspace": ".",
                        "folders": [],
                        "pairs": [
                            { "from": "audio_01.wav", "to": [45] },
                            { "from": "audio_02.wav", "to": [80, 21] },
                        ]
                    }
                ],
                "pairs": [
                    { "to": [8080, 8888], "from": "audio_03.wav" },
                    { "to": [80, 400], "from": "audio_04.wav" },
                ]
            }
        ]
        for test_case in test_cases:
            logger.info(f"Validating {test_case}")
            validate(test_case, target_import_schema)

    def test_target_import_schema_fail(self):
        logger.info("Running target_import_schema validation test (failing)...")
        test_cases = [
            # Empty pairs. Why do you want to make an array of empty pair?
            {
                "workspace": "..",
                "folders": [],
                "pairs": []
            },

            # Missing folder. Make it an empty array to skip this step 
            {
                "workspace": "..",
                "pairs": []
            },

            # Missing workspace
            {
                "folders": [],
                "pairs": [
                    { "to": [8080, 8888], "from": "audio_03.wav" },
                    { "to": [80, 400], "from": "audio_04.wav" },
                ]
            },

            # Missing workspace in the nested part
            {
                "workspace": "..",
                "folders": [
                    {
                        "folders": [],
                        "pairs": [
                           { "from": "audio_01.wav", "to": [45] },
                           { "from": "audio_02.wav", "to": [80, 21] },
                        ]
                    }
                ],
                "pairs": [
                    { "to": [8080, 8888], "from": "audio_03.wav" },
                    { "to": [80, 400], "from": "audio_04.wav" },
                ]
            },
 
            # One of the pairs contain decimal audio source ID
            {
                "workspace": "..",
                "folders": [],
                "pairs": [
                    { "to": [9.1, 123], "from": "vo.wav" },
                    { "to": [80, 400], "from": "audio_04.wav" },
                ]
            },
 
            # One of the `to` is empty
            {
                "workspace": "..",
                "folders": [
                    {
                        "workspace": ".",
                        "folders": [],
                        "pairs": [
                            { "from": "audio.wav", "to": [] },
                            { "from": "audio_02.wav", "to": [80, 21] },
                        ]
                    }
                ],
                "pairs": [
                    { "to": [8080, 8888], "from": "audio_03.wav" },
                    { "to": [80, 400], "from": "audio_04.wav" },
                ]
            },

            {
                "workspace": "..",
                "folders": [
                    {
                        "workspace": ".",
                        "folders": [
                            {
                                "workspace": "folder_1",
                                "folders": [],
                                "pairs": [] # Cannot be empty
                            }
                        ],
                        "pairs": [
                            { "from": "audio_01.wav", "to": [45] },
                            { "from": "audio_02.wav", "to": [80, 21] },
                        ]
                    }
                ],
                "pairs": [
                    { "to": [8080, 8888], "from": "audio_03.wav" },
                    { "to": [80, 400], "from": "audio_04.wav" },
                ]
            },
        ]
        for test_case in test_cases:
            logger.info(f"Validating {test_case}")
            self.assertRaises(
                ValidationError, 
                lambda: validate(test_case, target_import_schema)
            )

    def test_target_import_task_schema_ok(self):
        logger.info("Running target_import_task_schema validation test (passing)...")
        test_cases = [
            {
                "revert_all": { "before": True, "after": True },
                "write_patch_to": ".",
                "target_imports": [
                    {
                        "workspace": "..",
                        "folders": [],
                        "pairs": [
                            { "from": "audio_01.wav", "to": [123] },
                            { "from": "audio_02.wav", "to": [123, 345] }
                        ]
                    },
                    {
                        "workspace": "..",
                        "folders": [
                            {
                                "workspace": ".",
                                "folders": [],
                                "pairs": [
                                    { "from": "audio_01.wav", "to": [45] },
                                    { "from": "audio_02.wav", "to": [80, 21] },
                                ]
                            }
                        ],
                        "pairs": [
                            { "from": "audio_01.wav", "to": [123] },
                            { "from": "audio_02.wav", "to": [123, 345] }
                        ]
                    }
                ]
            },
        ]

        for test_case in test_cases:
            logger.info(f"Validating {test_case}")
            validate(test_case, task_schema)

    def test_target_import_task_schema_fail(self):
        logger.info("Runing target_import_task_schema validation test (failing)...")
        test_cases = [ 
            # target_imports has an empty array. Why do you want to have an empty
            # of target imports?
            {
                "revert_all": { "before": True, "after": True },
                "write_patch_to": ".",
                "target_imports": []
            },
            # Missing revert all
            {
                "write_patch_to": ".",
                "target_imports": [
                    {
                        "workspace": "..",
                        "folders": [],
                        "pairs": [
                            { "from": "audio_01.wav", "to": [123] },
                            { "from": "audio_02.wav", "to": [123, 345] }
                        ]
                    }
                ]
            },
            # Missing revert all
            {
                "revert_all": { "before": True, "after": True },
                "target_imports": [
                    {
                        "workspace": "..",
                        "folders": [],
                        "pairs": [
                            { "from": "audio_01.wav", "to": [123] },
                            { "from": "audio_02.wav", "to": [123, 345] }
                        ]
                    }
                ]
            }
        ]
        for test_case in test_cases:
            logger.info(f"Validating {test_case}")
            self.assertRaises(
                ValidationError, 
                lambda: validate(test_case, target_import_schema)
            )


    def test_schema_ok(self):
        logger.info("Running schema validation test (passing)...")
        test_cases = [
            {
                "version": 3,
                "tasks": [
                    {
                        "revert_all": { "before": True, "after": True },
                        "write_patch_to": ".",
                        "target_imports": [
                            {
                                "workspace": "..",
                                "folders": [],
                                "pairs": [
                                    { "from": "audio_01.wav", "to": [123] },
                                    { "from": "audio_02.wav", "to": [123, 345] }
                                ]
                            },
                            {
                                "workspace": "..",
                                "folders": [
                                    {
                                        "workspace": ".",
                                        "folders": [],
                                        "pairs": [
                                            { "from": "audio_01.wav", "to": [45] },
                                            { "from": "audio_02.wav", "to": [80, 21] },
                                        ]
                                    }
                                ],
                                "pairs": [
                                    { "from": "audio_01.wav", "to": [123] },
                                    { "from": "audio_02.wav", "to": [123, 345] }
                                ]
                            }
                        ]
                    }                
                ]
            }
        ]
        
        for test_case in test_cases:
            logger.info(f"Validating {test_case}")
            validate(test_case, manifest_schema)

    def test_schema_fail(self):
        logger.info("Running schema validation test (failing)...")
        test_cases = [
            # Wrong version number
            { "version": 1 },
        ]
        for test_case in test_cases:
            logger.info(f"Validating {test_case}")
            self.assertRaises(
                ValidationError, 
                lambda: validate(test_case, target_import_schema)
            )


if __name__ == "__main__":
    unittest.main()
