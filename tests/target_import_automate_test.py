import os
import posixpath as xpath
import unittest

from backend.target_import_csv import target_import_automation_csv
from backend.target_import_json import target_import_automation_json
from core import Mod
from env import get_data_path


class TargetImportAutomateTest(unittest.IsolatedAsyncioTestCase):

    async def test_target_import_csv(self):
        csvs: list[str] = [entry.path for entry in os.scandir("tests/mockup/csvs")]
        for csv in csvs:
            mod = Mod("")
            archive = csv.split("_")[-1].strip(".csv")
            mod.load_archive_file(xpath.join(get_data_path(), archive))
            await target_import_automation_csv(mod, csv)

    """
    async def test_target_import_json(self):
        jsons: list[str] = [entry.path for entry in os.scandir("tests/mockup/jsons")]
        for j in jsons:
            mod = Mod("")
            archive = j.split("_")[-1].strip(".json")
            mod.load_archive_file(xpath.join(get_data_path(), archive))
            await target_import_automation_json(mod, j)
    """
