"""
This is a callback based event loop. It most likely to be a very bad design.
"""

import time

from collections import deque
from collections.abc import Callable
from concurrent import futures
from typing import Any, Iterable

from imgui_bundle import portable_file_dialogs as pfd

from log import logger
from ui.task_def import FilePickerAction, FolderPickerAction, ThreadReduceAction
from ui.task_def import Action, ThreadAction 
from ui.task_def import State


class EventLoop:

    def __init__(self, deadline: float = 1 / 144.0 * 1_0_0000_0000):
        """
        @params
        - deadline: the deadline for each iteration of the event loop (including
        time for input polling and rendering)
            -> default to 1 second / 120 frame ~= 0.0083 sec -> 8300000 ns
        """
        self.pool = futures.ThreadPoolExecutor()
        self.event_actions: deque[Action] = deque()
        self.file_picker_actions: deque[FilePickerAction] = deque()
        self.folder_picker_actions: deque[FolderPickerAction] = deque()
        self.micro_actions: deque[Action] = deque()
        self.thread_actions: deque[ThreadAction] = deque()
        self.thread_reduce_actions: deque[ThreadReduceAction] = deque()
        self.db_write_action: deque[ThreadAction] = deque(maxlen=1)
        self.deadline = deadline
        self.deadline_exceed_counter = 0

    def is_idle(self):
        total_actions = len(self.event_actions) + \
                        len(self.file_picker_actions) + \
                        len(self.folder_picker_actions) + \
                        len(self.micro_actions) + \
                        len(self.thread_actions) + \
                        len(self.thread_reduce_actions) + \
                        len(self.db_write_action)
        return total_actions <= 0

    def is_db_write_busy(self):
        return len(self.db_write_action) > 0 and not self.db_write_action[0].future.done()

    def get_event_by_actor(self, actor: Any):
        return deque([e for e in self.event_actions if actor == e.actor])

    def get_micro_action_by_actor(self, actor: Any):
        return deque([ma for ma in self.micro_actions if actor == ma.actor])

    def get_thread_actions_by_actor(self, actor: Any):
        return deque([ta for ta in self.thread_actions if actor == ta.actor])

    def get_thread_action_reduces_by_actor(self, actor: Any):
        return deque([r for r in self.thread_reduce_actions if actor == r.actor])

    def cancel_all_event_action_by_actor(self, actor: Any):
        for a in self.event_actions:
            if a.actor == actor:
                a.state = State.cancel
                a.cancel()

    def cancel_all_micro_actions_by_actor(self, actor: Any):
        for a in self.micro_actions:
            if a.actor == actor:
                a.state = State.cancel
                a.cancel()

    def cancel_all_thread_actions_by_actor(self, actor: Any):
        all_cancelled = True
        for a in self.thread_actions:
            if a.actor == actor:
                if not a.future.cancel():
                    all_cancelled = False
                a.cancel()
        return all_cancelled

    def cancel_all_thread_action_reduces_by_actor(self, actor: Any):
        all_cancelled = True
        for g in self.thread_reduce_actions:
            if g.actor == actor:
                if not g.cancel():
                    all_cancelled = False
        return all_cancelled

    def cancel_db_write_action_by_actor(self, actor: Any):
        cancelled = True
        for a in self.db_write_action:
            if a.actor == actor:
                if not a.future.cancel():
                    cancelled = False
                a.cancel()
        return cancelled

    def cancel_all_actions_by_actor(self, actor: Any):
        all_cancelled = True
        self.cancel_all_event_action_by_actor(actor)
        self.cancel_all_micro_actions_by_actor(actor)
        if not self.cancel_all_thread_actions_by_actor(actor):
            all_cancelled = False
        if not self.cancel_db_write_action_by_actor(actor):
            all_cancelled = False
        return all_cancelled

    def has_issue_event(self, actor: Any):
        for e in self.event_actions:
            if actor == e.actor:
                return True
        return False

    def has_issue_micro_action(self, actor: Any):
        for a in self.micro_actions:
            if actor == a.actor:
                return True
            return False

    def has_issue_macro_action(self, actor: Any):
        for a in self.micro_actions:
            if actor == a.actor:
                return True
            return False

    def has_issue_thread_action(self, actor: Any):
        for ta in self.thread_actions:
            if actor == ta.actor:
                return True
            return False

    def has_issue_file_picker(self, action: Any):
        for a in self.file_picker_actions:
            if a.actor == action:
                return True
        return False

    def has_issue_folder_picker(self, action: Any):
        for a in self.folder_picker_actions:
            if a.actor == action:
                return True
        return False

    def has_issue_db_write_action(self, actor: Any):
        for a in self.db_write_action:
            if a.actor == actor:
                return True
        return False

    def queue_file_picker_action[I](
        self,
        actor: I,
        title: str,
        callback: Callable[[list[str]], None],
        default_path: str = "",
        filters: list[str] | None = None,
        multi: bool = False
    ):
        options = pfd.opt.none
        if multi:
            options = pfd.opt.multiselect
    
        picker = pfd.open_file(title, default_path, filters, options)

        self.file_picker_actions.append(FilePickerAction[I](actor, picker, callback))

        logger.debug("Queued a file picker action")

    def queue_folder_picker_action[I](
        self,
        actor: I,
        title: str,
        callback: Callable[[str], None], 
        default_path: str = ""):
        picker = pfd.select_folder(title, default_path)
    
        self.folder_picker_actions.append(FolderPickerAction[I](actor, picker, callback))

        logger.debug("Queued a folder picker action")

    def queue_event[I, R](self, e: Action[I, R]):
        self.event_actions.append(e)

        logger.debug("Queued a event action")

    def queue_micro_action[I, R](self, t: Action[I, R]):
        self.micro_actions.append(t)

        logger.debug("Queued a micro action")

    def queue_thread_action[I, R](
        self,
        actor: I,
        task: Callable[..., R],
        on_cancel: Callable[..., None] | None = None,
        on_result: Action[I, Any] | None = None,
        on_reject: Callable[[BaseException], None] | None = None,
        state: State = State.pending,
    ):
        t = ThreadAction(
            actor, self.pool.submit(task), on_cancel, on_result, on_reject, state
        )

        self.thread_actions.append(t)

        logger.debug("Queued a thread action")
        
        return t

    def queue_thread_reduce_action[I, R](
        self,
        actor: I,
        task: Callable[..., R],
        iterable: Iterable,
        on_cancel: Callable[..., None] | None = None,
        on_result: Action[I, Any] | None = None,
        on_reject: Callable[[BaseException], None] | None = None,
        state: State = State.pending,
        partial: bool = True
    ):
        fs: list[futures.Future[R]] = []

        for i in iterable:
            fs.append(self.pool.submit(lambda: task(i)))

        r = ThreadReduceAction(actor, fs, on_cancel, on_result, on_reject, state, partial)

        self.thread_reduce_actions.append(r)

        logger.debug("Queued a thread reduce action")

        return r

    def queue_db_write_action[I](
        self, 
        actor: I,
        task: Callable[..., None],
        on_cancel: Callable[..., None] | None = None,
        on_result: Action | None = None,
        on_reject: Callable[[BaseException], None] | None = None,
        state: State = State.pending,
    ):
        if len(self.db_write_action) > 0:
            raise AssertionError(
                "Unhandle logic check: queuing an database write operation when "
                "there's an active database write operation."
            )

        t = ThreadAction(
            actor, self.pool.submit(task), on_cancel, on_result, on_reject, state
        )

        self.db_write_action.append(t)

        logger.debug("Queued a DB write action")

        return t

    def process(self, remain: int):
        # [Thread Action]
        prev = time.perf_counter_ns()

        if len(self.thread_actions) > 0:
            self.process_thread_actions()
            curr = time.perf_counter_ns()
            remain -= curr - prev
            prev = curr
        if remain <= 0:
            self.deadline_exceed_counter += 1
            # logger.warning(f"Deadline exceeded (by {-remain} ns) after processing thread actions."
            #                f" Remain thread actions: {len(self.thread_actions)}."
            #                " Abort current loop...")
            return False

        # [Thread Action Reduce]
        if len(self.thread_reduce_actions) > 0:
            self.process_thread_action_reduces()
            curr = time.perf_counter_ns()
            remain -= curr - prev
            prev = curr
        if remain <= 0:
            self.deadline_exceed_counter += 1
            # logger.warning(f"Deadline exceeded (by {-remain} ns) after processing thread reduces."
            #                f" Remain thread reduces: {len(self.thread_reduce_actions)}."
            #                " Abort current loop...")
            return False

        # [DB Write Action]
        if len(self.db_write_action) > 0:
            self.process_db_write_action()
            curr = time.perf_counter_ns()
            remain -= curr - prev
            prev = curr
        if remain <= 0:
            self.deadline_exceed_counter += 1
            # logger.warning(f"Deadline exceeded (by {-remain} ns) after processing DB write action. Abort current loop...")
            return False

        # [Event Actions]
        if len(self.event_actions) > 0:
            self.process_event_actions()
            curr = time.perf_counter_ns()
            remain -= curr - prev
            prev = curr
        if remain <= 0:
            self.deadline_exceed_counter += 1
            # logger.warning(f"Deadline exceeded (by {-remain} ns) after processing event actions."
            #                f" Remain event actions: {len(self.event_actions)}."
            #                " Abort current loop...")
            return False

        # [Micro Actions]
        if len(self.micro_actions) > 0:
            remain = self.process_micro_actions(remain)
            prev = time.perf_counter_ns()
        if remain <= 0:
            self.deadline_exceed_counter += 1
            # logger.warning(f"Deadline exceeded (by {-remain} ns) after processing micro actions."
            #                f" Remain micro actions: {len(self.micro_actions)}."
            #                " Abort current loop...")
            return False

        # [File Picker]
        if len(self.file_picker_actions) > 0:
            self.process_file_picker_actions()
            curr = time.perf_counter_ns()
            remain -= curr - prev
            prev = curr
        if remain <= 0:
            self.deadline_exceed_counter += 1
            # logger.warning(f"Deadline exceeded (by {-remain} ns) after processing file picker actions."
            #                f" Remain file picker actions: {len(self.file_picker_actions)}."
            #                " Abort current loop...")
            return False

        # [Folder Picker]
        if len(self.folder_picker_actions) > 0:
            self.process_folder_picker_actions()
            curr = time.perf_counter_ns()
            remain -= curr - prev
            prev = curr
        if remain <= 0:
            self.deadline_exceed_counter += 1
            # logger.warning(f"Deadline exceeded (by {-remain} ns) after processing folder picker actions."
            #                f" Remain folder picker actions: {len(self.folder_picker_actions)}."
            #                " Abort current loop...")
            return False

        return True

    def process_event_actions(self):
        processed = 0
        while len(self.event_actions) > 0:
            top = self.event_actions.popleft()
            processed += 1

            """
            An actor marks an action explicitly.
            """
            # Cancel all subsequent actions
            if top.state == State.cancel:
                top.cancel()
                if top.on_cancel != None:
                    top.on_cancel(None)
                continue

            # Reject all subsequent actions
            if top.state == State.reject:
                if top.err != None:
                    top.reject(top.err)
                else:
                    top.reject()
                if top.on_reject != None:
                    top.on_reject(top.err)
                continue

            if top.state == State.result and top.on_result != None:
                top.on_result.prev_result = top.curr_result
                self.event_actions.appendleft(top.on_result)
                continue
            """
            End
            """

            try:
                result = top.task(top.prev_result)
                top.curr_result = result
                top.state = State.result
                if top.on_result != None:
                    top.on_result.prev_result = top.curr_result
                    self.event_actions.appendleft(top.on_result)
            except Exception as err:
                top.state = State.reject
                top.err = err
                top.reject(err)
                if top.on_reject != None:
                    top.on_reject(err)

        logger.debug(f"Processed {processed} event actions. "
                     f"{len(self.event_actions)} remains")

    def process_micro_actions(self, remain: int) -> int:
        prev = time.perf_counter_ns()
        processed = 0
        while len(self.micro_actions) > 0 and remain > 0:
            top = self.micro_actions.popleft()
            processed += 1
            
            """
            An actor marks an action explicitly
            """
            # Cancel all subsequent actions
            if top.state == State.cancel:
                top.cancel()
                if top.on_cancel != None:
                    top.on_cancel(None)
                continue

            # Reject all subsequent actions
            if top.state == State.reject:
                if top.err != None:
                    top.reject(top.err)
                else:
                    top.reject()
                if top.on_reject != None:
                    top.on_reject(top.err)
                continue

            if top.state == State.result and top.on_result != None:
                top.on_result.prev_result = top.curr_result
                self.micro_actions.appendleft(top.on_result)
                continue
            """
            End
            """

            try:
                result = top.task(top.prev_result)
                top.curr_result = result
                top.state = State.result
                if top.on_result != None:
                    top.on_result.prev_result = top.curr_result
                    self.micro_actions.appendleft(top.on_result)
            except Exception as err:
                top.state = State.reject
                top.err = err
                top.reject(err)
                if top.on_reject != None:
                    top.on_reject(err)

            curr = time.perf_counter_ns()
            remain -= curr - prev
            prev = curr

        logger.debug(f"Processed {processed} micro actions. "
                     f"{len(self.micro_actions)} remains")

        return remain

    def process_thread_actions(self):
        removes: list[ThreadAction] = []
        for action in self.thread_actions:
            """
            An actor marks on action explicitly
            """
            # Cancel all subsequent actions
            if action.state == State.cancel:
                removes.append(action)
                action.future.cancel()
                action.cancel()
                if action.on_cancel != None:
                    action.on_cancel()
                continue

            # Reject all subsequent actions
            if action.state == State.reject:
                removes.append(action)
                action.future.cancel()
                if action.err != None:
                    action.reject(action.err)
                else:
                    action.reject()
                if action.on_reject != None:
                    if action.err == None:
                        action.err = InterruptedError(
                            "Forced rejection. All subsequent actions are reject"
                        )
                    action.on_reject(action.err)
                continue
            """
            End
            """

            if action.future.running():
                continue

            removes.append(action)

            if action.future.cancelled():
                action.state = State.cancel
                action.cancel()
                if action.on_cancel != None:
                    action.on_cancel()
                continue

            err = action.future.exception()
            if err != None:
                action.state = State.reject
                action.reject(err)
                if action.on_reject != None:
                    action.on_reject(err)
                continue

            result = action.future.result()
            action.state = State.result
            if action.on_result == None:
                continue

            action.on_result.prev_result = result
            self.micro_actions.append(action.on_result)

        for remove in removes:
            self.thread_actions.remove(remove)

        logger.debug(f"Processed {len(removes)} thread actions. "
                     f"{len(self.thread_actions)} remains")

    def process_thread_action_reduces(self):
        removes: list[ThreadReduceAction] = []
        for reduce in self.thread_reduce_actions:
            """
            An actor marks an action explicitly
            """
            # Cancel all subsequent actions
            if reduce.state == State.cancel:
                removes.append(reduce)
                reduce.cancel()
                if reduce.on_cancel != None:
                    reduce.on_cancel()
                continue

            # Reject all subsequent actions
            if reduce.state == State.reject:
                removes.append(reduce)
                if reduce.err != None:
                    reduce.reject(reduce.err)
                else:
                    reduce.reject()
                if reduce.on_reject != None:
                    if reduce.err == None:
                        reduce.err = InterruptedError(
                            "Forced rejection. All subsequent actions are reject"
                    )
                    reduce.on_reject(reduce.err)
                continue
            """
            End
            """

            if not reduce.ready():
                continue

            removes.append(reduce)

            results: list = []
            if reduce.partial:
                for f in reduce.futures:
                    if f.cancel() and reduce.on_cancel != None:
                        reduce.on_cancel()
                        continue

                    err = f.exception()
                    if err != None and reduce.on_reject != None:
                        reduce.on_reject(err)
                        continue

                    results.append(f.result())
            else:
                for f in reduce.futures:
                    if f.cancel():
                        reduce.state = State.cancel
                        reduce.cancel()
                        if reduce.on_cancel != None:
                            reduce.on_cancel()
                        return

                    err = f.exception()
                    if err != None:
                        reduce.state= State.reject
                        reduce.reject(err)
                        if reduce.on_reject != None:
                            reduce.on_reject(err)
                        return

                    results.append(f.result())

            reduce.state = State.result

            if reduce.on_result == None:
                continue

            reduce.on_result.prev_result = results
            self.micro_actions.append(reduce.on_result)

        for remove in removes:
            self.thread_reduce_actions.remove(remove)

        logger.debug(f"Processed {len(removes)} thread reduce actions. "
                     f"{len(self.thread_reduce_actions)} remains")

    def process_db_write_action(self):
        top = self.db_write_action[0]

        """
        An actor marks an action explicitly
        """
        # Cancel all subsequent actions
        if top.state == State.cancel:
            top.cancel()
            if top.on_cancel != None:
                top.on_cancel()
            return

        # Reject all subsequent actions
        if top.state == State.reject:
            top.cancel()
            if top.err != None:
                top.reject(top.err)
            else:
                top.reject()
            if top.on_reject != None:
                if top.err == None:
                    top.err = InterruptedError(
                        "Forced rejection. All subsequent actions are reject"
                    )
                top.on_reject(top.err)
            return

        if top.future.running():
            return

        action = self.db_write_action.popleft()
        if action.future.cancelled():
            action.state = State.cancel
            action.cancel()
            if action.on_cancel != None:
                action.on_cancel()
            return

        err = action.future.exception()
        if err != None:
            action.state = State.reject
            action.reject(err)
            if action.on_reject != None:
                action.on_reject(err)
            return

        action.state = State.result
        if top.on_result == None:
            return

        self.micro_actions.append(top.on_result)

    def process_file_picker_actions(self):
        actions: list[FilePickerAction] = []

        for action in self.file_picker_actions:
            if action.cancel:
                actions.append(action)
                continue

            if action.picker.ready():
                actions.append(action)
                results = action.picker.result()
                if len(results) > 0:
                    action.callback(results)

        for action in actions:
            self.file_picker_actions.remove(action)

        logger.debug(f"Processed {len(actions)} file picker actions. "
                     f"{len(self.file_picker_actions)} remains")

    def process_folder_picker_actions(self):
        actions: list[FolderPickerAction] = []
        for action in self.folder_picker_actions:
            if action.cancel:
                actions.append(action)
                continue

            if action.picker.ready():
                actions.append(action)
                action.callback(action.picker.result())

        for action in actions:
            self.folder_picker_actions.remove(action)

        logger.debug(f"Processed {len(actions)} folder picker actions. "
                     f"{len(self.folder_picker_actions)} remains")

    def __str__(self):
        s = f"\t# of event action: {len(self.event_actions)}"
        s += f"\n\t# of micro action: {len(self.micro_actions)}"
        s += f"\n\t# of threaded action: {len(self.thread_actions)}"
        s += f"\n\t# of active database write action: {len(self.db_write_action)}"
        s += f"\n\t# of file picker action: {len(self.file_picker_actions)}"
        s += f"\n\t# of folder picker action: {len(self.folder_picker_actions)}"
        s += f"\n\tDeadline exceed count: {self.deadline_exceed_counter}"

        return s
