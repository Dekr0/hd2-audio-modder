import shutil
import unittest

from audio_modder import AudioSource, FileHandler
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
                     ("test_mockup_audio_ak47_sup_mw_bolt_forward_01.wav.wem", [949543845]),
                     ("test_mockup_audio_ak47_sup_mw_bolt_forward_02.wav.wem", [540578400]),
                     ("test_mockup_audio_ak47_sup_mw_bolt_forward_03.wav.wem", [1004439290]),
                     ("test_mockup_audio_ak47_sup_mw_bolt_back_01.wav.wem", [224957304]),
                     ("test_mockup_audio_ak47_sup_mw_bolt_back_02.wav.wem", [113945009]),
                     ("test_mockup_audio_ak47_sup_mw_bolt_back_03.wav.wem", [510284008])
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
                     ("test_mockup_audio_ak47_sup_mw_bolt_forward_01.wav.wem", [949543845]),
                     ("test_mockup_audio_ak47_sup_mw_bolt_forward_02.wav.wem", [540578400]),
                     ("test_mockup_audio_ak47_sup_mw_bolt_forward_03.wav.wem", [1004439290]),
                     ("test_mockup_audio_ak47_sup_mw_bolt_back_01.wav.wem", [224957304]),
                     ("test_mockup_audio_ak47_sup_mw_bolt_back_02.wav.wem", [113945009]),
                     ("test_mockup_audio_ak47_sup_mw_bolt_back_03.wav.wem", [510284008]),
                     ("test_mockup_audio_81mm_mortar_fire_bass_01.wav.wem", [872092613, 836761035]),
                     ("test_mockup_audio_81mm_mortar_fire_bass_02.wav.wem", [947154282, 41500478]),
                     ("test_mockup_audio_81mm_mortar_fire_bass_03.wav.wem", [81887028, 542512334]),
                     ("test_mockup_audio_81mm_mortar_fire_bass_04.wav.wem", [101340640, 558443132]),
                     ("test_mockup_audio_senator_mw_deagle_tail_distance_01_01.wav.wem", [572874295]),
                     ("test_mockup_audio_senator_mw_deagle_tail_distance_01_02.wav.wem", [481985023]),
                     ("test_mockup_audio_senator_mw_deagle_tail_distance_01_03.wav.wem", [612881130]),
                     ("test_mockup_audio_senator_mw_deagle_tail_distance_01_04.wav.wem", [486534632]),
                     ("test_mockup_audio_senator_mw_deagle_tail_distance_01_05.wav.wem", [591778201]),
                     ("test_mockup_audio_senator_mw_deagle_tail_distance_01_06.wav.wem", [225694475]),
                     ("test_mockup_audio_senator_mw_deagle_tail_distance_01_07.wav.wem", [120634926]),
                ]
            )
        ]

        for test_case in test_cases:
            pairs, _ = handler.create_conversion_listing(test_case[0])
            for pair in pairs:
                pair_with_id = (pair[0], [i.get_id() for i in pair[1]])
                self.assertIn(pair_with_id, test_case[1])

    def test_target_import_automate_csv_validation(self):
        handler = FileHandler()
        handler.load_archive_file(
                archive_file="test_mockup/archive_files/ea6967f8565a2d76")

        test_cases = [
            [ "audio/amr/sandstorm/shell_eject_01", "1", "407310262" ],
            [ "audio/amr/sandstorm/shell_eject_02", "1", "276231232" ],
            [ "audio/amr/sandstorm/shell_eject_03", "2", "760146779", "276231232" ],
            [ "audio/amr/sandstorm/shell_eject_04", "1", "989834962" ],
            [ "audio/amr/sandstorm/shell_eject_05", "2", "596132438", "989834962" ],
            [ "audio/amr/sandstorm/transient_kick_01", "1", "171011462" ],
            [ "audio/amr/sandstorm/transient_kick_02", "1", "678196601" ],
            [ "audio/amr/sandstorm/transient_kick_03", "1", "305807060" ],
            [ "audio/amr/sandstorm/transient_kick_04", "1", "553167497" ],
            [ "audio/amr/sandstorm/transient_kick_05", "1", "1014728585" ],
            [ "audio/amr/sandstorm/transient_npc_01", "1", "458926136" ],
            [ "audio/amr/sandstorm/transient_npc_02", "1", "563092254" ],
            [ "audio/amr/sandstorm/transient_npc_03", "1", "1043464505" ],
            [ "audio/amr/sandstorm/transient_npc_04", "1", "207681903" ],
            [ "audio/amr/sandstorm/transient_npc_05", "1", "837221041" ],
            [ "audio/amr/sandstorm/exp_tail_01", "1", "1038831131" ],
            [ "audio/amr/sandstorm/exp_tail_02", "1", "1012273532" ],
            [ "audio/amr/sandstorm/exp_tail_03", "2", "442730921", "1012273532" ],
            [ "audio/amr/sandstorm/exp_tail_04", "1", "400408848" ],
            [ "audio/amr/sandstorm/exp_tail_05", "1", "900395835" ]
        ]

        match_cases = [(
            std_path(os.path.abspath(f"test_mockup/{test_case[0]}.wav")), 
            list([handler.get_audio_by_id(int(sid)) for sid in test_case[2:]])) 
            for test_case in test_cases]

        for i, test_case in enumerate(test_cases):
            pairs = handler.validate_target_import_csv_row(
                    std_path(os.path.abspath("test_mockup")), test_case)
            self.assertEqual(match_cases[i], pairs)

    def test_target_import_automate_csv_validation_fail(self):
        handler = FileHandler()
        handler.load_archive_file(
                archive_file="test_mockup/archive_files/ea6967f8565a2d76")
        test_cases = [
            # Less than two columns
            ([ ], SyntaxError),

            # Columns miss match
            ([ "audio/amr/sandstorm/shell_eject_01", "1" ], ValueError),

            # Non integer 
            ([ "audio/amr/sandstorm/shell_eject_01", "1", "abc" ], ValueError),

            # Columns miss match
            ([ "audio/amr/sandstorm/shell_eject_01", "2", "123", "345" ], ValueError),

            # No physical audio source
            ([ "audio/amr/sandstorm/shell_eject_01", "123" ], ValueError),  

            # Source does not exist 
            ([ "audio/amr/shell_eject_01", "123" ], OSError),  
        ]

        for test_case in test_cases:
            self.assertRaises(
                test_case[1],
                lambda: handler.validate_target_import_csv_row("test_mockup", test_case[0])
            )
            
    def test_target_import_create_conversion_listing_csv(self):
        handler = FileHandler()
        handler.load_archive_file(
                archive_file="test_mockup/archive_files/ea6967f8565a2d76")

        test_cases = [
            [ "audio/amr/sandstorm/shell_eject_01", "1", "407310262" ],
            [ "audio/amr/sandstorm/shell_eject_02", "1", "276231232" ],
            [ "audio/amr/sandstorm/shell_eject_03", "2", "760146779", "276231232" ],
            [ "audio/amr/sandstorm/shell_eject_04", "1", "989834962" ],
            [ "audio/amr/sandstorm/shell_eject_05", "2", "596132438", "989834962" ],
            [ "audio/amr/sandstorm/transient_kick_01", "1", "171011462" ],
            [ "audio/amr/sandstorm/transient_kick_02", "1", "678196601" ],
            [ "audio/amr/sandstorm/transient_kick_03", "1", "305807060" ],
            [ "audio/amr/sandstorm/transient_kick_04", "1", "553167497" ],
            [ "audio/amr/sandstorm/transient_kick_05", "1", "1014728585" ],
            [ "audio/amr/sandstorm/transient_npc_01", "1", "458926136" ],
            [ "audio/amr/sandstorm/transient_npc_02", "1", "563092254" ],
            [ "audio/amr/sandstorm/transient_npc_03", "1", "1043464505" ],
            [ "audio/amr/sandstorm/transient_npc_04", "1", "207681903" ],
            [ "audio/amr/sandstorm/transient_npc_05", "1", "837221041" ],
            [ "audio/amr/sandstorm/exp_tail_01", "1", "1038831131" ],
            [ "audio/amr/sandstorm/exp_tail_02", "1", "1012273532" ],
            [ "audio/amr/sandstorm/exp_tail_03", "2", "442730921", "1012273532" ],
            [ "audio/amr/sandstorm/exp_tail_04", "1", "400408848" ],
            [ "audio/amr/sandstorm/exp_tail_05", "1", "900395835" ]
        ]

        test_case_pairs: list[tuple[str, list[AudioSource]]] = []
        for test_case in test_cases:
            pairs = handler.validate_target_import_csv_row("test_mockup", test_case)
            self.assertIsNotNone(pairs)
            test_case_pairs.append(pairs) # type: ignore

        test_case_pairs, _ = handler.create_conversion_listing_csv(test_case_pairs)
        for test_case_pair in test_case_pairs:
            logger.info(test_case_pair[0])

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

    async def test_target_import_automate_full_csv(self):
        handler = FileHandler()
        handler.load_archive_file(
                archive_file="test_mockup/archive_files/ea6967f8565a2d76")

        await handler.target_import_automation_csv(
                os.path.abspath("test_mockup/target_import_01.csv"))

if __name__ == "__main__":
    unittest.main()
