import argparse
import asyncio
import copy
import functools
import json
import subprocess
import sys
import os
import shutil
import posixpath as xpath

from concurrent.futures import ProcessPoolExecutor as Pool
from concurrent.futures import Future

import env
import target_import_csv
import target_import_json
import patch_automation as patch_automation_m
from core import Mod
from log import logger


MAX_WORKER = 8


def default_error_callback(err: BaseException):
    logger.critical(f"Unhandle exception: {err}")


def to_safe(args: argparse.Namespace):
    if args.archives == None and args.target_includes != None:
        raise RuntimeError(
            "Must include a listing of archives' file paths when using target "
            "import automation"
        ) 

    archives: list[str] = []
    if args.archives != None:
        archives: list[str] = args.archives

    target_includes: list[str] = []
    if args.target_includes != None:
        target_includes: list[str] = args.target_includes

    patch_includes: list[str] = []
    if args.patch_includes != None:
        patch_includes: list[str] = args.patch_includes

    isolated = False
    if args.isolated != None:
        isolated = args.isolated

    if args.data != None:
        env.set_data_path(args.data)

    return archives, target_includes, patch_includes, isolated


def target_import_automation_task(archive: str, target_includes: list[str]):
    """
    @param
    - archive
        - The file path / file name of an archive
    - target_includes
        - a list of target import automation scripts' file path
    """
    mod = Mod(archive)

    abort = False
    try:
        mod.load_archive_file(xpath.join(env.get_data_path(), archive))
    except OSError as err:
        logger.error(err)
        abort = True
    except BaseException as err:
        logger.critical(f"Uncaught exception: {err}")
        abort = True

    if abort:
        return

    logger.info(f"Loaded {archive}")
    for include in target_includes:
        _, ext = os.path.splitext(include)
        if ext == ".csv":
            pass
        elif ext == ".json":
            pass
        else:
            logger.error(f"Unsupported automation file schema: {include}")


def target_import_automation(
    archives: list[str],
    target_includes: list[str],
    isolated: bool,
    workers: int
):
    """
    @param
    - archives
        - a list of archives' file path
    - target_includes
        - a list of target import automation scripts' file path
    - isolated
        - True / False flag to determine whether if applying target import 
        automation scripts individual archive or applying target import 
        automation scripts after loading all archives into a Mod instance
    - workers
        - Number of processes / threads when running under isolated mode
    @return
    """
    if isolated:
        logger.info("Isolation run is work in progress")

        return

        tasks: list[Future] = []
        with Pool(workers) as p:
            for archive in archives:
                binding = functools.partial(target_import_automation_task, archive, target_includes)
                tasks.append(p.submit(binding))

            finished = 0
            while finished < len(tasks):
                for task in tasks:
                    if not task.done():
                        continue
                    finished += 1
                    err = task.exception()
                    if err != None:
                        default_error_callback(err)
    else:
        mod = Mod("main")
        data_path = env.get_data_path()
        for archive in archives:
            try:
                mod.load_archive_file(xpath.join(data_path, archive))
            except OSError as err:
                logger.error(err)
            except BaseException as err:
                logger.critical(f"Uncaught exception: {err}")
        with Pool(workers) as p:
            tasks: list[Future] = []
            for include in target_includes:
                _, ext = os.path.splitext(include)
                if ext == ".csv":
                    tasks.append(
                        p.submit(
                            functools.partial(
                                csv_entry_point, 
                                copy.deepcopy(mod), include
                            )
                        )
                    )
                elif ext == ".json":
                    tasks.append(
                        p.submit(
                            functools.partial(
                                json_entry_point,
                                copy.deepcopy(mod), include, workers
                            )
                        )
                    )
                else:
                    logger.error(f"Unsupported automation file schema: {include}")


def csv_entry_point(mod: Mod, csv_path: str):
    try:
        asyncio.run(target_import_csv.target_import_automation_csv(mod, csv_path))
    except (
        OSError, 
        ValueError, 
        subprocess.CalledProcessError,
        NotImplementedError
    ) as err:
        logger.error(err)


def json_entry_point(mod: Mod, json_path: str, workers: int):
    try:
        asyncio.run(target_import_json
                    .target_import_automation_json(mod, json_path, workers))
    except (
        OSError, 
        json.JSONDecodeError
    ) as err:
        logger.error(err)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog = "Audio Modding Tool CLI" 
    )

    target_import_group = parser.add_argument_group("target import")
    target_import_group.add_argument("--archives", type = str, nargs = "*")
    target_import_group.add_argument("--target_includes", type = str, nargs = "*")
    target_import_group.add_argument("--isolated", action = "store_true")

    parser.add_argument("--patch_includes", type = str, nargs = "*")
    parser.add_argument("--data", type = str)
    parser.add_argument("--workers", type = int, default = 8)

    args: argparse.Namespace = parser.parse_args(sys.argv[1:])
    archives, target_includes, patch_includes, isolated = to_safe(args)

    MAX_WORKER = args.workers

    if os.path.exists(env.TMP):
        shutil.rmtree(env.TMP)
    os.mkdir(env.TMP)

    with Pool(MAX_WORKER) as p:
        tasks: list[Future] = []

        if len(target_includes) > 0:
            binding = functools.partial(
                target_import_automation,
                archives, target_includes, isolated, MAX_WORKER
            )
            tasks.append(p.submit(binding))

        for patch_include in patch_includes:
            binding = functools.partial(patch_automation_m.patch_automation, patch_include)
            tasks.append(p.submit(binding))
        finished = 0

        while finished < len(tasks):
            for task in tasks:
                if not task.done():
                    continue
                finished += 1
                err = task.exception()
                if err != None:
                    default_error_callback(err)

    shutil.rmtree(env.TMP)
