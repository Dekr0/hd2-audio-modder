import sqlite3

from logging import Logger
from typing import Callable

def config_sqlite_conn(db_path: str):
    conn: sqlite3.Connection | None = None

    def _get_sqlite_conn() -> sqlite3.Connection | None:
        nonlocal conn
        if conn != None:
            return conn

        # Exception source
        conn = sqlite3.connect(db_path)

        return conn

    return _get_sqlite_conn

class HelldiverGameArchive:

    """
    game_archive_id: Hex ID appear on the game data directory
    tags: names (from Google Sheet) that are given to each game archive
    """
    def __init__(self,
                 id: str,
                 game_archive_id: str,
                 categories: set[str],
                 tags: set[str]
                 ):
        self.id = id
        self.game_archive_id = game_archive_id
        self.categories = categories
        self.tags = tags

        def __str__(self):
            s = f"ID: {self.id}\n"
            s += f"Game archive ID: {self.game_archive_id}\n"
            s += f"Catgories: {self.categories}\n"
            s += f"Tags: {self.tags}\n\n"
            
            return s

class HelldiverSoundbank:

    """
    soundbank_id: File ID from its associative ToC Header 
    soundbank_name: Human readable name from its associative Wwise Dependency 
    """
    def __init__(self,
                 id: str,
                 soundbank_id: int,
                 soundbank_name: str,
                 soundbank_readable_name: str,
                 categories: set[str],
                 linked_game_archive_ids: set[str]
                 ):
        self.id = id
        self.soundbank_id = soundbank_id
        self.soundbank_name = soundbank_name
        self.soundbank_readable_name = soundbank_readable_name
        self.categories = categories
        self.linked_game_archive_ids = linked_game_archive_ids

    def __str__(self):
        s = f"DB Id: {self.id}\n"
        s += f"Sounbank Id: {self.soundbank_id}\n"
        s += f"Soundbank Name: {self.soundbank_name}\n"
        s += f"Soundbank readable name: {self.soundbank_readable_name}\n"
        s += f"Category: {self.categories}\n"
        s += f"Linked game archives: {self.linked_game_archive_ids}\n\n"

        return s

class HelldiverAudioSource:

    """
    audio_source_id: 32-bits Wwise short ID in the Wwise Sound object. 
    """
    def __init__(self,
                 id: str,
                 audio_source_id: int,
                 label: str,
                 tags: set[str],
                 linked_soundbank_ids: set[int]
                 ):
        self.id = id
        self.audio_source_id = audio_source_id
        self.label = label
        self.tags = tags
        self.linked_soundbank_ids = linked_soundbank_ids

    def __str__(self):
        s = f"DB Id: {self.id}\n"
        s += f"Audio Source ID: f{self.audio_source_id}\n"
        s += f"Label: {self.label}\n"
        s += f"Tags: {self.tags}\n"
        s += f"Linked Soundbank ID: {self.linked_soundbank_ids}\n\n"

        return s

class LookupStore:

    """
    Query game archive by category is not 100% accurate because there are game 
    archives that contain Wwise Soundbanks with mixed categories.
    """
    def query_helldiver_game_archive_by_category(self, category: str = "") -> \
            list[HelldiverGameArchive]:
        return []

    """
    Query game archive based on the assigned names (aka. tag). The label 
    names are direct sourced from the Google Sheet.

    This query is identical to first implementation of builtin archive search
    """
    def query_helldiver_game_archive_by_tag(self, tag: str = "") -> \
            list[HelldiverGameArchive]:
        return []

    def write_helldiver_soundbank_bulk(self,
                                        banks: list[HelldiverSoundbank]):
        pass

    def write_helldiver_audio_source_bulk(self,
                                          sources: list[HelldiverAudioSource]):
        pass

class SQLiteLookupStore (LookupStore):

    def __init__(self, initializer: Callable[[], sqlite3.Connection | None], 
                 logger: Logger):
        # Let exception bubble up
        self.conn = initializer()

        self.logger = logger

        if self.conn != None:
            # Let exception bubble up
            self.cursor = self.conn.cursor()
        else:
            raise RuntimeError("Builtin audio source lookup is disabled due to \
                    database connection error")

    def query_helldiver_game_archive_by_category(self, category: str = "") -> \
            list[HelldiverGameArchive]:
        rows: sqlite3.Cursor
        archives: list[HelldiverGameArchive] = []

        try:
            if category == "":
                rows = self.cursor.execute("SELECT * FROM helldiver_game_archive")
            else:
                args = (f"%{category}%",)
                rows = self.cursor.execute("SELECT * FROM helldiver_game_archive"
                                           " WHERE categories LIKE ?"
                                           , args)
            archives = [
                    HelldiverGameArchive(
                        row[0],
                        row[1],
                        set(row[2].split(";")),
                        set(row[3].split(";"))
                    ) 
                    for row in rows
                    ]
        except Exception as err:
            self.logger.critical(err, stack_info=True)
            archives = []

        return archives

    def write_helldiver_soundbank_bulk(self, banks: list[HelldiverSoundbank]):
        try:
            self.cursor.execute("DELETE FROM helldiver_soundbank")
            self.conn.commit()
            data = [
                    (
                        bank.id,
                        str(bank.soundbank_id),
                        bank.soundbank_name,
                        bank.soundbank_readable_name,
                        ";".join(bank.categories),
                        ";".join(bank.linked_game_archive_ids)
                        )
                    for bank in banks
                    ]
            self.cursor.executemany("INSERT INTO helldiver_soundbank (\
                    id, \
                    soundbank_id, \
                    soundbank_name, \
                    soundbank_readable_name, \
                    categories, \
                    linked_game_archive_ids) VALUES (\
                    ?, ?, ?, ?, ?, ?)", data)
            self.conn.commit()
        except Exception as err:
            self.logger.error(err)

    def write_helldiver_audio_source_bulk(self,
                                          sources: list[HelldiverAudioSource]):
        try:
            self.cursor.execute("DELETE FROM helldiver_audio_source")
            self.conn.commit()
            data = [
                    (
                        source.id,
                        str(source.audio_source_id),
                        source.label,
                        ";".join(source.tags),
                        ";".join([str(i) for i in source.linked_soundbank_ids]),
                        )
                    for source in sources 
                    ]
            self.cursor.executemany("INSERT INTO helldiver_audio_source (\
                    id, \
                    audio_source_id, \
                    label, \
                    tags, \
                    linked_soundbank_ids) VALUES (\
                    ?, ?, ?, ?, ?)", data)
            self.conn.commit()
        except Exception as err:
            self.logger.error(err)
