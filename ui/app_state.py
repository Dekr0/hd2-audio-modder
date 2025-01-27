import logging
import os
import sqlite3
import time

from collections import deque
from collections.abc import Callable
from typing import Any, Iterable

from dataclasses import dataclass

from imgui_bundle import imgui

from backend.db.db_schema_map import HircObjRecord
from backend.core import GameArchive, Mod, ModHandler, SoundHandler
from backend.db.db_access import SQLiteDatabase
from log import logger, std_formatter
from setting import Setting
from ui.bank_viewer.state import BankViewerState, ModViewerState
from ui.event_loop import EventLoop
from ui.task_def import Action, ThreadAction


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
        if imgui.button("Exit", imgui.ImVec2(-imgui.FLT_MIN, 0)):
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

    def __str__(self):
        status = f"\t# of critical modal: {len(self.critical_modal)}"
        status += f"\n\t# of warning modal: {len(self.warning_modals)}"
        status += f"\n\t# of confirm modal: {len(self.confirm_modals)}"
        return status


class AppState:

    def __init__(self, frame_rate: float = 1 / 60.0 * 1_0_0000_0000):
        self.gui_log_handler = CircularHandler()
        self.gui_log_handler.setFormatter(std_formatter)
        logger.addHandler(self.gui_log_handler)

        ModHandler.create_instance()
        self.mod_handler = ModHandler.get_instance()
        self.sound_handler = SoundHandler()

        self.db_conn_config: Callable[..., 
                                      sqlite3.Connection | None] | None = None

        self.hirc_records: dict[int, HircObjRecord] = {}

        self.setting: Setting = Setting()

        self.font: imgui.ImFont | None = None
        self.symbol_font: imgui.ImFont | None = None

        self.mod_counter: int = 0 # never decrease, used for mod initialization
        self.mod_states: dict[str, ModViewerState] = {}
        self.gc_banks: deque[str] = deque()

        self.modal_loop = ModalLoop()
        self.logic_loop = EventLoop()

        self.frame_rate = int(frame_rate)
        self.prev_timer = 0

    def start_timer(self):
        self.prev_timer = time.perf_counter_ns()

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

    def new_db_conn(self):
        if self.db_conn_config == None:
            raise AssertionError(
                "Unhandle logic check: connect database when database access is"
                " disabled.")

        return SQLiteDatabase(self.db_conn_config)

    def write_hirc_obj_records(
        self,
        bank_state: BankViewerState,
        on_write_cancel: Callable[..., None] | None = None,
        on_write_error: Callable[[BaseException], None] | None = None,
        on_write_done_cancel: Callable[..., None] | None = None,
        on_write_done_error: Callable[[Exception | None], None] | None = None,
    ):
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

        def task():
            self.new_db_conn().update_hirc_obj_labels_by_hirc_ids(
                [(label, str(hirc_ul_ID)) for hirc_ul_ID, label in muts.items()],
                True
            )

        def on_write_done():
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

                view_creation_task = Action[BankViewerState, None](
                    bank_state,
                    lambda _: bank_state.create_bank_hirc_view(self.hirc_records),
                    on_cancel = on_write_done_cancel,
                    on_reject = on_write_done_error,
                )

                self.logic_loop.queue_micro_action(view_creation_task)

        write_done_task = Action[BankViewerState, None](
            bank_state, 
            on_write_done,
            on_cancel = on_write_done_cancel,
            on_reject = on_write_done_error
        )

        db_task = self.logic_loop.queue_db_write_action(
            bank_state, 
            task, 
            on_cancel = on_write_cancel,
            on_result = write_done_task,
            on_reject = on_write_error 
        )

        return write_done_task, db_task

    def fetch_bank_hirc_obj_record[I](
        self,
        actor: I,
        bank_names: list[str], 
        on_cancel: Callable[..., None] | None = None,
        on_hirc_record_update_done_action: Action[I, Any] | None = None,
        on_reject: Callable[[BaseException | None], None] | None = None
    ):
        """
        @description
        - Schedule a database query for hierarchy object record using file names 
        of sound banks, and cache in the received record in memory.

        @params
        - on_hirc_record_update_done_action - a micro action that can be scheduled
         after a database query is finished and its record is cached in memory.

        @exception
        - AssertionError
        - sqlite3.Error
        """
        if self.db_conn_config == None:
            return

        def fetch(_) -> list[HircObjRecord]:
            conn = self.new_db_conn()
            records: list[HircObjRecord] = conn.get_hirc_objs_by_soundbank(bank_names, False)
            conn.close()

            return records

        def on_fetch_done(records: list[HircObjRecord]):
            for record in records:
                wwise_object_id = record.wwise_object_id
                if wwise_object_id in self.hirc_records:
                    continue
                self.hirc_records[wwise_object_id] = record

        fetch_action = Action[I, list[HircObjRecord]](
            actor, fetch, on_cancel = on_cancel, on_reject = on_reject
        )
        on_fetch_done_action = Action[I, None](
            actor, on_fetch_done,
            on_cancel = on_cancel, 
            on_result = on_hirc_record_update_done_action,
            on_reject = on_reject
        )
        fetch_action.on_result = on_fetch_done_action

        self.logic_loop.queue_micro_action(fetch_action)

    def create_blank_mod(self):
        new_mod_name = f"mod_{self.mod_counter}"
        if self.mod_handler.has_mod(new_mod_name):
            self.mod_counter += 1
            new_mod_name = f"mod_{self.mod_counter}"
            while self.mod_handler.has_mod(new_mod_name):
                self.mod_counter += 1
                new_mod_name = f"mod_{self.mod_counter}"

        new_mod = self.mod_handler.create_new_mod(new_mod_name)
        self.mod_states[new_mod.name] = ModViewerState(
            new_mod, BankViewerState(new_mod.get_wwise_banks())
        )

    def load_archives_as_single_new_mod(
        self,
        file_paths: list[str],
        on_cancel: Callable[..., None] | None = None,
        on_reject: Callable[[BaseException | None], None] | None = None
    ):
        """
        @description
        - Given some file paths of game archives, open them and encapsulate as 
        instances of GameArchive, store them in a new instance of Mod, and 
        create view model of this new instance of Mod

        @exception
        --
        """
        def load_archive(file_path):
            return GameArchive.from_file(file_path)

        def on_load_archives_done(new_game_archives: Iterable[GameArchive]):
            new_mod_name = f"mod_{self.mod_counter}"
            if self.mod_handler.has_mod(new_mod_name):
                self.mod_counter += 1
                new_mod_name = f"mod_{self.mod_counter}"
                while self.mod_handler.has_mod(new_mod_name):
                    self.mod_counter += 1
                    new_mod_name = f"mod_{self.mod_counter}"

            try:
                new_mod = self.mod_handler.create_new_mod(new_mod_name)
                self.mod_states[new_mod.name] = ModViewerState(
                    new_mod, BankViewerState(new_mod.get_wwise_banks())
                )

                def add_game_archive_task(game_archive: GameArchive):
                    new_mod.add_game_archive(game_archive)

                for new_game_archive in new_game_archives:
                    add_game_archive_action = Action[ModViewerState, None](
                        self.mod_states[new_mod.name], add_game_archive_task,
                        on_cancel = on_cancel, on_reject = on_reject,
                        prev_result = new_game_archive
                    )

                    self.logic_loop.queue_micro_action(add_game_archive_action)

                def on_add_game_archives_done(_):
                    bank_names: list[str] = [
                        bank.get_name().replace("/", "_").replace("\x00", "")
                        for bank in new_mod.get_wwise_banks().values()
                        if bank.hierarchy != None
                    ]

                    def on_hirc_record_update_done(_):
                        self.mod_states[new_mod.name] \
                            .bank_state.create_bank_hirc_view(new_mod, self.hirc_records)

                    on_hirc_record_update_done_action = Action[ModViewerState, None](
                        self.mod_states[new_mod.name], on_hirc_record_update_done, 
                        on_cancel = on_cancel, on_reject = on_reject
                    )

                    self.fetch_bank_hirc_obj_record(
                        self.mod_states[new_mod.name], bank_names,
                        on_cancel, on_hirc_record_update_done_action, on_reject
                    )

                on_add_game_archives_done_action = Action[ModViewerState, None](
                    self.mod_states[new_mod.name], on_add_game_archives_done,
                    on_cancel = on_cancel, on_reject = on_reject
                )

                self.logic_loop.queue_micro_action(on_add_game_archives_done_action)
            except KeyError:
                raise AssertionError(
                    "No name conflict on mod handle but name conflict on viewer"
                    " state."
                )

        on_load_archives_done_action = Action[AppState, None](
            self, on_load_archives_done,
            on_cancel = on_cancel,
            on_reject = on_reject
        )

        return self.logic_loop.queue_thread_reduce_action(
            self, load_archive, file_paths, 
            on_cancel = on_cancel, 
            on_result = on_load_archives_done_action,
            on_reject = on_reject,
        )
        

    def load_archive_as_separate_new_mods(
        self, 
        file_paths: list[str],
        on_cancel: Callable[..., None] | None = None,
        on_reject: Callable[[BaseException | Exception | None], None] | None = None
    ):
        """
        @description
        - Give some file paths of game archives, for each game archive, open it 
        as an new instance of Mod.

        @exception
        -
        """
        thread_actions: list[ThreadAction] = []
        for file_path in file_paths:
            # Threaded
            def load_archive_as_new_mod_thread():
                new_mod = Mod("")
                new_mod.load_archive_file(file_path)
                return new_mod

            # Main thread
            def load_archive_as_new_mod_thread_done(new_mod: Mod):
                new_mod.name = f"mod_{self.mod_counter}"
                if self.mod_handler.has_mod(new_mod.name):
                    self.mod_counter += 1
                    new_mod.name = f"mod_{self.mod_counter}"
                    while self.mod_handler.has_mod(new_mod.name):
                        self.mod_counter += 1
                        new_mod.name = f"mod_{self.mod_counter}"

                if new_mod.name in self.mod_states:
                    raise AssertionError(
                        "No name conflict on mod handle but name conflict on viewer"
                        " state."
                    )

                self.mod_handler.add_new_mod(new_mod.name, new_mod)
                self.mod_states[new_mod.name] = ModViewerState(
                    new_mod, BankViewerState(new_mod.get_wwise_banks())
                )

                bank_names: list[str] = [
                    bank.get_name().replace("/", "_").replace("\x00", "")
                    for bank in new_mod.get_wwise_banks().values()
                    if bank.hierarchy != None
                ]

                def on_hirc_record_update_done(_):
                    self.mod_states[new_mod.name] \
                        .bank_state.create_bank_hirc_view(new_mod, self.hirc_records)
                    logger.info(f"Loaded {os.path.basename(file_path)} as a new mod")

                on_hirc_record_done_action = Action[ModViewerState, None](
                    self.mod_states[new_mod.name],
                    on_hirc_record_update_done,
                    on_cancel = on_cancel, on_reject = on_reject
                )
                    
                self.fetch_bank_hirc_obj_record(
                    self.mod_states[new_mod.name], bank_names, 
                    on_cancel, on_hirc_record_done_action, on_reject
                )

            load_archive_as_new_mod_thread_done_action = Action[AppState, None](
                self, load_archive_as_new_mod_thread_done,
                on_cancel = on_cancel,
                on_reject = on_reject
            )

            thread_actions.append(self.logic_loop.queue_thread_action(
                self, load_archive_as_new_mod_thread, 
                on_cancel, load_archive_as_new_mod_thread_done_action, on_reject
            ))

        return thread_actions

    def load_archive_on_exist_mod(
        self, 
        file_paths: list[str],
        mod_state: ModViewerState,
        on_cancel: Callable[..., None] | None = None,
        on_reject: Callable[[BaseException | Exception | None], None] | None = None
    ):
        """
        @description
        - load some new (potential) archives into an existence mod

        @exception
        - OSError
        - sqlite3.Error
        - Exception
        """
        if mod_state.mod.name not in self.mod_states:
            raise AssertionError(
                f"Mod instance with name {mod_state.mod.name} is not tracked in "
                "list of ModViewerState."
            )

        def load_archive(file_path: str):
            return GameArchive.from_file(file_path)

        def on_load_archives_done(new_game_archives: list[GameArchive]):

            old_bank_names: set[str] = set([
                bank.get_name().replace("/", "_").replace("\x00", "")
                for bank in mod_state.mod.get_wwise_banks().values()
                if bank.hierarchy != None
            ])

            def add_game_archive(game_archive: GameArchive):
                mod_state.mod.add_game_archive(game_archive)

            for new_game_archive in new_game_archives:
                add_game_archive_action = Action[ModViewerState, None](
                    mod_state, add_game_archive, 
                    on_cancel = on_cancel, on_reject = on_reject,
                    prev_result = new_game_archive
                )
                self.logic_loop.queue_micro_action(add_game_archive_action)

            def on_add_game_archives_done(_):
                new_bank_names: set[str] = set([
                    bank.get_name().replace("/", "_").replace("\x00", "")
                    for bank in mod_state.mod.get_wwise_banks().values()
                    if bank.hierarchy != None
                ])

                diff = list(new_bank_names.difference(old_bank_names))

                def on_hirc_record_update_done(_):
                    mod_state.bank_state.create_bank_hirc_view(
                        mod_state.mod, self.hirc_records
                    )

                on_hirc_record_update_done_action = Action[ModViewerState, None](
                    mod_state, on_hirc_record_update_done, 
                    on_cancel = on_cancel, on_reject = on_reject
                )

                self.fetch_bank_hirc_obj_record(
                    mod_state, diff, 
                    on_cancel, on_hirc_record_update_done_action, on_reject
                )

            on_add_game_archives_done_action = Action[ModViewerState, None](
                mod_state, on_add_game_archives_done,
                on_cancel = on_cancel, on_reject = on_reject
            )

            self.logic_loop.queue_micro_action(on_add_game_archives_done_action)

        on_load_archives_done_action = Action[ModViewerState, None](
            mod_state, on_load_archives_done, 
            on_cancel = on_cancel, on_reject = on_reject
        )

        return self.logic_loop.queue_thread_reduce_action(
            mod_state, load_archive, file_paths, 
            on_cancel, on_load_archives_done_action, on_reject,
        )

    def run_logic_loop(self):
        exceeded = self.logic_loop.process(self.frame_rate - (time.perf_counter_ns() - self.prev_timer))
        self.process_gc_banks()
        return exceeded

    def process_modals(self):
        self.modal_loop.process_critical_modal()
        self.modal_loop.process_warning_modals()
        self.modal_loop.process_confirm_modals()

    def process_gc_banks(self):
        pass

    def queue_confirm_modal(
        self, msg: str, callback: Callable[[bool], None] | None = None
    ):
        self.modal_loop.queue_confirm_modal(msg, callback)

    def queue_critical_modal(self, msg: str, err: Exception):
        self.modal_loop.queue_critical_modal(msg, err)

    def queue_warning_modal(self, msg: str):
        self.modal_loop.queue_warning_modal(msg)

    def gc_bank(self, bank_state_id: str):
        pass

    def _gc_bank(self, bid: str):
        pass

    def __str__(self):
        status = "AppState:"
        status += f"\n\tDB access status: {'Enabled' if self.db_conn_config != None else 'Disabled'}"
        status += f"\n\t# of hierarchy records: {len(self.hirc_records)}"
        status += f"\n\tMod name counter: {self.mod_counter}"
        status += f"\n\t# of mod viewer states: {len(self.mod_states)}"

        status += "\n\nModal Loop State:"
        status += f"\n{self.modal_loop.__str__()}"

        status += "\n\nLogic Loop State:"
        status += f"\n{self.logic_loop.__str__()}"

        return status
