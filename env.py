import os
import pathlib
import platform
import sys

from fileutil import std_path
import one_shot_ui

from log import logger

DIR = std_path(os.path.dirname(__file__))
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    DIR = os.path.dirname(sys.argv[0])

CACHE = os.path.join(DIR, ".cache")
TMP = os.path.join(DIR, ".tmp")

DEFAULT_WWISE_PROJECT = os.path.join(
    DIR, "AudioConversionTemplate/AudioConversionTemplate.wproj")

SYSTEM = platform.system()

FFMPEG = ""
VGMSTREAM = ""
WWISE_CLI = ""
WWISE_VERSION = ""

match SYSTEM:
    case "Windows":
        FFMPEG = "ffmpeg.exe"
        VGMSTREAM = "vgmstream-win64/vgmstream-cli.exe"
        if "WWISEROOT" in os.environ:
            WWISE_CLI = os.path.join(
                    os.environ["WWISEROOT"],
                    "Authoring\\x64\\Release\\bin\\WwiseConsole.exe"
            )
        else:
            logger.warning("Failed to locate WwiseConsole.exe")
            one_shot_ui.show_warning("Missing Essential Tool",
                                     "Failed to locate WwiseConsole.exe")
    case "Linux":
        VGMSTREAM = "vgmstream-linux/vgmstream-cli"
        FFMPEG = "ffmpeg"
        WWISE_CLI = ""
        logger.warning("Wwise integration is not supported for Linux. WAV file "
                       "import is disabled.")
    case "Darwin":
        VGMSTREAM = "vgmstream-macos/vgmstream-cli"
        FFMPEG = "ffmpeg"
        if os.path.exists("/Applications/Audiokinetic"):
            match = next(pathlib.Path("/Applications/Audiokinetic").glob("Wwise*"))
            WWISE_CLI = os.path.join(match, 
                                     "Wwise.app/Contents/Tools/WwiseConsole.sh")

if os.path.exists(WWISE_CLI):
    if "Wwise2024" in WWISE_CLI:
        WWISE_VERSION = "2024"
    elif "Wwise2023" in WWISE_CLI:
        WWISE_VERSION = "2023"
else:
    WWISE_VERSION = ""

def get_data_path():
    location = os.environ.get("HD2DATA")
    return "" if location == None else location

def set_data_path(path: str):
    os.environ["HD2DATA"] = path 
