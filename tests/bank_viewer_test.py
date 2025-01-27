import os
import unittest

from backend.core import ModHandler, SoundHandler
from backend.env import get_data_path, set_data_path
from ui.bank_viewer.state import BankViewerState


class TestBankViewer(unittest.TestCase):

    def test_create_view_dry_run(self):
        set_data_path("D:/Program Files/Steam/steamapps/common/Helldivers 2/data")
        
        ModHandler.create_instance()
        SoundHandler.create_instance()

        mod_handler: ModHandler = ModHandler.get_instance()

        entries = os.scandir(get_data_path())
        for entry in entries:
            if not entry.is_file():
                continue
            name, ext = os.path.splitext(entry)
            if ext == ".stream":
                print(f"Loading {name}")
                mod = mod_handler.create_new_mod(name)
                mod.load_archive_file(entry.path.removesuffix(".stream"))
                bank_state = BankViewerState(mod.get_wwise_banks())
                bank_state.create_bank_hirc_view(mod, {})

    def test_create_view_debugging(self):
        set_data_path("D:/Program Files/Steam/steamapps/common/Helldivers 2/data")
        
        ModHandler.create_instance()
        SoundHandler.create_instance()

        mod_handler: ModHandler = ModHandler.get_instance()

        mod_handler.create_new_mod("adjudicator")
        mod = mod_handler.get_active_mod()

        mod.load_archive_file("D:/Program Files/Steam/steamapps/common/Helldivers 2/data/a66d7cf238070ca7")
        bank_state = BankViewerState(mod.get_wwise_banks())
        bank_state.create_bank_hirc_view(mod, {})

        pass
