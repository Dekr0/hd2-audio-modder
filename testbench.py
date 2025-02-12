import os
import shutil
import unittest

from env import TMP
# from tests.mediautil_test import TestMediaUtil
# from tests.mod_test import TestMod
# from tests.sound_handler_test import TestSoundHandler
# from tests.patch_automate_schema_test import TestPatchAutomateSchema
# from tests.target_import_schema_test import TestTargetImportSchema
from tests.target_import_automate_test import TargetImportAutomateTest
# from tests.patch_automate_task_test import TestPatchAutomation


if __name__ == "__main__":
    if os.path.exists(TMP):
        shutil.rmtree(TMP)
    os.mkdir(TMP)
    unittest.main()
