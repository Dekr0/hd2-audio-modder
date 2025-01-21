import gc
import logging
import sqlite3

from collections import deque
from collections.abc import Callable
from typing import Any

from dataclasses import dataclass

from imgui_bundle import imgui

import backend.db.db_schema_map as orm

from backend.core import SoundHandler
from backend.db.db_access import SQLiteDatabase
from log import logger, std_formatter
from setting import Setting
from ui.event_loop import EventLoop
from ui.bank_viewer.state import BankViewerState


@dataclass 
class CriticalModalState:

    msg: str
    err: Exception
    is_trigger: bool = False


@dataclass
class MsgModalState:

    msg: str
    is_trigger: bool = False


@dataclass
class ConfirmModalState:

    msg: str
    callback: Callable[[bool], Any] | None = None
    is_trigger: bool = False


class CircularHandler(logging.Handler):
    
    def __init__(self, maxlen = 64):
        logging.Handler.__init__(self)

        self.buffer: deque[str] = deque(maxlen = maxlen)

    def emit(self, record):
        self.buffer.append(self.format(record))

    def to_string(self):
        return "\n".join(self.buffer)


class ModalLoop:

    def __init__(self):
        self.critical_modal: deque[CriticalModalState] = deque(maxlen=1)
        self.warning_modals: deque[MsgModalState] = deque()
        self.confirm_modals: deque[ConfirmModalState] = deque()

    def process_critical_modal(self):
        if len(self.critical_modal) <= 0:
            return

        top = self.critical_modal[0]

        if not top.is_trigger:
            imgui.open_popup("Critical")
            top.is_trigger = True

        ok, _ = imgui.begin_popup_modal(
                "Critical", flags = imgui.WindowFlags_.always_auto_resize.value)
        if not ok:
            return

        imgui.text(top.msg + "\nPlease check log.txt")
        if imgui.button("Exit", imgui.ImVec2(imgui.FLT_MAX, 0)):
            logger.critical(top.err)
            imgui.close_current_popup()
            imgui.end_popup()
            exit(1)

        imgui.end_popup()

    def process_warning_modals(self):
        if len(self.warning_modals) <= 0:
            return
    
        top = self.warning_modals[0]
        if not top.is_trigger:
            imgui.open_popup("Warning")
            top.is_trigger = True
    
        ok, _ = imgui.begin_popup_modal(
                "Warning", flags = imgui.WindowFlags_.always_auto_resize.value)
        if not ok:
            return
    
        imgui.text(top.msg)
        if imgui.button("OK", imgui.ImVec2(-imgui.FLT_MIN, 0)):
            imgui.close_current_popup()
            imgui.end_popup()
            self.warning_modals.popleft()
            return

        imgui.end_popup()

    def process_confirm_modals(self):
        if len(self.confirm_modals) <= 0:
            return
    
        top = self.confirm_modals[0]
        if not top.is_trigger:
            imgui.open_popup("Required Action")
            top.is_trigger = True
    
        ok, _ = imgui.begin_popup_modal(
                "Required Action", 
                flags = imgui.WindowFlags_.always_auto_resize.value)
        if not ok:
            return
    
        imgui.text(top.msg)
        callback = top.callback
    
        if imgui.button("Yes", imgui.ImVec2(128.0, 0)):
            if callback != None:
                callback(True)
            imgui.close_current_popup()
            imgui.end_popup()
            self.confirm_modals.popleft()
            return
    
        imgui.set_item_default_focus()
    
        imgui.same_line()
        if imgui.button("No", imgui.ImVec2(128.0, 0)):
            if callback != None:
                callback(False)
            imgui.close_current_popup()
            imgui.end_popup()
            self.confirm_modals.popleft()
            return
    
        imgui.same_line()
        if imgui.button("Cancel", imgui.ImVec2(128.0, 0)):
            imgui.close_current_popup()
            imgui.end_popup()
            self.confirm_modals.popleft()
            return
    
        imgui.end_popup()

    def queue_critical_modal(self, msg: str, err: Exception):
        self.critical_modal.append(CriticalModalState(msg, err))

    def queue_warning_modal(self, msg: str):
        self.warning_modals.append(MsgModalState(msg))

    def queue_confirm_modal(
        self,
        msg: str,
        callback: Callable[[bool], None] | None = None
    ):
        self.confirm_modals.append(ConfirmModalState(msg, callback))


