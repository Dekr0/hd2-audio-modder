from typing import Set


class GameArchive:
    def __init__(self,
                 db_id: str,
                 game_archive_id: str,
                 tags: Set[str],
                 categories: Set[str]):
        self.db_id = db_id
        self.game_archive_id = game_archive_id
        self.tags = tags
        self.categories = categories


class Soundbank:
    def __init__(self,
                 db_id: str,
                 toc_file_id: int,
                 soundbank_path_name: str,
                 soundbank_readable_name: str,
                 categories: Set[str]):
        self.db_id = db_id
        self.toc_file_id = toc_file_id
        self.soundbank_path_name = soundbank_path_name
        self.soundbank_readable_name = soundbank_readable_name
        self.categories = categories


class HircObjRecord:
    def __init__(self,
                 wwise_object_id: int,
                 type_db_id: str,
                 parent_wwise_object_id: int,
                 label: str,
                 description: str,
                 tags: Set[str]):
        self.wwise_object_id = wwise_object_id
        self.type_db_id = type_db_id
        self.parent_wwise_object_id = parent_wwise_object_id
        self.label = label
        self.description = description
        self.tags = tags


class SoundView:
    def __init__(self,
                 wwise_object_id: int,
                 wwise_short_id: int,
                 label: str,
                 description: str,
                 tags: Set[str]):
        self.wwise_object_id = wwise_object_id
        self.wwise_short_id = wwise_short_id
        self.label = label
        self.tags = tags
        self.description = description
