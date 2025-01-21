from collections.abc import Callable
from dataclasses import dataclass

from imgui_bundle import portable_file_dialogs as pfd

@dataclass
class FilePickerTask:

    picker: pfd.open_file
    callback: Callable[[list[str]], None]
    cancel: bool = False


@dataclass
class FolderPickerTask:

    picker: pfd.select_folder
    callback: Callable[[str], None]
    cancel: bool = False
