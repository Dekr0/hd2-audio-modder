import posixpath as xpath
import unittest

import env

from backend.db import SQLiteDatabase, config_sqlite_conn
from core import Mod
from wwise_hierarchy import Sound


class TestRerouteSound(unittest.IsolatedAsyncioTestCase):

    async def test_reroute_sound(self):
        db = SQLiteDatabase(config_sqlite_conn("database"))
        mod = Mod("", db)
        mod.load_archive_file(
            xpath.join(env.get_data_path(), "8f295b4d04c3a06c")
        )

        self.assertEqual(len(mod.wwise_banks), 1)

        bank = list(mod.wwise_banks.values())[0]

        hirc = bank.hierarchy

        assert(hirc)

        entries = hirc.entries

        kick_sounds: list[Sound] = []
        for entry in entries.values():
            if isinstance(entry, Sound):
                assert(entry.baseParam)
                if entry.baseParam.directParentID == 348348206:
                    kick_sounds.append(entry)

        self.assertEqual(len(kick_sounds), 13)

        new_audio_sources: list[str] = [
            "D:/sfx/MG/lmg/m105/squad_m249/core_01.wav",
            "D:/sfx/MG/lmg/m105/squad_m249/core_02.wav",
            "D:/sfx/MG/lmg/m105/squad_m249/core_03.wav",
            "D:/sfx/MG/lmg/m105/squad_m249/core_04.wav",
            "D:/sfx/MG/lmg/m105/squad_m249/core_05.wav",
            "D:/sfx/MG/lmg/m105/squad_m249/core_06.wav",
            "D:/sfx/MG/lmg/m105/squad_m249/core_07.wav",
            "D:/sfx/MG/lmg/m105/squad_m249/core_08.wav",
            "D:/sfx/MG/lmg/m105/squad_m249/core_09.wav",
            "D:/sfx/MG/lmg/m105/squad_m249/core_10.wav",
            "D:/sfx/MG/lmg/m105/squad_m249/core_11.wav",
            "D:/sfx/MG/lmg/m105/squad_m249/core_12.wav",
            "D:/sfx/MG/lmg/m105/squad_m249/core_13.wav"
        ]

        pairs = {
            new_audio_sources[i]: [kick_sounds[i]] for i in range(len(kick_sounds))
        }

        await mod.reroute_sound_wav(pairs)

        mod.write_patch("C:/Users/Dekr0/Desktop/")
