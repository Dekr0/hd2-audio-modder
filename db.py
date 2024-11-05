import sqlite3
import uuid

from logging import Logger
from typing import Callable

def config_sqlite_conn(db_path: str):
    conn: sqlite3.Connection | None = None

    def _get_sqlite_conn() -> sqlite3.Connection | None:
        nonlocal conn
        if conn != None:
            return conn
        conn = sqlite3.connect(db_path)
        return conn

    return _get_sqlite_conn

# Redesign
class HelldiverGameArchive:

    def __init__(self,
                 id: str,
                 game_archive_id: str,
                 categories: set[str]
                 ):
        self.id = id
        self.game_archive_id = game_archive_id
        self.categories = categories

        def __str__(self):
            return f"ID {self.id}; Game archive id: {self.game_archive_id}"

class HelldiverAudioBank:

    def __init__(self,
                 id: str,
                 audio_bank_id: int,
                 audio_bank_name: str,
                 audio_bank_readable_name: str,
                 category: str,
                 linked_game_archives: set[str]
                 ):
        self.id = id
        self.audio_bank_id = audio_bank_id
        self.audio_bank_name = audio_bank_name
        self.audio_bank_readable_name = audio_bank_readable_name
        self.category = category
        self.linked_game_archives = linked_game_archives

    def __str__(self):
        return f"Audio bank id: {self.audio_bank_id}; Audio bank name: " + \
               f"{self.audio_bank_name}"

class HelldiverAudioSource:

    def __init__(self,
                 id: str,
                 audio_source_id: int,
                 label: str,
                 tags: list[str],
                 linked_audio_bank_id: list[str]
                 ):
        self.id = id
        self.audio_source_id = audio_source_id
        self.label = label
        self.tags = tags
        self.linked_audio_bank_id = linked_audio_bank_id

    def __str__(self):
        return f"Audio Source id: {self.audio_source_id};"
# End

class HelldiverAudioArchive:

    def __init__(self, 
                 audio_archive_id: str, 
                 audio_archive_name_id: str,
                 audio_archive_name: str):
        self.audio_archive_id = audio_archive_id
        self.audio_archive_name_id = audio_archive_name_id
        self.audio_archive_name = audio_archive_name

class HelldiverAudioArchiveName:

    def __init__(self,
                 audio_archive_name_id: str,
                 audio_archive_name: str):
        self.audio_archive_name_id = audio_archive_name_id
        self.audio_archive_name = audio_archive_name

class OldHelldiverAudioSource:

    def __init__(self,
                 audio_source_id: int,
                 linked_audio_archive_ids: set[str],
                 linked_audio_archive_name_ids: set[str]
                 ):
        self.audio_source_id = audio_source_id
        self.linked_audio_archive_ids = linked_audio_archive_ids
        self.linked_audio_archive_name_ids = linked_audio_archive_name_ids

"""
Database Access Interface
"""
class LookupStore:

    def query_helldiver_four_vo(self, query: str) -> dict[str, str]:
        return {} 

    def query_helldiver_game_archive(self, category: str = "") -> \
            list[HelldiverGameArchive]:
        return []

    def query_helldiver_audio_archive(self, category: str = "") -> \
            list[HelldiverAudioArchive]:
        return []

    def query_helldiver_audio_archive_category(self) -> list[str]:
        return []

    def write_helldiver_audio_source_bulk(self,
                                          sources: list[OldHelldiverAudioSource]):
        pass

