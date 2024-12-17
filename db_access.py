import sqlite3

from typing import Callable

import db_schema_map as orm


"""
Singleton database connection initializer within the lifetime of an application

Exception will happen.
"""
def config_sqlite_conn(db_path: str):
    conn: sqlite3.Connection | None = None

    def _get_sqlite_conn() -> sqlite3.Connection | None:
        nonlocal conn
        if conn != None:
            return conn
        conn = sqlite3.connect(db_path)
        return conn

    return _get_sqlite_conn

"""
All database access method will raise exception.
"""
class SQLiteDatabase:

    """
    Can raise Exception. Exception is bubble up by database connection 
    initialize function
    """
    def __init__(self, 
                 initializer: Callable[[], sqlite3.Connection | None]):
        self.conn = initializer()
        if self.conn != None:
            self.cursor = self.conn.cursor()
        else:
            raise RuntimeError("Failed to establish database connection")

    """
    Can raise Exception 
    """
    def close(self):
        if self.conn != None:
            self.cursor.close()
            self.conn.commit()
            self.conn.close()

    def commit(self):
        if self.conn != None:
            self.conn.commit()

    """
    @param game_archive_id - str
    """
    def get_game_archive_by_game_archive_id_single(self, game_archive_id: str) -> \
        orm.GameArchive | None:
        query = "SELECT * FROM game_archive WHERE game_archive_id = ?"
        result = self.cursor.execute(query, (f"'{game_archive_id}'"))
        record = result.fetchone()
        if record == None:
            return None
        return orm.GameArchive(
                record[0], 
                record[1], 
                record[2], 
                set(record[3].split(";")))

    """
    @param path_name - str => Path name used by the game engine to identify the 
    soundbank

    @return dict[soundbank_path_name, set[game_archive_id]]
    """
    def get_game_archive_by_soundbank_path_name_many(self, path_name: str) -> \
            dict[str, set[str]]:
        query = "SELECT soundbank_path_name, linked_game_archive_ids FROM "
        "soundbank WHERE soundbank_path_name LIKE ?"
        rows = self.cursor.execute(query, (f"'%{path_name}%'",))
        return { row[0]: set(row[1].split(";")) for row in rows }

    def get_random_seq_containers_view_many(self) -> list[orm.RandomSeqContainerView]:
        rows = self.cursor.execute("SELECT * FROM random_seq_container_view")
        random_seq_cntr = [
            orm.RandomSeqContainerView(
                int(row[0]),
                int(row[1]),
                row[2],
                set(row[3].split(";")),
                set(row[4].split(";"))
            ) for row in rows
        ]
        return random_seq_cntr

    def get_soundbank_path_name_many(self) -> list[str]:
        query = "SELECT soundbank_path_name FROM soundbank"
        rows = self.cursor.execute(query)
        return [row[0] for row in rows]

    def get_sounds_from_view(self) -> list[orm.SoundView]:
        rows = self.cursor.execute("SELECT * FROM sound_view")
        sounds = [orm.SoundView(
                int(row[0]),
                int(row[1]),
                int(row[2]),
                row[3],
                set(row[4].split(";")),
                set(row[5].split(";"))
            ) for row in rows]
        return sounds

    def get_sound_label_by_source_id_view(self, source_id: int) -> list[str]:
        query = f"SELECT label FROM sound_view WHERE wwise_short_id = ?"
        rows = self.cursor.execute(query, (str(source_id),))
        return [row[0] for row in rows]

    def get_sound_by_source_id_view_many(
            self, source_ids: list[int]) -> list[orm.SoundView]:
        param_slots = ",".join(["?" for _ in range(len(source_ids))])
        source_ids_str = [str(source_id) for source_id in source_ids]
        query = f"SELECT * FROM sound_view WHERE wwise_short_id IN ({param_slots})" 
        rows = self.cursor.execute(query, source_ids_str)
        sounds = [orm.SoundView(
                int(row[0]),
                int(row[1]),
                int(row[2]),
                row[3],
                set(row[4].split(";")),
                set(row[5].split(";"))
            ) for row in rows]

        return sounds

    def get_sound_label_by_source_id_view_many(self, source_ids: list[int]) -> \
        dict[str, str]:
        param_slots = ",".join(["?" for _ in range(len(source_ids))])
        source_ids_str = [str(source_id) for source_id in source_ids]
        query = f"SELECT wwise_short_id, label FROM sound_view WHERE wwise_short_id IN ({param_slots})" 
        rows = self.cursor.execute(query, source_ids_str)
        results: dict[str, str] = {}
        for row in rows:
            if row[0] not in results:
                results[row[0]] = row[1]
            else:
                if results[row[0]] == "" and row[1] != "":
                    results[row[0]] = row[1]
        return results
            

    def update_sound_label_by_source_id(self, label: str, source_id: int):
        query = f"UPDATE sound SET label = ? WHERE wwise_short_id = ?" 
        self.cursor.execute(query, (label, str(source_id)))
        self.commit()

    def update_random_seq_container_by_source_id(self, label: str, db_id: str):
        query = f"UPDATE random_seq_container SET label = ? WHERE db_id = ?"
        self.cursor.execute(query, (label, db_id))
        self.commit()

    """
    @param updates - list[tuple[label, db_id]]
    """
    def update_random_seq_container_by_source_id_many(
        self,
        updates: list[tuple[str, str]]
    ):
        query = f"UPDATE random_seq_container SET label = ? WHERE db_id = ?"
        self.cursor.executemany(query, updates)
        self.commit()

    """
    @param updates - list[tuple[label, wwise_short_id]]
    """
    def update_sound_label_by_source_id_many(
            self, 
            updates: list[tuple[str, str]] 
        ):
        query = f"UPDATE sound SET label = ? WHERE wwise_short_id = ?"
        self.cursor.executemany(query, updates)
        self.commit()
