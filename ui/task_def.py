import enum

from dataclasses import dataclass
from collections.abc import Callable
from concurrent import futures
from typing import Any, Union

from imgui_bundle import portable_file_dialogs as pfd


class State(enum.Enum):

    pending = 0
    result = 1
    reject = 2
    cancel = 3 # highest priority


class Action[I, R]:

    def __init__(
        self,
        actor: I,
        task: Callable[..., R],
        on_cancel: Callable[..., None] | None = None,
        on_result: Union['Action[I, Any]', None] = None,
        on_reject: Callable[[BaseException | None], None] | None = None,
        state: State = State.pending,
        prev_result: Any = None,
        curr_result: R | None = None,
        err: BaseException | None = None,
    ):
        self.actor = actor
        self.task = task
        self.on_cancel = on_cancel
        self.on_result = on_result
        self.on_reject = on_reject
        self.state = state 
        self.prev_result = prev_result
        self.curr_result = curr_result
        self.err = err

    def cancel(self):
        self.state = State.cancel
        if self.on_result != None:
            self.on_result.cancel()

    def reject(
        self, 
        err: BaseException = InterruptedError(
            "Forced rejection. All subsequent actions are reject"
        )
    ):
        self.state = State.reject
        self.err = err
        if self.on_result != None:
            self.on_result.reject(err)


class UnscheudledThreadAction[I, R]:

    def __init__(
        self,
        actor: I,
        task: Callable[..., R],
        params: Any,
        on_cancel: Callable[..., None] | None = None,
        on_result: Action[I, R] | None = None,
        on_reject: Callable[[BaseException], None] | None = None,
        state: State = State.pending
    ):
        self.actor: I = actor
        self.task: Callable[..., R] = task
        self.params: Any = params
        self.on_cancel: Callable[..., None] | None = on_cancel
        self.on_result: Action[I, R] | None = on_result
        self.on_reject: Callable[[BaseException], None] | None = on_reject
        self.state: State = state

    def cancel(self):
        self.state = State.cancel
        if self.on_result != None:
            self.on_result.cancel()

    def reject(
        self, 
        err: BaseException = InterruptedError(
            "Forced rejection. All subsequent actions are reject"
        )
    ):
        self.state = State.reject
        self.err = err
        if self.on_result != None:
            self.on_result.reject(err)


class ThreadAction[I, R]:

    def __init__(
        self,
        actor: I,
        future: futures.Future[R],
        on_cancel: Callable[..., None] | None = None,
        on_result: Action[I, R] | None = None,
        on_reject: Callable[[BaseException], None] | None = None,
        state: State = State.pending,
        err: BaseException | None = None
    ):
        self.actor: I = actor
        self.future: futures.Future[R] = future
        self.on_cancel: Callable[..., None] | None = on_cancel
        self.on_result: Action[I, R] | None = on_result
        self.on_reject: Callable[[BaseException], None] | None = on_reject
        self.state = state
        self.err = err

    def cancel(self):
        self.state = State.cancel
        self.future.cancel()
        if self.on_result != None:
            self.on_result.cancel()

    def reject(
        self, 
        err: BaseException = InterruptedError(
            "Forced rejection. All subsequent actions are reject"
        )
    ):
        self.state = State.reject
        self.err = err
        self.future.cancel()
        if self.on_result != None:
            self.on_result.reject(err)


class ThreadReduceAction[I, R]:

    def __init__(
        self,
        actor: I,
        fs: list[futures.Future[R]],
        on_cancel: Callable[..., None] | None = None,
        on_result: Action[I, None] | None = None,
        on_reject: Callable[[BaseException], None] | None = None,
        state: State = State.pending,
        partial: bool = False,
        err: BaseException | None = None
    ):
        self.actor: I = actor
        self.futures: list[futures.Future[R]] = fs
        self.on_cancel: Callable[..., None] | None = on_cancel
        self.on_result: Action[I, None] | None = on_result
        self.on_reject: Callable[[BaseException], None] | None = on_reject
        self.state = state
        self.partial: bool = partial
        self.err = err

    def ready(self):
        if self.state == State.cancel or self.state == State.reject:
            return True

        for f in self.futures:
            if f.running():
                return False
        return True

    def cancel(self):
        self.state = State.cancel
        for f in self.futures:
            f.cancel()
        if self.on_result != None:
            self.on_result.cancel()

    def reject(
        self, 
        err: BaseException = InterruptedError(
            "Forced rejection. All subsequent actions are reject"
        )
    ):
        self.state = State.reject
        self.err = err
        for f in self.futures:
            f.cancel()
        if self.on_result != None:
            self.on_result.reject(err)


"""
Constraint for callback when it comes to FilePickerTask and FolderPickerTask:
    - If it require long time, scheudle it as a micro / macro / thread task
"""
@dataclass
class FilePickerAction[I]:

    actor: I
    picker: pfd.open_file
    callback: Callable[[list[str]], None]
    cancel: bool = False


@dataclass
class FolderPickerAction[I]:

    actor: I
    picker: pfd.select_folder
    callback: Callable[[str], None]
    cancel: bool = False
