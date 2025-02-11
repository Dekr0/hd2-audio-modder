import csv
import os
import posixpath as xpath

import fileutil

from core import Mod
from log import logger


def validate_target_import_csv_row(workspace: str, row: list[str]) -> \
        tuple[str, list[int]]:
    """
    @params
    - workspace
        - POSIX absolute directory path of provided CSV file
    @return
    - tuple[str, list[int]]
        - str
            - POSIX absolut path of a wave file
        - list[int]
            - a list audio source IDs
    @exception
    - OSError
    - SyntaxError
    - TypeError
    - ValueError
    @side_effect
    - Input file path will be formatted.
        - If it misses extension, assume wave file format.
        - If it's relative path, it will join with the absolute directory path 
        of provided CSV file.
    """

    if len(row) < 2:
        raise SyntaxError(f"Less than 2 columns of values.")

    # [Check for file existence]
    from_file, target_count_str = row[0:2]
    _, ext = xpath.splitext(from_file)
    if ext == "":
        from_file += ".wav"
    elif ext != ".wav":
        raise NotImplementedError(
            "Target import automation only supports wave file format "
            "currently."
        )

    if not os.path.isabs(from_file): 
        from_file = xpath.join(workspace, from_file)

    if not os.path.exists(from_file):
        raise OSError(f"Audio file {from_file} doesn't exist.")

    # [Check for target count mismatch]
    target_count: int = 0
    target_count = int(target_count_str)

    if target_count != len(row) - 2:
        raise ValueError(
            f"The number of audio source IDs specifid mismtaches the number of "
            f"audio source ID provided. (Specified: {target_count}, Provided "
            f"{len(row) - 2})"
        )

    sids = validate_source_ids(row[2:]) 
    
    return (from_file, sids)


def validate_source_ids(sids_str: list[str]) -> list[int]:
    """
    @exception
    - TypeError -> caused by
        - string to int conversion error
    - ValueError -> caused by
        - string to int conversion error
        - An audio source ID does not have a physical audio source.
    """
    sids_set: set[int] = set()
    for c, sid_str in enumerate(sids_str, start=2):
        try:
            sid = int(sid_str)

            if sid in sids_str:
                continue

            sids_set.add(sid)
        except KeyError as err:
            logger.error(f"Error at columne {c}: {err}")

    return list(sids_set)


async def target_import_automation_csv(mod: Mod, csv_file: str):
    """
    @params
    - mod
        - an instance of Mod class
    - csv_file
        - csv script for automating on the provided Mod instance

    @exception
    - OSError
    """
    csv_file = fileutil.to_posix(csv_file, True)

    if not os.path.exists(csv_file):
        raise OSError(f"Target import CSV file {csv_file} does not exist.")

    mod.revert_all()

    workspace = xpath.dirname(csv_file)
    output = workspace

    target_import_pairs: dict[str, list[int]] = {}

    # [Validation of CSV file]
    with open(csv_file) as f:
        reader = csv.reader(f)
        line = 0
        for row in reader:
            if line == 0 and row[0] == "workspace":
                if len(row) <= 1:
                    logger.warning(
                        f"Line {line}: workspace folder path is not specified."
                    )
                else:
                    overwrite_workspace = row[1]
                    if not xpath.isabs(overwrite_workspace):
                        overwrite_workspace = fileutil.to_posix(
                            overwrite_workspace, True
                        )
                    if os.path.exists(overwrite_workspace):
                        workspace = overwrite_workspace
                    else:
                        logger.warning(
                            f"The provided workspace {overwrite_workspace} does "
                             "not exists."
                        )
            elif line == 1 and row[0] == "output":
                if len(row) <= 1:
                    logger.warning(
                        f"Line {line}: output folder path is not specified."
                    )
                else:
                    overwrite_output = row[1]
                    if not xpath.isabs(overwrite_output):
                        overwrite_workspace = fileutil.to_posix(overwrite_output, True)
                    if os.path.exists(overwrite_output):
                        output = overwrite_output
                    else:
                        logger.warning(
                            f"The provided workspace {overwrite_output} does "
                             "not exists."
                        )
            else:
                try:
                    from_file, targets = validate_target_import_csv_row(
                        workspace, row
                    )

                    if from_file in target_import_pairs:
                        left = set(target_import_pairs[from_file])
                        target_import_pairs[from_file] = list(
                            set(targets).union(left)
                        )
                    else:
                        target_import_pairs[from_file] = targets
                except (OSError, SyntaxError, TypeError, ValueError) as err:
                    logger.warning(
                        f"At line {line}: {err}. Skipping this row of target "
                         "import."
                    )

            line += 1

    await mod.import_wavs_async(target_import_pairs)

    if not os.path.exists:
        os.mkdir(os.path.exists)

    mod.write_patch(output)
