import os
import pickle
import tkinter.messagebox as message_box
import tkinter.filedialog as file_dialog
import uuid

from log import logger


class Separator:

    version = 1
    entry_type = "Separator"

    def __init__(self, id: str, label: str, linked_entry_id: int):
        self.id = id
        self.label = label
        self.linked_entry_id = linked_entry_id 

class Config:

    def __init__(self, game_data_path: str,
                 separators: dict[str, Separator] = {},
                 separated_entries: dict[int, list[str]] = {},
                 workspace_paths: set[str] = set(),
                 recent_files: list[str] = [],
                 theme: str = "dark_mode",):
        self.game_data_path = game_data_path
        self.workspace_paths = workspace_paths
        self.theme = theme
        self.recent_files = recent_files
        self.separators = separators
        self.separated_entries = separated_entries

    """
    @return (int): A status code to tell whether there are new workspace being 
    added
    """
    def add_new_workspace(self, workspace_path : str = "") -> int:
        if not os.path.exists(workspace_path):
            return 1
        if workspace_path in self.workspace_paths:
            return 1
        self.workspace_paths.add(workspace_path)
        return 0 

    def save_config(self, config_path: str = "config.pickle"):
        try:
            with open(config_path, "wb") as f:
                pickle.dump(self, f)
        except Exception as e:
            logger.error("Error occur when serializing configuration")
            logger.error(e)

    def get_workspace_paths(self) -> set[str]:
        # Validate and update all workspace paths to ensure they exists
        self.workspace_paths = set([p for p in self.workspace_paths 
                                    if os.path.exists(p)])
        return self.workspace_paths

    def add_separator(self, label: str, linked_entry_id: int) -> str:
        id = uuid.uuid4().hex
        if id in self.separators:
            logger.error("Hash collision when creating a new separator!")
            return ""
        separator = Separator(id, label, linked_entry_id)
        self.separators[id] = separator
        if linked_entry_id not in self.separated_entries:
            self.separated_entries[linked_entry_id] = [separator.id]
        else:
            self.separated_entries[linked_entry_id].append(separator.id)
        return separator.id

    def remove_separator(self, id: str):
        if id not in self.separators:
            return
        linked_entry_id = self.separators.pop(id).linked_entry_id
        if linked_entry_id not in self.separated_entries:
            return
        self.separated_entries[linked_entry_id].remove(id)

def load_config(config_path: str = "config.pickle") -> Config | None:
    if os.path.exists(config_path):
        cfg: Config | None = None
        try:
            # Reading existence configuration
            with open(config_path, "rb") as f:
                cfg = pickle.load(f)
            if not isinstance(cfg, Config):
                raise ValueError("Invalid configuration data")
        except Exception as e:
            logger.critical("Error occurred when de-serializing configuration")
            logger.critical(e)
            logger.critical(f"Delete {config_path} to resolve the error")
            cfg = None
        if cfg == None:
            return None
        if not os.path.exists(cfg.game_data_path):
            # Old game data path is no longer valid, require update
            game_data_path: str | None = _select_game_data_path()
            if game_data_path is None:
                return None
            cfg.game_data_path = game_data_path
            cfg.workspace_paths = set([p for p in cfg.workspace_paths 
                                   if os.path.exists(p)])
        # for backwards compatibility with config created before these were added
        # Suggestion for backward compatibility: version number. If version 
        # number is missing, assume it's the oldest version.
        try: 
            _ = cfg.theme
        except:
            cfg.theme = "dark_mode"
        try:
            _ = cfg.recent_files
        except:
            cfg.recent_files = []
        try:
            _ = cfg.separators
        except:
            cfg.separators = {}
        try:
            _ = cfg.separated_entries
        except:
            cfg.separated_entries = {}
        cfg.save_config()
        return cfg

    game_data_path: str | None = _select_game_data_path()
    if game_data_path is None:
        return None
    new_cfg: Config = Config(game_data_path)
    new_cfg.save_config(config_path)

    return new_cfg

def _select_game_data_path() -> str | None:
    while True:
        game_data_path: str = file_dialog.askdirectory(
            mustexist=True,
            title="Locate game data directory for Helldivers 2"
        )
        if os.path.exists(game_data_path) \
                and game_data_path.endswith("steamapps/common/Helldivers 2/data"):
            return game_data_path
        res = message_box.askretrycancel(message="Invalid game data directory")
        if not res:
            return None
