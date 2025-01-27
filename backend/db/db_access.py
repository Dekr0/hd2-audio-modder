import sqlite3
import os
import time

from typing import Callable

import backend.db.db_schema_map as orm

def config_sqlite_conn(db_path: str):
    """
    @exception
    - OSError
    """
    if not os.path.exists(db_path):
        raise OSError(f"Database {db_path} does not exists.")

    def _get_sqlite_conn() -> sqlite3.Connection | None:
        """
        @exception
        - sqlite3.Error
        """
        conn = sqlite3.connect(db_path, timeout = 5.0)
        return conn

    return _get_sqlite_conn


class SQLiteDatabase:

    def __init__(self, 
                 initializer: Callable[[], sqlite3.Connection | None]):
        """
        @exception
        - RuntimeError
        - sqlite3.Error
        """
        self.conn = initializer()
        if self.conn != None:
            self.cursor = self.conn.cursor()
        else:
            raise RuntimeError("Failed to establish database connection")

    def close(self, commit = False):
        """
        @exception
        - Any
        """
        if self.conn != None:
            self.cursor.close()
            if commit: 
                self.conn.commit()
            self.conn.close()

    def commit(self):
        if self.conn != None:
            self.conn.commit()

    def get_all_hirc_obj_types(self) -> dict[str, str]:
        """
        @exception
        - AssertionError
        - Any
        """
        rows = self.cursor.execute("SELECT * FROM hierarchy_object_type")
        results: dict[str, str] = {}
        for row in rows:
            if row[0] in results:
                raise AssertionError("Field db_id in table hierarchy_object_type does not meet PRIMARY KEY constraint.")
            results[row[0]] = row[1]
        return results

    def get_sound_objs_by_soundbank(self, bank_name: str, as_dict: bool = False) -> dict[int, orm.SoundView] | list[orm.SoundView]:
        """
        @exception
        - TypeError, ValueError
        - AssertionError
        - sqlite3.*Error
        """
        query = "SELECT wwise_object_id, wwise_short_id, label, tags, description FROM sound_view WHERE soundbank_path_name = ?"
        rows = self.cursor.execute(query, (bank_name,))

        if as_dict:
            results: dict[int, orm.SoundView] = {}
            for row in rows:
                wwise_object_id = int(row[0])
                if wwise_object_id in results:
                    raise AssertionError("Field wwise_object_id UNIQUE constraint is not meet! ")
                results[wwise_object_id] = orm.SoundView(
                    wwise_object_id,
                    int(row[1]),
                    row[2],
                    row[4],
                    set(row[3].split(","))
                )
            return results
        else:
            return [orm.SoundView(int(row[0]), int(row[1]), row[2], row[4], set(row[3].split(","))) for row in rows]

    def get_hirc_objs_by_soundbank(self, bank_names: list[str], as_dict: bool = False) \
            -> dict[int, orm.HircObjRecord] | list[orm.HircObjRecord]:
        """
        @exception
        - TypeError, ValueError
        - AssertionError
        - sqlite3.*Error
        """
        if len(bank_names) <= 0:
            return {} if as_dict else []
        cond = "OR ".join([f"soundbank_path_name = ?" for _ in range(len(bank_names))])
        query = f"SELECT wwise_object_id, type_db_id, parent_wwise_object_id, label, tags, description FROM hierarchy_object_view WHERE {cond}"
        rows = self.cursor.execute(query, tuple(bank_names))
        if as_dict:
            results: dict[int, orm.HircObjRecord] = {}
            for row in rows:
                wwise_object_id = int(row[0])
                if wwise_object_id in results:
                    raise AssertionError("Field wwise_object_id UNIQUE constraint is not meet! ")
                results[wwise_object_id] = orm.HircObjRecord(
                    wwise_object_id,
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    set(row[3].split(","))
                )
            return results
        else:
            return [orm.HircObjRecord(int(row[0]), row[1], row[2], row[3], row[4], set(row[3].split(","))) for row in rows]

    def update_hirc_obj_labels_by_hirc_ids(
            self, labels: list[tuple[str, str]], commit: bool = False):
        """
        @exception
        - TypeError, ValueError
        - AssertionError
        - sqlite3.*Error
        """
        time.sleep(10)
        query = f"UPDATE hierarchy_object SET label = ? WHERE wwise_object_id = ?"
        self.cursor.executemany(query, labels)
        commit and self.commit()
