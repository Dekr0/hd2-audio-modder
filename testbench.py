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
# from tests.mediautil_test import TestMediaUtil
# from tests.mod_test import TestMod


if __name__ == "__main__":
    os.mkdir(TMP)
    unittest.main()
    shutil.rmtree(TMP)
