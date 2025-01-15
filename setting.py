import os
import pickle

import fileutil


class Setting:

    def __init__(
            self,
            data: str = "",
            recent_files: list[str] = [],
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


def load_setting(path: str = "setting.pickle") -> Setting:
    """
    @exception
    - OSError
    - pickle.PickleError
    """
    if not os.path.exists(path):
        setting = Setting()
        setting.save()
        return setting

    with open(path, "rb") as f:
        setting = pickle.load(f)
        if not isinstance(setting, Setting):
            raise ValueError("De-serializing pickle data is not an instance of "
                             "Setting.")

        if not hasattr(setting, "recent_files"):
            setting.recent_files = []

        setting.recent_files = [fileutil.to_posix(f) 
                                for f in setting.recent_files
                                if os.path.exists(f)]
        setting.save()

        return setting
