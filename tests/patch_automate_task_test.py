import os
import unittest

import patch_automation


class TestPatchAutomation(unittest.TestCase):

    def test_patch_automation(self):
        manifests: list[str] = [entry.path for entry in os.scandir("tests/mockup/patch_includes")]
        for manifest in manifests:
            patch_automation.patch_automation(manifest)
