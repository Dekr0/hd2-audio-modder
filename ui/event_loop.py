from collections import deque
from collections.abc import Callable
from concurrent import futures
from dataclasses import dataclass
from typing import Any

from imgui_bundle import portable_file_dialogs as pfd

from ui.file_picker import FilePickerTask, FolderPickerTask


@dataclass
class DBOperationTask:

    issuer: Any
    future: futures.Future[None]
    callback: Callable[..., None]
    cancel: bool = False


class EventLoop:

    def __init__(self):
        self.pool = futures.ThreadPoolExecutor()
        self.db_write_task: deque[DBOperationTask] = deque(maxlen=1)
        self.file_picker_task_queue: deque[FilePickerTask] = deque()
        self.folder_picker_task_queue: deque[FolderPickerTask] = deque()
        self.micro_tasks_queue: deque[Callable[..., None]] = deque()
        self.macro_tasks_queue: deque[Callable[..., None]] = deque()


    def is_db_write_busy(self):
        return len(self.db_write_task) > 0 and not self.db_write_task[0].future.done()

    def has_issue_db_write(self, issuer: Any):
        for t in self.db_write_task:
            if t.issuer == issuer:
                return True
        return False

    def queue_file_picker_task(
        self,
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

        self.file_picker_task_queue.append(FilePickerTask(picker, callback))

    def queue_folder_picker_task(
        self,
        title: str,
        callback: Callable[[str], None], 
        default_path: str = ""):
        picker = pfd.select_folder(title, default_path)
    
        self.folder_picker_task_queue.append(FolderPickerTask(picker, callback))

    def queue_macro_task(self, task: Callable[..., None]):
        self.macro_tasks_queue.append(task)

    def queue_db_write_task(
        self, 
        issuer: Any,
        task: Callable[..., None], 
        on_finished: Callable[..., None]
    ):
        if len(self.db_write_task) <= 0:
            write_task = DBOperationTask(issuer, self.pool.submit(task), on_finished)
            self.db_write_task.append(write_task)
            return write_task
        else:
            raise AssertionError(
                "Unhandle logic check: queuing an database write operation when"
                "there's an active database write operation.")

    def process(self):
        while len(self.macro_tasks_queue) > 0:
            self.macro_tasks_queue.popleft()()

        self.process_db_write_task()
        self.process_file_picker_tasks_queue()
        self.process_folder_picker_tasks_queue()

    def process_db_write_task(self):
        if len(self.db_write_task) <= 0:
            return

        top = self.db_write_task[0]

        if top.future.done():
            self.db_write_task.popleft()

            err = top.future.exception()
            if err != None:
                raise err
            else:
                top.callback()

    def process_file_picker_tasks_queue(self):
        killed_tasks: list[FilePickerTask] = []

        for task in self.file_picker_task_queue:
            if task.cancel:
                killed_tasks.append(task)
                continue

            if task.picker.ready():
                killed_tasks.append(task)
                results = task.picker.result()
                if len(results) > 0:
                    task.callback(results)

        for killed_task in killed_tasks:
            self.file_picker_task_queue.remove(killed_task)

    def process_folder_picker_tasks_queue(self):
        killed_tasks: list[FolderPickerTask] = []
        for task in self.folder_picker_task_queue:
            if task.cancel:
                killed_tasks.append(task)
                continue

            if task.picker.ready():
                killed_tasks.append(task)
                task.callback(task.picker.result())
        for killed_task in killed_tasks:
            self.folder_picker_task_queue.remove(killed_task)

    def __str__(self):
        s = f"# of active database write operation: {len(self.db_write_task)}"
        s += f"\n# of file picker task: {len(self.file_picker_task_queue)}"
        s += f"\n# of folder picker task: {len(self.folder_picker_task_queue)}"
        s += f"\n# of macro tasks: {len(self.macro_tasks_queue)}"

        return s


