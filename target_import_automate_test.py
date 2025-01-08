import shutil
import unittest

from audio_modder import FileHandler
from env import *


class TargetImportAutomateTest(unittest.TestCase):

    def test_create_conversion_setting(self):
        handler = FileHandler()
        handler.load_archive_file(
                archive_file="test_mockup/archive_files/a66d7cf238070ca7")

        test_cases = [
            (
                [
                    {
                        "workspace": "test_mockup/audio/ak47_sup_mw",
                        "folders": [],
                        "pairs": [
                            { "from": "bolt_forward_01", "to": [949543845] },
                            { "from": "bolt_forward_02", "to": [540578400] },
                            { "from": "bolt_forward_03", "to": [1004439290] },
                            { "from": "bolt_back_01", "to": [224957304] },
                            { "from": "bolt_back_02", "to": [113945009] },
                            { "from": "bolt_back_03", "to": [510284008] }
                        ]
                    }
                ],
                [
                     ("test_mockup_audio_ak47_sup_mw_bolt_forward_01.wem", [949543845]),
                     ("test_mockup_audio_ak47_sup_mw_bolt_forward_02.wem", [540578400]),
                     ("test_mockup_audio_ak47_sup_mw_bolt_forward_03.wem", [1004439290]),
                     ("test_mockup_audio_ak47_sup_mw_bolt_back_01.wem", [224957304]),
                     ("test_mockup_audio_ak47_sup_mw_bolt_back_02.wem", [113945009]),
                     ("test_mockup_audio_ak47_sup_mw_bolt_back_03.wem", [510284008])
                ]
            ),
            (
                [
                    {
                        "workspace": "test_mockup",
                        "folders": [
                            {
                                "workspace": "audio/81mm",
                                "folders": [],
                                "pairs": [
                                    { "from": "mortar_fire_bass_01.wav", "to": [872092613, 836761035] },
                                    { "from": "mortar_fire_bass_02.wav", "to": [947154282, 41500478] },
                                    { "from": "mortar_fire_bass_03.wav", "to": [81887028, 542512334] },
                                    { "from": "mortar_fire_bass_04.wav", "to": [101340640, 558443132] }
                                ]
                            },
                            {
                                "workspace": "audio/senator/mw_deagle",
                                "folders": [],
                                "pairs": [
                                    { "from": "tail_distance_01_01.wav", "to": [572874295] },
                                    { "from": "tail_distance_01_02.wav", "to": [481985023] },
                                    { "from": "tail_distance_01_03.wav", "to": [612881130] },
                                    { "from": "tail_distance_01_04.wav", "to": [486534632] },
                                    { "from": "tail_distance_01_05.wav", "to": [591778201] },
                                    { "from": "tail_distance_01_06.wav", "to": [225694475] },
                                    { "from": "tail_distance_01_07.wav", "to": [120634926] },
                                ]
                            },
                            {
                                "workspace": "audio/ak47_sup_mw",
                                "folders": [],
                                "pairs": [
                                    { "from": "bolt_forward_01", "to": [949543845] },
                                    { "from": "bolt_forward_02", "to": [540578400] },
                                    { "from": "bolt_forward_03", "to": [1004439290] },
                                    { "from": "bolt_back_01", "to": [224957304] },
                                    { "from": "bolt_back_02", "to": [113945009] },
                                    { "from": "bolt_back_03", "to": [510284008] }
                                ]
                            }
                        ],
                        "pairs": [
                        ]
                    }
                ],
                [
                     ("test_mockup_audio_ak47_sup_mw_bolt_forward_01.wem", [949543845]),
                     ("test_mockup_audio_ak47_sup_mw_bolt_forward_02.wem", [540578400]),
                     ("test_mockup_audio_ak47_sup_mw_bolt_forward_03.wem", [1004439290]),
                     ("test_mockup_audio_ak47_sup_mw_bolt_back_01.wem", [224957304]),
                     ("test_mockup_audio_ak47_sup_mw_bolt_back_02.wem", [113945009]),
                     ("test_mockup_audio_ak47_sup_mw_bolt_back_03.wem", [510284008]),
                     ("test_mockup_audio_81mm_mortar_fire_bass_01.wem", [872092613, 836761035]),
                     ("test_mockup_audio_81mm_mortar_fire_bass_02.wem", [947154282, 41500478]),
                     ("test_mockup_audio_81mm_mortar_fire_bass_03.wem", [81887028, 542512334]),
                     ("test_mockup_audio_81mm_mortar_fire_bass_04.wem", [101340640, 558443132]),
                     ("test_mockup_audio_senator_mw_deagle_tail_distance_01_01.wem", [572874295]),
                     ("test_mockup_audio_senator_mw_deagle_tail_distance_01_02.wem", [481985023]),
                     ("test_mockup_audio_senator_mw_deagle_tail_distance_01_03.wem", [612881130]),
                     ("test_mockup_audio_senator_mw_deagle_tail_distance_01_04.wem", [486534632]),
                     ("test_mockup_audio_senator_mw_deagle_tail_distance_01_05.wem", [591778201]),
                     ("test_mockup_audio_senator_mw_deagle_tail_distance_01_06.wem", [225694475]),
                     ("test_mockup_audio_senator_mw_deagle_tail_distance_01_07.wem", [120634926]),
                ]
            )
        ]

        for test_case in test_cases:
            pairs, _ = handler.create_conversion_listing(test_case[0])
            for pair in pairs:
                pair_with_id = (pair[0], [i.get_id() for i in pair[1]])
                self.assertIn(pair_with_id, test_case[1])


class TargetImportAutomateTestAsync(unittest.IsolatedAsyncioTestCase):

    async def test_target_import_automate_conversion(self):
        handler = FileHandler()
        handler.load_archive_file(
                archive_file="test_mockup/archive_files/a66d7cf238070ca7")

        test_cases = [
            {
                "revert_all": { "before": True, "after": True },
                "write_patch_to": ".",
                "target_imports": [
                    {
                        "workspace": "test_mockup/audio/ak47_sup_mw",
                        "folders": [],
                        "pairs": [
                            { "from": "bolt_forward_01", "to": [949543845] },
                            { "from": "bolt_forward_02", "to": [540578400] },
                            { "from": "bolt_forward_03", "to": [1004439290] },
                            { "from": "bolt_back_01", "to": [224957304] },
                            { "from": "bolt_back_02", "to": [113945009] },
                            { "from": "bolt_back_03", "to": [510284008] }
                        ]
                    }
                ]
            }
        ]

        for test_case in test_cases:
            pairs, schema = handler.create_conversion_listing(test_case["target_imports"])
            tmp_dest = await handler.convert_wav_to_wem(DEFAULT_WWISE_PROJECT,
                                                        schema)
            tmp_dest = os.path.join(tmp_dest, SYSTEM)
            wem_source_pairs = [(os.path.join(tmp_dest, pair[0]), pair[1])
                                 for pair in pairs]

            for wem_source_pair in wem_source_pairs:
                self.assertTrue(os.path.exists(wem_source_pair[0]))

            try:
                shutil.rmtree(tmp_dest)
            except OSError as err:
                logger.warning("Failed to remove temporary staging point for "
                               f"wave files to wem files conversion. Trace: {err}")

    async def test_target_import_automate_full(self):
        handler = FileHandler()
        handler.load_archive_file(
                archive_file="test_mockup/archive_files/a66d7cf238070ca7")

        await handler.target_import_automation(
            "test_mockup/target_import_manifest/adjudicator.json"
        )


if __name__ == "__main__":
    unittest.main()
