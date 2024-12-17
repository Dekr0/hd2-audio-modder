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
                 categories: Set[str],
                 linked_game_archive_ids: Set[str]):
        self.db_id = db_id
        self.toc_file_id = toc_file_id
        self.soundbank_path_name = soundbank_path_name
        self.soundbank_readable_name = soundbank_readable_name
        self.categories = categories
        self.linked_game_archive_ids = linked_game_archive_ids


class HierarchyObject:
    def __init__(self,
                 db_id: str,
                 wwise_object_id: int,
                 obj_type_db_id: int,
                 parent_wwise_object_id: int,
                 linked_soundbank_path_names: Set[str]):
        self.db_id = db_id
        self.wwise_object_id = wwise_object_id
        self.obj_type_db_id = obj_type_db_id
        self.parent_wwise_object_id = parent_wwise_object_id
        self.linked_soundbank_path_names = linked_soundbank_path_names


class RandomSeqContainer:
    def __init__(self,
                 db_id: str,
                 label: str,
                 tags: Set[str]):
        self.db_id = db_id
        self.label = label
        self.tags = tags


class RandomSeqContainerView:
    def __init__(self,
                 wwise_object_id: int,
                 parent_wwise_object_id: int,
                 label: str,
                 tags: Set[str],
                 linked_soundbank_path_names: Set[str]):
        self.wwise_object_id = wwise_object_id
        self.parent_wwise_object_id = parent_wwise_object_id
        self.label = label
        self.tags = tags
        self.linked_soundbank_path_names = linked_soundbank_path_names


class Sound:
    def __init__(self,
                 db_id: str,
                 wwise_short_id: int,
                 label: str,
                 tags: Set[str]):
        self.db_id = db_id
        self.wwise_short_id = wwise_short_id
        self.label = label
        self.tags = tags

class SoundView:
    def __init__(self,
                 wwise_object_id: int,
                 parent_wwise_object_id: int,
                 wwise_short_id: int,
                 label: str,
                 tags: Set[str],
                 linked_soundbank_path_names: Set[str]):
        self.wwise_object_id = wwise_object_id
        self.parent_wwise_object_id = parent_wwise_object_id
        self.wwise_short_id = wwise_short_id
        self.label = label
        self.tags = tags
        self.linked_soundbank_path_names = linked_soundbank_path_names
