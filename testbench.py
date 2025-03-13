import os
import shutil
import unittest

from env import TMP

# from tests.actor_mixer_test import TestActorMixerParser
# from tests.sound_parser_test import TestSoundParser
# from tests.cntr_parser_test import TestCntrParser
from tests.parser_integration_test import TestParserIntegration
# from tests.switch_container_parser_test import TestSwitchContainerParser
# from tests.source_id_gen_test import TestSourceIDGen
# from tests.event_parser_test import TestEventParser
# from tests.action_parser_test import TestActionParser
# from tests.mediautil_test import TestMediaUtil
# from tests.mod_test import TestMod
# from tests.sound_handler_test import TestSoundHandler
# from tests.patch_automate_schema_test import TestPatchAutomateSchema
# from tests.target_import_schema_test import TestTargetImportSchema
# from tests.target_import_automate_test import TargetImportAutomateTest
# from tests.patch_automate_task_test import TestPatchAutomation
from tests.reroute_sound_test import TestRerouteSound


if __name__ == "__main__":
    if os.path.exists(TMP):
        shutil.rmtree(TMP)
    os.mkdir(TMP)
    unittest.main()