class AppState:

    def __init__(self):
        self.gui_log_handler = CircularHandler()
        self.gui_log_handler.setFormatter(std_formatter)
        logger.addHandler(self.gui_log_handler)

        self.sound_handler = SoundHandler()

        self.db_conn_config: Callable[..., 
                                      sqlite3.Connection | None] | None = None

        self.hirc_records: dict[int, orm.HircObjRecord] = {}

        self.setting: Setting = Setting()

        self.font: imgui.ImFont | None = None
        self.symbol_font: imgui.ImFont | None = None

        self.bank_states: dict[str, BankViewerState] = {}
        self.gc_banks: deque[str] = deque()
        self.loaded_files: set[str] = set()

        self.modal_loop = ModalLoop()
        self.logic_loop = EventLoop()

    def get_symbol_font(self):
        if self.symbol_font == None:
            return imgui.get_font()
        return self.symbol_font
    
    def get_font(self):
        if self.font == None:
            return imgui.get_font()
        return self.font

    def is_db_enabled(self):
        return self.db_conn_config != None

    def is_db_write_busy(self):
        return self.logic_loop.is_db_write_busy()

    def new_db_conn(self):
        if self.db_conn_config == None:
            raise AssertionError(
                "Unhandle logic check: connect database when database access is"
                " disabled.")

        return SQLiteDatabase(self.db_conn_config)

    def has_issue_db_write(self, bank_state: BankViewerState):
        return self.logic_loop.has_issue_db_write(bank_state)

    def write_hirc_obj_records(self, bank_state: BankViewerState):
        """
        @exception
        - AssertionError
        """
        if self.db_conn_config == None:
            raise AssertionError(
                "Uncheck UI logic: perform database write when database access"
                " is disabled.")
        if self.logic_loop.is_db_write_busy():
            raise AssertionError(
                "Uncheck UI logic: perform database write when there's an active"
                " database write operation."
            )

        mut_hirc_views = bank_state.mut_hirc_views
        if len(mut_hirc_views) <= 0:
            return

        muts: dict[int, str] = {}
        for mut_hirc_view in mut_hirc_views.values():
            hirc_ul_ID = mut_hirc_view.hirc_ul_ID
            usr_defined_label = mut_hirc_view.usr_defined_label
            if hirc_ul_ID in muts:
                raise AssertionError("A hierarchy view cause more than one mutation.")
            muts[hirc_ul_ID] = usr_defined_label

        def on_finished():
            bank_state.mut_hirc_views.clear()

            for hirc_ul_ID, usr_defined_label in muts.items():
                if hirc_ul_ID not in self.hirc_records:
                    raise AssertionError(
                        "Hierarchy object record with wwise object ID "
                       f"{hirc_ul_ID} is not fetched from database."
                    )
                self.hirc_records[hirc_ul_ID].label = usr_defined_label

            for unsync in self.bank_states.values():
                if unsync.id == bank_state.id:
                    continue
                bank_state.create_bank_hirc_view(self.hirc_records)

        
        self.logic_loop.queue_db_write_task(
            bank_state,
            lambda: self.new_db_conn() \
                    .update_hirc_obj_labels_by_hirc_ids(
                        [
                            (label, str(hirc_ul_ID))
                            for hirc_ul_ID, label in muts.items()
                        ],
                        True
                    ),
            on_finished
        )

    def fetch_bank_hirc_obj_record(self, bank_state: BankViewerState):
        """
        @exception
        - AssertionError
        - sqlite3.Error
        """
        file_handler = bank_state.file_handler
        banks = file_handler.get_wwise_banks()

        if self.db_conn_config == None:
            return

        conn = self.new_db_conn()

        for bank in banks.values():
            if bank.hierarchy == None:
                continue

            bank_name = bank.get_name().replace("/", "_").replace("\x00", "")
            hirc_obj_views: list[orm.HircObjRecord] = \
                    conn.get_hirc_objs_by_soundbank(bank_name, False)

            for hirc_obj_view in hirc_obj_views:
                wwise_object_id = hirc_obj_view.wwise_object_id
                if wwise_object_id in self.hirc_records:
                    continue
                self.hirc_records[wwise_object_id] = hirc_obj_view

    def load_archive_new_viewer(self, file_path: str):
        """
        @description
        Use on creating a new bank viewer

        @exception
        - OSError
        - AssertionError
        """
        if file_path in self.loaded_files:
            return None

        new_state = BankViewerState(self.sound_handler) 

        file_handler = new_state.file_handler
        file_handler.load_archive_file(file_path)
        loaded_path = file_handler.file_reader.path
        if loaded_path != file_path:
            raise AssertionError("Path is not being normalized to POSIX standard."
                                f"Input: {file_path}; Stored: {loaded_path}")

        try:
            self.fetch_bank_hirc_obj_record(new_state)
        except (sqlite3.Error, OSError) as err:
            logger.error(err)

        new_state.create_bank_hirc_view(self.hirc_records)

        self.loaded_files.add(file_path)

        self.bank_states[new_state.id] = new_state
        self.setting.update_recent_file(file_path)

    def load_archive_exist_viewer(
        self, 
        bank_state: BankViewerState, 
        file_path: str
    ):
        """
        @description
        Use on existing bank viewer.

        @exception
        - OSError
        - sqlite3.Error
        - Exception
        """
        file_handler = bank_state.file_handler

        if file_path in self.loaded_files:
            return

        file_handler = bank_state.file_handler
        file_reader = file_handler.file_reader

        old_loaded_file_path = file_reader.path
        if old_loaded_file_path != "" and old_loaded_file_path not in self.loaded_files:
            raise AssertionError(f"File {old_loaded_file_path} is not being "
                                 "tracked in the set of loaded file.")

        file_handler.load_archive_file(file_path)
        if file_handler.file_reader.path != file_path:
            raise AssertionError("Path is not being normalized to POSIX standard."
                                 f"Input: {file_path}; Stored: {file_reader.path}")

        if old_loaded_file_path != "":
            self.loaded_files.remove(old_loaded_file_path)

        try:
            self.fetch_bank_hirc_obj_record(bank_state)
        except (sqlite3.Error, OSError) as err:
            logger.error(err)

        bank_state.create_bank_hirc_view(self.hirc_records)

        self.loaded_files.add(file_path)

    def run_logic_loop(self):
        self.logic_loop.process()
        self.process_gc_banks()

    def process_modals(self):
        self.modal_loop.process_critical_modal()
        self.modal_loop.process_warning_modals()
        self.modal_loop.process_confirm_modals()

    def process_gc_banks(self):
        num_gc_banks = len(self.gc_banks)

        while len(self.gc_banks) > 0:
            bid = self.gc_banks.popleft()

            if bid not in self.bank_states:
                raise AssertionError(
                    f"{bid} does not have an associate " "bank state.")

            self._gc_bank(bid)

        if num_gc_banks > 0:
            gc.collect()


    def queue_file_picker_task(
        self,
        title: str,
        callback: Callable[[list[str]], None],
        default_path: str = "",
        filters: list[str] | None = None,
        multi: bool = False
    ):
        self.logic_loop.queue_file_picker_task(
            title, callback, default_path, filters, multi)

    def queue_folder_picker_task(
        self,
        title: str,
        callback: Callable[[str], None], 
        default_path: str = ""
    ):
        self.logic_loop.queue_folder_picker_task(title, callback, default_path)

    def queue_macro_task(self, task: Callable[..., None]):
        self.logic_loop.queue_macro_task(task)

    def queue_confirm_modal(
        self, 
        msg: str,
        callback: Callable[[bool], None] | None = None
    ):
        self.modal_loop.queue_confirm_modal(msg, callback)

    def queue_critical_modal(self, msg: str, err: Exception):
        self.modal_loop.queue_critical_modal(msg, err)

    def queue_warning_modal(self, msg: str):
        self.modal_loop.queue_warning_modal(msg)

    def gc_bank(self, bank_state_id: str):
        """
        @exception
        - AssertionError
        """
        if bank_state_id in self.gc_banks:
            raise AssertionError(f"Garbage collect bank {bank_state_id} more than once!")

        if bank_state_id not in self.bank_states:
            raise AssertionError(f"Bank {bank_state_id} does not exist!")
        
        self.gc_banks.append(bank_state_id)

    def _gc_bank(self, bid: str):
        bank_state = self.bank_states.pop(bid)
        file_path = bank_state.file_handler.file_reader.path

        if file_path == "":
            return

        if file_path not in self.loaded_files:
            raise AssertionError(
                    f"File {file_path} is not being tracked in the list of "
                    "loaded file.")

        self.loaded_files.remove(file_path)

    def __str__(self):
        s = f"# of bank states: {len(self.bank_states)}"
        for bid, state in self.bank_states.items():
            s += f"\n    {bid}: {state.file_handler.file_reader.path}"
        s += f"\n# of loaded file: {len(self.loaded_files)}"
        for p in self.loaded_files:
            s += f"\n    {p}"
        s += f"\n# of gc banks: {len(self.gc_banks)}"
        return s
