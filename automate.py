from tests.mockup.py.AC8 import automate as ac8_automate
from tests.mockup.py.AMR import automate as amr_automate
from tests.mockup.py.ART import automate as art_automate
from tests.mockup.py.AR23 import automate as ar23_automate
from tests.mockup.py.AR61 import automate as ar61_automate
from tests.mockup.py.AXAR import automate as axar_automate
from tests.mockup.py.BR14 import automate as br14_automate
from tests.mockup.py.CAS import automate as cas_automate
from tests.mockup.py.EAT import automate as eat_automate
from tests.mockup.py.GL21 import automate as gl21_automate
from tests.mockup.py.GR8 import automate as gr8_automate
from tests.mockup.py.P4 import automate as p4_automate
from tests.mockup.py.RL77 import automate as rl77_automate
from tests.mockup.py.M105 import automate as m105_automate
from tests.mockup.py.M206 import automate as m206_automate
from tests.mockup.py.MG43 import automate as mg43_automate
from tests.mockup.py.R63 import automate as r63_automate
from tests.mockup.py.RS422 import automate as rs422_automate
from tests.mockup.py.P2 import automate as p2_automate
from tests.mockup.py.EXO import automate as exo_automate


# ac8_automate()
# ar61_automate()
# ar23_automate()
# amr_automate()
# axar_automate()
# art_automate()
# br14_automate()
# gl21_automate()
# cas_automate()
# eat_automate()
# gr8_automate()
# m105_automate()
# m206_automate()
# mg43_automate()
# p4_automate()
# r63_automate()
# rl_77_automate()
# rs422_automate()
# p2_automate()
exo_automate()


AkPropID_128 = {
  0x00: "Volume",
  0x01: "LFE",
  0x02: "Pitch",
  0x03: "LPF",
  0x04: "HPF",
  0x05: "BusVolume",
  0x06: "MakeUpGain",
  0x07: "Priority",
  0x08: "PriorityDistanceOffset",
  0x09: "_FeedbackVolume", #removed
  0x0A: "_FeedbackLPF", #removed
  0x0B: "MuteRatio",
  0x0C: "PAN_LR",
  0x0D: "PAN_FR",
  0x0E: "CenterPCT",
  0x0F: "DelayTime",
  0x10: "TransitionTime",
  0x11: "Probability",
  0x12: "DialogueMode",
  0x13: "UserAuxSendVolume0",
  0x14: "UserAuxSendVolume1",
  0x15: "UserAuxSendVolume2",
  0x16: "UserAuxSendVolume3",
  0x17: "GameAuxSendVolume",
  0x18: "OutputBusVolume",
  0x19: "OutputBusHPF",
  0x1A: "OutputBusLPF",
  0x1B: "HDRBusThreshold",
  0x1C: "HDRBusRatio",
  0x1D: "HDRBusReleaseTime",
  0x1E: "HDRBusGameParam",
  0x1F: "HDRBusGameParamMin",
  0x20: "HDRBusGameParamMax",
  0x21: "HDRActiveRange",
  0x22: "LoopStart",
  0x23: "LoopEnd",
  0x24: "TrimInTime",
  0x25: "TrimOutTime",
  0x26: "FadeInTime",
  0x27: "FadeOutTime",
  0x28: "FadeInCurve",
  0x29: "FadeOutCurve",
  0x2A: "LoopCrossfadeDuration",
  0x2B: "CrossfadeUpCurve",
  0x2C: "CrossfadeDownCurve",
  0x2D: "MidiTrackingRootNote",
  0x2E: "MidiPlayOnNoteType",
  0x2F: "MidiTransposition",
  0x30: "MidiVelocityOffset",
  0x31: "MidiKeyRangeMin",
  0x32: "MidiKeyRangeMax",
  0x33: "MidiVelocityRangeMin",
  0x34: "MidiVelocityRangeMax",
  0x35: "MidiChannelMask",
  0x36: "PlaybackSpeed",
  0x37: "MidiTempoSource",
  0x38: "MidiTargetNode",
  0x39: "AttachedPluginFXID",
  0x3A: "Loop",
  0x3B: "InitialDelay",
  0x3C: "UserAuxSendLPF0",
  0x3D: "UserAuxSendLPF1",
  0x3E: "UserAuxSendLPF2",
  0x3F: "UserAuxSendLPF3",
  0x40: "UserAuxSendHPF0",
  0x41: "UserAuxSendHPF1",
  0x42: "UserAuxSendHPF2",
  0x43: "UserAuxSendHPF3",
  0x44: "GameAuxSendLPF",
  0x45: "GameAuxSendHPF",
  0x46: "AttenuationID", #132>=
  0x47: "PositioningTypeBlend", #132>=
  0x48: "ReflectionBusVolume", #135>=
  0x49: "PAN_UD", #140>=
  #0x4A: AkPropID_NUM
}
