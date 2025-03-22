import os
import posixpath as xpath
import unittest
import uuid

from backend import mediautil
from util import fnv_30

from const import CONVERSION_SETTING_MAX
from fileutil import to_posix

from env import DEFAULT_WWISE_PROJECT, SYSTEM, TMP
from log import logger


class TestMediaUtil(unittest.IsolatedAsyncioTestCase):

    async def test_to_wave_batch(self):
        mp3_files: list[str] = [entry.path for entry in os.scandir("tests/mockup/audio_files/mp3")]
        ogg_files: list[str] = [entry.path for entry in os.scandir("tests/mockup/audio_files/ogg")]
        workspace = xpath.join(TMP, f"{fnv_30(uuid.uuid4().bytes)}")
        os.mkdir(workspace)
        results = await mediautil.to_wave_batch(mp3_files, workspace)
        for result in results:
            self.assertEqual(result[2], 0)
        results = await mediautil.to_wave_batch(ogg_files, workspace)
        for result in results:
            self.assertEqual(result[2], 0)

    async def test_wwise_project_migration(self):
        self.assertEqual(
            await mediautil.wwise_project_migration(DEFAULT_WWISE_PROJECT), 
            0
        )

    async def test_convert_wav_to_wem(self):
        workspace = xpath.join(TMP, f"{fnv_30(uuid.uuid4().bytes)}")
        os.mkdir(workspace)

        waves: list[str] = [
            to_posix(os.path.abspath(entry.path)) 
            for entry in os.scandir("tests/mockup/audio_files/wave")
        ]

        convert_dest = await mediautil.convert_wav_to_wem(
            waves, workspace, DEFAULT_WWISE_PROJECT, CONVERSION_SETTING_MAX
        )

        self.assertEqual(convert_dest, xpath.join(workspace, SYSTEM))
        wems: list[str] = [
            xpath.join(convert_dest, entry.name).replace(".wav", ".wem") # type: ignore
            for entry in os.scandir("tests/mockup/audio_files/wave")
        ]
        for wem in wems:
            self.assertTrue(os.path.exists(wem))

    async def test_convert_mp3_to_wem(self):
        mp3_files: list[str] = [entry.path for entry in os.scandir("tests/mockup/audio_files/mp3")]

        mp3_to_wav_workspace = xpath.join(TMP, f"{fnv_30(uuid.uuid4().bytes)}")
        os.mkdir(mp3_to_wav_workspace)

        results = await mediautil.to_wave_batch(mp3_files, mp3_to_wav_workspace)

        waves: list[str] = []
        for result in results:
            self.assertEqual(result[2], 0)
            self.assertTrue(os.path.exists(result[1]))
            waves.append(result[1])

        wav_to_wem_workspace = xpath.join(TMP, f"{fnv_30(uuid.uuid4().bytes)}")
        os.mkdir(wav_to_wem_workspace)

        convert_dest = await mediautil.convert_wav_to_wem(
            waves, wav_to_wem_workspace, DEFAULT_WWISE_PROJECT, CONVERSION_SETTING_MAX
        )

        self.assertEqual(convert_dest, xpath.join(wav_to_wem_workspace, SYSTEM))
        wems: list[str] = [
            xpath.join(convert_dest, xpath.basename(wave)).replace(".wav", ".wem") # type: ignore
            for wave in waves
        ]
        for wem in wems:
            self.assertTrue(os.path.exists(wem))

    async def test_convert_ogg_to_wem(self):
        ogg_files: list[str] = [entry.path for entry in os.scandir("tests/mockup/audio_files/ogg")]

        ogg_to_wav_workspace = xpath.join(TMP, f"{fnv_30(uuid.uuid4().bytes)}")
        os.mkdir(ogg_to_wav_workspace)

        results = await mediautil.to_wave_batch(ogg_files, ogg_to_wav_workspace)

        waves: list[str] = []
        for result in results:
            self.assertEqual(result[2], 0)
            self.assertTrue(os.path.exists(result[1]))
            waves.append(result[1])

        wav_to_wem_workspace = xpath.join(TMP, f"{fnv_30(uuid.uuid4().bytes)}")
        os.mkdir(wav_to_wem_workspace)

        convert_dest = await mediautil.convert_wav_to_wem(
            waves, wav_to_wem_workspace, DEFAULT_WWISE_PROJECT, CONVERSION_SETTING_MAX
        )

        self.assertEqual(convert_dest, xpath.join(wav_to_wem_workspace, SYSTEM))
        wems: list[str] = [
            xpath.join(convert_dest, xpath.basename(wave)).replace(".wav", ".wem") # type: ignore
            for wave in waves
        ]
        for wem in wems:
            self.assertTrue(os.path.exists(wem))

    async def test_get_wem_length(self):
        wems: list[str] = [entry.path for entry in os.scandir("tests/mockup/audio_files/wem")]
        for wem in wems:
            sync = mediautil.get_wem_length_sync(wem)
            asyn = await mediautil.get_wem_length(wem)
            logger.info(f"Expect: {sync}. Received: {asyn}")
            self.assertEqual(sync, asyn)
