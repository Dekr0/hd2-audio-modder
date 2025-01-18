import sqlite3
import os

from typing import Callable

import backend.db.db_schema_map as orm


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

        if not os.path.exists(db_path):
            raise OSError(f"Database {db_path} does not exists.")

        conn = sqlite3.connect(db_path)
        return conn

    return _get_sqlite_conn

"""
All database access method will raise exception.
"""
class SQLiteDatabase:

    def __init__(self, 
                 initializer: Callable[[], sqlite3.Connection | None]):
        """
        @exception
        - Any
        """
        self.conn = initializer()
        if self.conn != None:
            self.cursor = self.conn.cursor()
        else:
            raise RuntimeError("Failed to establish database connection")

    def close(self):
        """
        @exception
        - Any
        """
        if self.conn != None:
            self.cursor.close()
            self.conn.commit()
            self.conn.close()

    def commit(self):
        if self.conn != None:
            self.conn.commit()

    def get_all_hierarchy_object_types(self) -> dict[str, str]:
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

    def get_sound_objects_by_soundbank(self, bank_name: str, as_dict: bool = False) -> dict[int, orm.SoundView] | list[orm.SoundView]:
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

    def get_hierarchy_objects_by_soundbank(self, bank_name: str, as_dict: bool = False) \
            -> dict[int, orm.HierarchyObjectView] | list[orm.HierarchyObjectView]:
        """
        @exception
        - TypeError, ValueError
        - AssertionError
        - sqlite3.*Error
        """
        query = "SELECT wwise_object_id, type_db_id, parent_wwise_object_id, label, tags, description FROM hierarchy_object_view WHERE soundbank_path_name = ?"
        rows = self.cursor.execute(query, (bank_name,))
        if as_dict:
            results: dict[int, orm.HierarchyObjectView] = {}
            for row in rows:
                wwise_object_id = int(row[0])
                if wwise_object_id in results:
                    raise AssertionError("Field wwise_object_id UNIQUE constraint is not meet! ")
                results[wwise_object_id] = orm.HierarchyObjectView(
                    wwise_object_id,
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    set(row[3].split(","))
                )
            return results
        else:
            return [orm.HierarchyObjectView(int(row[0]), row[1], row[2], row[3], row[4], set(row[3].split(","))) for row in rows]

    def update_hierarchy_object_labels_by_hierarchy_ids(
            self, labels: list[tuple[str, str]], commit: bool = False):
        """
        @exception
        - TypeError, ValueError
        - AssertionError
        - sqlite3.*Error
        """
        query = f"UPDATE hierarchy_object SET label = ? WHERE wwise_object_id = ?"
        self.cursor.executemany(query, labels)
        commit and self.commit()
