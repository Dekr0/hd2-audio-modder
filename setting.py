import os
import pickle

from collections import deque

import fileutil

from log import logger


class Setting:

    def __init__(
            self,
            data: str = "",
            recent_files: deque[str] = deque(maxlen=5),
            workspace_paths: set[str] = set()):
        self.data = data
        self.recent_files = recent_files
        self.workspace_paths = workspace_paths

    def add_new_workspace(self, workspace_path : str = "") -> bool:
        if not os.path.exists(workspace_path):
            return False

        if workspace_path in self.workspace_paths:
            return False

        self.workspace_paths.add(workspace_path)

        return True

    def save(self, config_path: str = "setting.pickle"):
        """
        @exception
        - OSError
        - pickle.PickleError
        """
        with open(config_path, "wb") as f:
            pickle.dump(self, f)

    def get_workspace_paths(self) -> set[str]:
        self.workspace_paths = set([p for p in self.workspace_paths 
                                    if os.path.exists(p)])
        return self.workspace_paths

    def update_recent_file(self, recent_file: str):
        if recent_file in self.recent_files:
            self.recent_files.remove(recent_file)
        self.recent_files.appendleft(recent_file)


def load_setting(path: str = "setting.pickle") -> Setting:
    """
    @exception
    - OSError
    - pickle.PickleError
    """
    if not os.path.exists(path):
        logger.warning("Failed to locate existing application setting. Creating "
                       " new one...")

        setting = Setting()
        setting.save()

        logger.info("Created brand new application setting")

        return setting

    with open(path, "rb") as f:
        setting = pickle.load(f)
        if not isinstance(setting, Setting):
            raise ValueError("De-serializing pickle data is not an instance of "
                             "Setting.")

        if not hasattr(setting, "recent_files"):
            setting.recent_files = deque(maxlen=5) 

        setting.recent_files = deque([fileutil.to_posix(f) 
                                for f in setting.recent_files
                                if os.path.exists(f)], maxlen=5)
        setting.save()

        return setting
