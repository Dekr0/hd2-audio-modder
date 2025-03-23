import os
import posixpath as xpath
import unittest

import env
from core import Mod
from fileutil import to_posix


class TestMediaUtilIntegration(unittest.IsolatedAsyncioTestCase):

    async def test_import_wavs(self):
        """
        This is an example test case.
        Select your own game archive file, your own wave files, and your own 
        import targets.
        """
        mod = Mod("", None) # type: ignore
        await mod.load_archive_file(xpath.join(
            env.get_data_path(), "2c26bc4c6592fa14"
        ))
 
        targets: dict[str, list[int]] = {
            to_posix(os.path.abspath("tests/mockup/audio_files/wave/A10_01.wav")): [
                16210027149246967656, 4098946748609408543, 15531829376206577415
            ]
        }

        errored_files = await mod.import_wavs(targets)

        for error_file in errored_files:
            print(error_file)

        mod.write_patch("tests")
