import sqlite3

from typing import Callable
import uuid

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

    def get_random_seq_containers_view_all(self) -> \
            list[orm.RandomSeqContainerView]:
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
    
    def get_random_seq_cntr_label_view_by_obj_id_many(
            self, wwise_object_ids: list[str]) -> dict[str, str]:
        param_slots = ",".join(["?" for _ in range(len(wwise_object_ids))])
        wwise_object_ids_str = [wwise_object_id 
                                for wwise_object_id in wwise_object_ids]
        query = f"SELECT wwise_object_id, label FROM random_seq_container_view WHERE wwise_object_id IN ({param_slots})" 
        rows = self.cursor.execute(query, wwise_object_ids_str)
        results: dict[str, str] = {}
        for row in rows:
            if row[0] not in results:
                results[row[0]] = row[1]
            else:
                if results[row[0]] == "" and row[1] != "":
                    results[row[0]] = row[1]
        return results
        
    def get_random_seq_cntr_db_id_by_object_id(self, wwise_object_id: str) \
            -> list[str]: 
        rows = self.cursor.execute("SELECT db_id FROM hierarchy_object WHERE wwise_object_id = ?", (wwise_object_id,))
        return [row[0] for row in rows]

    def get_soundbank_path_name_all(self) -> list[str]:
        query = "SELECT soundbank_path_name FROM soundbank"
        rows = self.cursor.execute(query)
        return [row[0] for row in rows]

    def get_sounds_from_view_all(self) -> list[orm.SoundView]:
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

    def get_sound_label_by_source_id_view(self, source_id: str) -> list[str]:
        query = f"SELECT label FROM sound_view WHERE wwise_short_id = ?"
        rows = self.cursor.execute(query, (source_id,))
        return [row[0] for row in rows]

    def get_sound_by_source_id_view_many(
            self, source_ids: list[str]) -> list[orm.SoundView]:
        param_slots = ",".join(["?" for _ in range(len(source_ids))])
        source_ids_str = [source_id for source_id in source_ids]
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

    def get_sound_label_by_source_id_view_many(self, source_ids: list[str]) -> \
        dict[str, str]:
        param_slots = ",".join(["?" for _ in range(len(source_ids))])
        source_ids_str = [source_id for source_id in source_ids]
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
            
    def insert_random_seq_cntr(self, 
                               label: str,
                               wwise_object_id: str, 
                               paren_wwise_object_id: str,
                               linked_soundbank_path_names: set[str],
                               commit: bool = False):
        rows = self.cursor.execute(f"SELECT db_id FROM hierarchy_object_type "
                                   "WHERE type = 'Random / Sequence Container'")
        type_db_id = rows.fetchone() 
        if type_db_id == None:
            raise RuntimeError("Failed to obtain ID of Random / Sequence "
                               "container type")
        db_id = uuid.UUID().hex
        self.cursor.execute(f"INSERT INTO hierarchy_object "
                            "(db_id, wwise_object_id, type_db_id, "
                            "parent_wwise_object_id, linked_soundbank_path_names) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (db_id, wwise_object_id, type_db_id, paren_wwise_object_id,
                             ",".join(linked_soundbank_path_names)))
        self.cursor.execute(f"INSERT INTO random_seq_container "
                            "(db_id, label, tags) VALUES (?, ?, ?)",
                            (db_id, label, ""))
        commit and self.commit() # type: ignore

    def update_sound_label_by_source_id(self, 
                                        label: str, 
                                        source_id: str, 
                                        commit: bool = False):
        query = f"UPDATE sound SET label = ? WHERE wwise_short_id = ?" 
        self.cursor.execute(query, (label, source_id))
        commit and self.commit() # type: ignore

    def update_random_seq_cntr_label_by_object_id(
            self, label: str, wwise_object_id: str, commit: bool = False):
        db_ids = self.get_random_seq_cntr_db_id_by_object_id(wwise_object_id)
        if len(db_ids) == 0:
            raise RuntimeError("No random sequence container associates with "
                               f"wwise object id {wwise_object_id}")
        if len(db_ids) > 1:
            raise RuntimeError("More than one random sequence container "
                               f"associateds with wwise object id {wwise_object_id}")
        query = f"UPDATE random_seq_container SET label = ? WHERE db_id = ?"
        self.cursor.execute(query, (label, db_ids[0]))
        commit and self.commit() # type: ignore

    """
    @param updates - list[tuple[label, db_id]]
    """
    def update_random_seq_cntr_by_source_id_many(
        self,
        updates: list[tuple[str, str]],
        commit: bool = False
    ):
        query = f"UPDATE random_seq_container SET label = ? WHERE db_id = ?"
        self.cursor.executemany(query, updates)
        commit and self.commit() # type: ignore

    """
    @param updates - list[tuple[label, wwise_short_id]]
    """
    def update_sound_label_by_source_id_many(
            self, 
            updates: list[tuple[str, str]],
            commit: bool = False
        ):
        query = f"UPDATE sound SET label = ? WHERE wwise_short_id = ?"
        self.cursor.executemany(query, updates)
        commit and self.commit() # type: ignore
