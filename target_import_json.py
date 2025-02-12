import asyncio
import copy
import functools
import os
import json
import subprocess
import jsonschema
import posixpath as xpath

from concurrent.futures import ProcessPoolExecutor as Pool
from concurrent.futures import Future
from typing import Any

import target_import_schema

from env import DEFAULT_WWISE_PROJECT
from core import Mod
from fileutil import to_posix
from log import logger


def default_error_callback(err: BaseException):
    logger.critical(f"Unhandle exception: {err}.")


async def target_import_automation_json(
    mod: Mod, manifest_path: str, workers: int = 8
):
    """
    @params
    - mod
        - an instance of Mod
    - manifest_path

    @exception
    - OSError
    - json.JSONDecodeError

    @notes
    - Target import automation does not support set duration yet.
    """
    if len(mod.wwise_banks) <= 0:
        return

    if not os.path.exists(manifest_path):
        raise OSError(f"{manifest_path} does not exist")

    manifest: dict[str, Any] = {}
    try:
        with open(manifest_path, "rb") as f:
            manifest = json.load(f)
    except json.JSONDecodeError as jerr:
        # Reformat
        raise json.JSONDecodeError(f"Target import manifest file {manifest_path} "
                                   "has malformed syntax", jerr.doc, jerr.pos)

    jsonschema.validate(manifest, target_import_schema.manifest_schema) 
    tasks = manifest["tasks"]
    if len(tasks) == 1:
        await target_import_task(mod, tasks[0])
        return
    
    isolated_tasks: list[Future] = []
    sequence_tasks: list[dict] = []

    with Pool(workers) as p:
        for task in tasks:
            if task["revert_all"]["after"]:
                binding = functools.partial(
                    target_import_task_process,
                    copy.deepcopy(mod), task,
                )
                isolated_tasks.append(p.submit(binding))
            else:
                sequence_tasks.append(task)

        for task in sequence_tasks:
            try:
                await target_import_task(mod, task)
            except BaseException as err:
                logger.critical(f"Unhandle exception: {err}")
                mod.revert_all()

        finished = 0
        while finished < len(isolated_tasks):
            for task in isolated_tasks:
                if not task.done():
                    continue
                finished += 1
                err = task.exception()
                if err != None:
                    default_error_callback(err)


def target_import_task_process(mod: Mod, task: dict):
    asyncio.run(target_import_task(mod, task))


async def target_import_task(mod: Mod, task: dict):
    """
    @params
    - mod
        - an instance of Mod
    - task
        - a target import task

    @exception
    - @extract_target_import_pairs
    """
    revert_before: bool = task["revert_all"]["before"]
    revert_after: bool = task["revert_all"]["after"]
    write_patch_to: str = task["write_patch_to"]
    wwise_project = ""

    if "wwise_project" not in task:
        wwise_project = DEFAULT_WWISE_PROJECT
    else:
        wwise_project = task["wwise_project"]
        if not os.path.exists(wwise_project):
            logger.warning(
                f"The provided wwise project {wwise_project} does not exist. "
                 "Using the default wwise project from audio modding tool."
            )
            wwise_project = DEFAULT_WWISE_PROJECT

    wavs = extract_target_import_pairs(task["target_imports"])

    if revert_before:
        mod.revert_all()

    abort = False 
    try:
        await mod.import_wavs_async(wavs)
    except (
        ValueError, 
        subprocess.CalledProcessError, 
        NotImplementedError
    ) as err:
        logger.error(err)
        abort = True

    if abort:
        return

    if write_patch_to != "":
        try:
            if not os.path.exists(write_patch_to):
                os.mkdir(write_patch_to)
            mod.write_patch(write_patch_to)
        except OSError as err:
            logger.error(err)

    if revert_after:
        mod.revert_all()


def extract_target_import_pairs(target_imports: dict):
    """
    @return
    - dict[str, list[int]]
        - str: absolute
    @exception
    - AssertionError
    """
    stack: list[dict] = []

    wavs: dict[str, list[int]] = {}

    for target_import in target_imports:
        if len(stack) > 0:
            raise AssertionError(
                "Previous target import parsing is not complete.")

        stack.append(target_import)

        while len(stack) > 0:
            top = stack.pop()

            workspace = to_posix(top["workspace"])
            folders = top["folders"]

            # Recursive Case
            if len(folders) > 0:
                for folder in folders:
                    # Attach child workspace path with parent workspace path
                    folder["workspace"] = xpath.join(
                        workspace, to_posix(folder["workspace"])
                    )
                    stack.append(folder)

            pairs = top["pairs"]
            for pair in pairs:
                from_file: str = xpath.join(workspace, to_posix(pair["from"]))

                _, ext = xpath.splitext(from_file)

                # Attach missing wave file format extension
                if ext == "":
                    from_file += ".wav"
                elif ext != ".wav":
                    logger.warning(
                        f"Target import {pair} fail. Reason: Target import "
                         "automation only supports wave file format currently."
                    )
                    continue

                if not os.path.exists(from_file):
                    logger.warning(
                        f"Target import {pair} fail. Reason: {from_file} does "
                         "not exists."
                    )
                    continue

                to: list[int] = pair["to"]
                from_file = to_posix(from_file, True)
                if from_file in wavs:
                    wavs[from_file] = list(set(wavs[from_file]).union(set(to)))
                else:
                    wavs[from_file] = to

    return wavs