class SQLiteLookupStore (LookupStore):

    def __init__(self, initializer: Callable[[], sqlite3.Connection | None], 
                 logger: Logger):
        self.conn = initializer()
        self.logger = logger
        if self.conn != None:
            self.cursor = self.conn.cursor()
        else:
            logger.warning("Builtin audio source lookup is disabled due to \
                    database connection error")

    def query_helldiver_game_archive(self, category: str = "") -> \
            list[HelldiverGameArchive]:
        rows: sqlite3.Cursor
        archives: list[HelldiverGameArchive] = []

        try:
            if category == "":
                rows = self.cursor.execute("SELECT * FROM helldiver_game_archive")
            else:
                args = (category,)
                rows = self.cursor.execute("SELECT * FROM helldiver_game_archive"
                                           " WHERE audio_archive_category LIKE ?"
                                           , args)
            archives = [
                    HelldiverGameArchive(
                        row[0],
                        row[1],
                        set(row[2].split(","))
                    ) 
                    for row in rows
                    ]
        except (sqlite3.OperationalError, sqlite3.IntegrityError) as err:
            self.logger.critical(err, stack_info=True)
            archives = []

        return archives
    
    def query_helldiver_audio_archive(self, category: str = "") -> \
            list[HelldiverAudioArchive]:
        rows: sqlite3.Cursor
        archives: list[HelldiverAudioArchive] = []
        try:
            if category == "":
                rows = self.cursor.execute("SELECT \
                        audio_archive_id, \
                        helldiver_audio_archive.audio_archive_name_id, \
                        audio_archive_name \
                        FROM helldiver_audio_archive INNER JOIN \
                        helldiver_audio_archive_name ON \
                        helldiver_audio_archive.audio_archive_name_id = \
                        helldiver_audio_archive_name.audio_archive_name_id")
            else:
                args = (category,)
                rows = self.cursor.execute("SELECT \
                        audio_archive_id, \
                        helldiver_audio_archive.audio_archive_name_id, \
                        audio_archive_name \
                        FROM helldiver_audio_archive INNER JOIN \
                        helldiver_audio_archive_name ON \
                        helldiver_audio_archive.audio_archive_name_id = \
                        helldiver_audio_archive_name.audio_archive_name_id \
                        WHERE audio_archive_category = ?", args)
            archives = [HelldiverAudioArchive(row[0], row[1], row[2]) 
                        for row in rows]
        except (sqlite3.OperationalError, sqlite3.IntegrityError) as err:
            self.logger.critical(err, stack_info=True)
        finally:
            return archives 

    def query_helldiver_audio_archive_category(self) -> list[str]:
        audio_archive_categories: list[str] = []
        try:
            rows = self.cursor.execute("SELECT DISTINCT audio_archive_category \
                    FROM helldiver_audio_archive")
            audio_archive_categories = [row[0] for row in rows]
        except (sqlite3.OperationalError, sqlite3.IntegrityError) as err:
            self.logger.critical(err, stack_info=True)
        finally:
            return audio_archive_categories

#    def query_helldiver_four_vo(self, query: str) -> dict[str, str]:
#        if len(query) == "":
#            return {}
#
#        if self.cursor == None:
#            return {}
#        # TO-DO the possibilities of verify SQL injection
#        args = (" OR ".join([f"\"{token}\"" for token in query.strip().split(" ") 
#                             if len(token) > 0]), )
#        rows = self.cursor.execute("", args)
#        return {row[0]: row[1] for row in rows} 

    def write_helldiver_audio_source_bulk(self,
                                          sources: list[OldHelldiverAudioSource]):
        if self.conn == None or self.cursor == None:
            return
        try:
            self.cursor.execute("DELETE FROM helldiver_audio_source")
            self.conn.commit()
            data = [
                    (
                        uuid.uuid4().hex,
                        str(source.audio_source_id),
                        ",".join(source.linked_audio_archive_ids),
                        ",".join(source.linked_audio_archive_name_ids)
                    )
                    for source in sources
                    ]
            self.cursor.executemany("INSERT INTO helldiver_audio_source (\
                    audio_source_db_id, \
                    audio_source_id, \
                    linked_audio_archive_ids, \
                    linked_audio_archive_name_ids) VALUES (\
                    ?, ?, ?, ?)", data)
            self.conn.commit()
        except (sqlite3.OperationalError, sqlite3.IntegrityError) as err:
            self.logger.error(err)
