import os

from backend.const import SUPPORTED_AUDIO_TYPES
from backend.core import AudioSource

from log import logger

from ui.app_state import AppState
from ui.bank_viewer.state import BankViewerState


async def target_import_database_label(
        path: str, app_state: AppState, bank_state: BankViewerState):
    hirc_views = bank_state.hirc_view_list

    pairs: dict[str, list[AudioSource]] = {}
    for hirc_view in hirc_views:
        data = hirc_view.data
        if not isinstance(data, AudioSource):
            continue

        user_defined_label = hirc_view.usr_defined_label
        if user_defined_label == "":
            continue

        if user_defined_label in pairs:
            pairs[user_defined_label].append(data)
        else:
            pairs[user_defined_label] = [data]

    if len(pairs) == 0:
        return

    filtered_pairs: dict[str, list[AudioSource]] = {}
    with os.scandir(path) as it:
        for entry in it:
            if not entry.is_file():
                continue

            name_ext, path = entry.name, entry.path

            name, ext = os.path.splitext(name_ext)
            if ext not in SUPPORTED_AUDIO_TYPES:
                logger.info("{name_ext} does not have a supported format.")
                continue
            if name in pairs:
                filtered_pairs[path] = pairs[name]

    if len(filtered_pairs) == 0:
        return
    
    # schema = create_conversion_listing_basic([(path, audio_sources) 
                                     for path, audio_sources in 
                                     filtered_pairs.items()])

    # tmp_dest = await convert_to_wem(schema)
