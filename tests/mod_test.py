import os
import posixpath as xpath
import unittest

from dataclasses import dataclass

import core

from fileutil import to_posix
from env import get_data_path, TMP
from log import logger


@dataclass
class MockUp:

    archive_name: str
    targets: dict[str, list[int]]


class TestMod(unittest.IsolatedAsyncioTestCase):

    async def test_import_wem_async(self):
        wem_dir = "tests/mockup/audio_files/wem"
 
        logger.info("Running test_import_wem...")

        # Add your own test cases
        test_cases = []
 
        for test_case in test_cases:
            mod = core.Mod(test_case.archive_name)
            mod.load_archive_file(xpath.join(get_data_path(), test_case.archive_name))
 
            await mod.import_wems_async(test_case.targets)
 
            mod.write_patch(TMP, False)
 
        logger.info("Please open UI to verifiy the final result for `test_import_wem`")
 
    async def test_import_wav_async(self):
         wave_dir = to_posix(os.path.abspath("tests/mockup/audio_files/wave"))
 
         logger.info("Running test_import_wav...")

         # Added your own test cases
         test_cases = []
 
         for test_case in test_cases:
             mod = core.Mod("test_import_wave")
             mod.load_archive_file(xpath.join(get_data_path(), test_case.archive_name))
 
             await mod.import_wavs_async(test_case.targets)
 
             mod.write_patch(TMP, overwrite = False)
 
         logger.info("Please open UI to verifiy the final result for `test_import_wav`")

    async def test_import_files_async(self):
        wave_dir = to_posix(os.path.abspath("tests/mockup/audio_files/wave"))
        wem_dir = to_posix(os.path.abspath("tests/mockup/audio_files/wem"))
        ogg_dir = to_posix(os.path.abspath("tests/mockup/audio_files/ogg"))
        logger.info("Runing test_import_files_async")

        mod = core.Mod("test_import_files_async")
        mod.load_archive_file(xpath.join(get_data_path(), "2c26bc4c6592fa14"))
        mod.load_archive_file(xpath.join(get_data_path(), "a66d7cf238070ca7"))

        # Add your own test cases
        targets: dict[str, list[int]] = {}

        await mod.import_files_async(targets)

        mod.write_patch(TMP, overwrite = False)
        
        logger.info("Please open UI to verifiy the final result for `test_import_wav`")

    async def test_write_patch_async(self):
        wave_dir = to_posix(os.path.abspath("tests/mockup/audio_files/wave"))
 
        logger.info("Runing test_import_wav")

        # Add your own test cases
        test_cases = []
 
        for test_case in test_cases:
            mod = core.Mod("test_import_wave")
            mod.load_archive_file(xpath.join(get_data_path(), test_case.archive_name))
 
            await mod.import_wavs_async(test_case.targets)
            await mod.write_patch_async(TMP, overwrite = False)
 
        logger.info("Please open UI to verifiy the final result for `test_import_wav`")
