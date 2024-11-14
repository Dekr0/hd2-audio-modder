import os
import uuid

import config as cfg
import db
from log import logger
from audio_modder import FileHandler, AudioSource
from audio_modder import VORBIS

def generate(
        app_state: cfg.Config,
        lookup_store: db.LookupStore,
        file_handler: FileHandler
    ):
    game_archives = lookup_store.query_helldiver_game_archive_by_category()

    """
    A soundbank might appear in multiple different game archives.
    """
    viewed_banks: dict[int, db.HelldiverSoundbank] = {}

    """
    An audio source might appear in multiple different soundbanks.
    Since a soundbank might appear in multiple different game archives, an audio
    source might appear in multiple different game archives across the board.
    """
    viewed_audio_sources: dict[int, db.HelldiverAudioSource] = {}

    """
    Visit each game archive. The game archives return from DB are unique. No 
    need to check for duplication visit.
    """
    for game_archive in game_archives:
        archive_file = os.path.join(app_state.game_data_path, 
                                    game_archive.game_archive_id)
        if not os.path.exists(archive_file):
            continue
        file_handler.load_archive_file(archive_file=archive_file)
        banks = file_handler.get_wwise_banks()

        """
        Within a single game archive, it might have more than one soundbank. 
        If so, these soundbanks might include some audio sources that are shared 
        among them.
        """
        viewed_sources: set[int] = set()
        for bank in banks.values():
            bank_id: int = bank.get_id()
            bank_name = bank.dep.data

            if bank_id not in viewed_banks:
                viewed_banks[bank_id] = db.HelldiverSoundbank(
                    uuid.uuid4().hex,
                    bank_id,
                    bank_name,
                    "",
                    set(),
                    set([game_archive.game_archive_id])
                )
            else:
                viewed_banks[bank_id].linked_game_archive_ids.add(
                        game_archive.game_archive_id)
                continue

            """
            Within a single Wwise Soundbank, its structure is a Hirearchy. The 
            hirearchy contains multiple (Hirearchy) entries.

            A entry can be leaf level entry or another hirearchy.
            """
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
                    if audio_id not in viewed_audio_sources:
                        viewed_audio_sources[audio_id] = db.HelldiverAudioSource(
                                uuid.uuid4().hex,
                                audio_id,
                                "",
                                set(),
                                set([bank_id]),
                        )
                    else:
                        viewed_audio_sources[audio_id].linked_soundbank_ids.add(
                                bank_id)

    banks = [bank for _, bank in viewed_banks.items()]
    audio_sources = [audio_source 
                     for _, audio_source in viewed_audio_sources.items()]

    lookup_store.write_helldiver_soundbank_bulk(banks)
    lookup_store.write_helldiver_audio_source_bulk(audio_sources)

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
    generate(app_state, lookup_store, file_handler)
