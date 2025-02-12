import asyncio
import copy
import functools
import os
import json
import jsonschema
import posixpath as xpath

from core import Mod
from concurrent.futures import ProcessPoolExecutor as Pool, Future
from typing import Any

import env
import fileutil
import target_import_csv
import target_import_json
import patch_automate_schema

from log import logger


def default_error_callback(err: BaseException):
    logger.critical(f"Unhandle exception: {err}")


def patch_automation(manifest_path: str):
    """
    @exception (in order)
    - OSError
        - path specified by manifest_path does not exist
    - JSONDecodeError
    - jsonschema.ValidationError
        - Manifest validation fails
    - ValueError
    - RuntimeError
        - No valid task is available to run
    """
    if not os.path.exists(manifest_path):
        raise OSError(
            f"Patch automation manifest file {manifest_path} does not exist."
        )

    manifest: dict[str, Any] = {}
    with open(manifest_path, "rb") as f:
        manifest = json.load(f)

    jsonschema.validate(manifest, patch_automate_schema.manifest_schema)

    workers = 8
    if "workers" in manifest:
        workers = manifest["workers"]
        if workers <= 0 and workers >= 64:
            raise ValueError("Invalid number for number of worker processes")
        

    with Pool(workers) as p:
        tasks: list[Future] = [
            p.submit(functools.partial(patch_automation_task, workers, task))
            for task in manifest["tasks"]
        ]
        finished = 0
        while finished < len(tasks):
            for task in tasks:
                if not task.done():
                    continue
                finished += 1
                err = task.exception()
                if err != None:
                    default_error_callback(err)


def patch_automation_task(workers: int, task: dict):
    """
    @exception (in order)
    """
    archives, includes = validate_task(task)

    if task["merge"]:
        mod = Mod("")
        for archive_file in archives:
            try:
                mod.load_archive_file(archive_file)
            except OSError as err:
                logger.error(err)
            except BaseException as err:
                logger.critical(f"Unhandle exception: {err}")

        with Pool(workers) as p:
            tasks: list[Future] = []
            for include in includes:
                _, ext = os.path.splitext(include) 
                if ext == ".csv":
                    binding = functools.partial(
                        csv_entry_point, copy.deepcopy(mod), include
                    )
                    tasks.append(p.submit(binding))
                elif ext == ".json":
                    binding = functools.partial(
                        json_entry_point, copy.deepcopy(mod), include, workers
                    )
                    tasks.append(p.submit(binding))
    else:
        with Pool(workers) as p:
            tasks: list[Future] = []
            for archive in archives:
                binding = functools.partial(
                    patch_automation_target_import_split,
                    archive, includes, workers
                )
                tasks.append(p.submit(binding))

            finished = 0
            while finished < len(tasks):
                for t in tasks:
                    if not t.done():
                        continue
                    finished += 1
                    err = t.exception()
                    if err != None:
                        default_error_callback(err)


def patch_automation_target_import_split(
    archive_file: str, 
    includes: set[str], 
    workers: int
):
    """
    @exception
    - OSError
    """
    mod = Mod("")

    mod.load_archive_file(archive_file)

    with Pool(workers) as p:
        tasks: list[Future] = []
        for include in includes:
            _, ext = os.path.splitext(include) 
            if ext == ".csv":
                binding = functools.partial(
                    csv_entry_point, copy.deepcopy(mod), include
                )
                tasks.append(p.submit(binding))
            elif ext == ".json":
                binding = functools.partial(
                    json_entry_point, copy.deepcopy(mod), include, workers
                )
                tasks.append(p.submit(binding))
        
        finished = 0
        while finished < len(tasks):
            for task in tasks:
                if not task.done:
                    continue
                finished += 1
                err = task.exception()
                if err != None:
                    default_error_callback(err)
        

def csv_entry_point(mod: Mod, csv_path: str):
    try:
        asyncio.run(target_import_csv.target_import_automation_csv(mod, csv_path))
    except OSError as err:
        logger.error(err)


def json_entry_point(mod: Mod, manifest_path: str, workers: int):
    try:
        asyncio.run(target_import_json
                    .target_import_automation_json(mod, manifest_path, workers))
    except (OSError, json.JSONDecodeError) as err:
        logger.error(err)


def validate_task(task: dict) -> tuple[set[str], set[str]]:
    """
    @exception
    - OSError
    - ValueError
    """
    data = ""
    if "data" not in task:
        logger.warning(
            "The file path for archive files lookup does not exist. Using data "
            "directory for Helldivers 2 for archive files lookup instead..."
        )

        data = env.get_data_path() 
        if data == "":
            raise OSError(
                "HD2DATA enviromental variable is not set. Archive files lookup "
                "source is not available."
            )
    else:
        data = fileutil.to_posix(task["data"], True)
        if not os.path.exists(task["data"]):
            raise OSError(
                "HD2DATA enviromental variable is not set. Archive files lookup "
                "source is not available."
            )

    archives: set[str] = set()
    for archive in task["archives"]:
        archive = xpath.join(data, archive)
        if not os.path.exists(archive):
            logger.warning(f"Archive file {archive} does not exists.")
        archives.add(archive)

    if len(archives) <= 0:
        raise ValueError(f"No archive file is provided.")

    workspace = ""
    if "workspace" in task:
        workspace = task["workspace"]
        if not os.path.exists(workspace):
            raise OSError(
                f"The provided workspace {workspace} for target import "
                 " automation manifest does not exist."
            )

    includes: set[str] = set()
    for include in task["includes"]:
        include = xpath.join(workspace, include)
        if not os.path.exists(include):
            logger.warning(
                f"The provided target import automation manifest {include}"
                 " does not exist."
            )
            continue
        includes.add(include)

    if len(includes) <= 0:
        raise ValueError("No target import automation manifest is provided.")

    return archives, includes
