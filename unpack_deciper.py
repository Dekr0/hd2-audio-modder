import os

from audio_modder import FileHandler
from config import Config, load_config


def test_stream_id_is_toc_file_id(file_handler: FileHandler):
    result_stream_resource_ids: list[int] = [
            stream.content.get_resource_id()
            for stream in file_handler.get_wwise_streams().values()
            if stream.content != None
            ]
    assert(len(result_stream_resource_ids) == 
           len(file_handler.file_reader.wwise_stream_resource_ids))
    for e in result_stream_resource_ids:
        assert(e in file_handler.file_reader.wwise_stream_resource_ids)

app_state: Config | None = load_config()
if app_state == None:
    exit(1)

file_handler = FileHandler()

archive_file = os.path.join(app_state.game_data_path, "a66d7cf238070ca7")

if not os.path.exists(archive_file):
    exit(1)

file_handler.load_archive_file(archive_file=archive_file)

# test_stream_id_is_toc_file_id(file_handler)
