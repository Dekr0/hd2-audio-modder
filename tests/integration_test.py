import os
import struct
import time
import posixpath as xpath
import unittest

import env
import core
from fileutil import to_posix


patch_file_name = "9ba626afa44a3aa3.patch_0"


class TestIntegration(unittest.IsolatedAsyncioTestCase):
    """
    Please select own input for each unit test. The followings are only example
    """

    async def _test_hierarchy_data_import(self):
        mod = core.Mod("", None) # type: ignore
        await mod.load_archive_file(xpath.join(env.get_data_path(), "de96cd7cc69628bc"))

        await mod.import_wavs({
            to_posix(os.path.abspath("tests/mockup/template_patches/EAT/core_03.wav")): 
            [
                350171671,462238529,657113547,936725363,607612623,827383878
            ]
        })

        mod.import_patch(f"tests/mockup/template_patches/EAT/{patch_file_name}")

        bank = list(mod.wwise_banks.values())
        self.assertEqual(len(bank), 1)

        hirc = bank[0].hierarchy
        self.assertIsNotNone(hirc)

        core_layer = hirc.get_layer_container_by_id(367240026) # type: ignore
        p = core_layer.get_base_param().propBundle

        self.assertIn(6, p.pIDs)
        self.assertIn(59, p.pIDs)
        
        for i in range(p.cProps):
            if p.pIDs[i] == 6:
                v: float = struct.unpack("<f", p.pValues[i])[0]
                self.assertAlmostEqual(v, 1.6)
            elif p.pIDs == 59:
                v: float = struct.unpack("<f", p.pValues[i])[0]
                self.assertAlmostEqual(v, 0.058)

        mod.write_patch(f"tests/mockup/template_patches/EAT/result")

    async def _test_state_desync(self):
        archives = [
            "9bc33b7058a2bd5a",
            "1e33cc1600ff38f3",
            "de456f55554abb56",
            "f70996775c6430a9",
            "2c26bc4c6592fa14",
            "23bb68bd2e366fdf",
            "bfe4d006cc25a01e",
        ]
        for archive in archives:
            arc = core.GameArchive.from_file(xpath.join(env.get_data_path(), archive))
            for bank in arc.wwise_banks.values():
                hirc = bank.hierarchy
                assert(hirc != None)
                a = len(hirc.actions) + \
                    len(hirc.actor_mixers) + \
                    len(hirc.events) + \
                    len(hirc.layer_container) + \
                    len(hirc.music_segments) + \
                    len(hirc.music_tracks) + \
                    len(hirc.random_sequence_containers) + \
                    len(hirc.sounds) + \
                    len(hirc.switch_containers) + \
                    len(hirc.uncategorized)
                print(a, len(hirc.entries))
                self.assertEqual(a, len(hirc.entries))

    async def test_actor_mixer_merging(self):
        mod = core.Mod("", None) # type: ignore

        await mod.load_archive_file(xpath.join(env.get_data_path(), "9bc33b7058a2bd5a"))
        await mod.load_archive_file(xpath.join(env.get_data_path(), "1e33cc1600ff38f3"))
        await mod.load_archive_file(xpath.join(env.get_data_path(), "de456f55554abb56"))
        await mod.load_archive_file(xpath.join(env.get_data_path(), "2c26bc4c6592fa14"))
        await mod.load_archive_file(xpath.join(env.get_data_path(), "23bb68bd2e366fdf"))
        await mod.load_archive_file(xpath.join(env.get_data_path(), "bfe4d006cc25a01e"))

        mod.import_patch(f"tests/mockup/template_patches/CAS/{patch_file_name}")

        for bank in mod.wwise_banks.values():
            hirc = bank.hierarchy
            assert(hirc)
            engine_mixer = hirc.get_actor_mixer_by_id(644177938)
            p = engine_mixer.get_base_param().propBundle
            self.assertIn(6, p.pIDs)
            self.assertIn(7, p.pIDs)
            for i in range(p.cProps):
                if p.pIDs[i] == 6:
                    decimal: float = struct.unpack("<f", p.pValues[i])[0]
                    self.assertAlmostEqual(decimal, 9.6, delta=0.001)
                elif p.pIDs[i] == 7:
                    decimal: float = struct.unpack("<f", p.pValues[i])[0]
                    self.assertAlmostEqual(decimal, 95.0, delta=0.001)
