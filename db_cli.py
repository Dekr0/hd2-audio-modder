import os
import uuid

import config as cfg
import db
from log import logger
from audio_modder import FileHandler, AudioSource
from audio_modder import VORBIS

def generate_audio_source_table(
        app_state: cfg.Config,
        lookup_store: db.LookupStore,
        file_handler: FileHandler,
        ):
    audio_sources: dict[int, db.OldHelldiverAudioSource] = {}
    loaded_audio_archives: set[str] = set()
    loaded_audio_archive_name_ids: set[str] = set()
    audio_archives = lookup_store.query_helldiver_audio_archive()
    for audio_archive in audio_archives:
        audio_archive_id = audio_archive.audio_archive_id
        audio_archive_name_id = audio_archive.audio_archive_name_id
        if audio_archive_id in loaded_audio_archives:
            continue
        if audio_archive_name_id in loaded_audio_archive_name_ids:
            continue
        loaded_audio_archives.add(audio_archive_id)
        loaded_audio_archive_name_ids.add(audio_archive_name_id)

        archive_file = os.path.join(app_state.game_data_path, audio_archive_id)
        file_handler.load_archive_file(archive_file=archive_file)

        banks = file_handler.get_wwise_banks()
        viewed_sources: set[int] = set()
        for bank in banks.values():
            viewed_sources.clear()
            for hierarchy_entry in bank.hierarchy.entries.values():
                for source in hierarchy_entry.sources:
                    source_id = source.source_id
                    is_vorbis = source.plugin_id == VORBIS
                    if not is_vorbis or source_id in viewed_sources:
                        continue
                    viewed_sources.add(source_id)
                    audio = file_handler.get_audio_by_id(source_id)
                    if not isinstance(audio, AudioSource):
                        continue
                    audio_id: int = audio.get_id()
                    if audio_id not in audio_sources:
                        audio_sources[audio_id] = db.OldHelldiverAudioSource(
                                audio_id, set([audio_archive_id]), set([audio_archive_name_id]))
                    else:
                        audio_sources[audio_id].linked_audio_archive_ids.add(
                                audio_archive_id)
                        audio_sources[audio_id].linked_audio_archive_name_ids.add(
                                audio_archive_name_id)
    sources = [value for _, value in audio_sources.items()]
    lookup_store.write_helldiver_audio_source_bulk(sources)

def generate_audio_bank_table(
        app_state: cfg.Config,
        lookup_store: db.LookupStore,
        file_handler: FileHandler
    ):
    game_archives = lookup_store.query_helldiver_game_archive()
    viewed_banks: dict[int, db.HelldiverAudioBank] = {}
    for game_archive in game_archives:
        archive_file = os.path.join(app_state.game_data_path, 
                                    game_archive.game_archive_id)
        if not os.path.exists(archive_file):
            continue
        file_handler.load_archive_file(archive_file=archive_file)
        banks = file_handler.get_wwise_banks()
        for bank in banks.values():
            bank_id: int = bank.get_id()
            bank_name = bank.dep.data 
            if bank_id not in viewed_banks:
                viewed_banks[bank_id] = db.HelldiverAudioBank(
                    uuid.uuid4().hex,
                    bank_id,
                    bank_name,
                    "",
                    set(),
                )
            if game_archive.id not in viewed_banks[bank_id].linked_game_archives:
                viewed_banks[bank_id].linked_game_archives.add(game_archive.id)


if __name__ == "__main__":
    app_state: cfg.Config | None = cfg.load_config()
    if app_state == None:
        exit(1)
        
    lookup_store: db.LookupStore | None = None
    if os.path.exists("hd_audio_db.db"):
        sqlite_initializer = db.config_sqlite_conn("hd_audio_db.db")
        try:
            lookup_store = db.SQLiteLookupStore(sqlite_initializer, logger)
        except Exception as err:
            logger.error("Failed to connect to audio archive database", 
                         stack_info=True)
            lookup_store = None
            exit(1)
    else:
        logger.warning("Please ensure `hd_audio_db.db` is in the same folder as \
                the executable when generating audio sources table.")
        exit(1)

    file_handler = FileHandler()
    generate_audio_bank_table(app_state, lookup_store, file_handler)
    # generate_audio_source_table(app_state, lookup_store, file_handler)
