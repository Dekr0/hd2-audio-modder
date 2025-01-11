import unittest
import cProfile
import pstats

from sys import stdout

from audio_modder import FileHandler


class TestProfiling(unittest.TestCase):

    def test_profiling_validate_source_ids_csv(self):
        handler = FileHandler()
        handler.load_archive_file(
                archive_file="test_mockup/archive_files/ea6967f8565a2d76")

        sources = [
            "407310262",
            "276231232",
            "760146779",
            "276231232",
            "989834962"
        ]
        
        profiler = cProfile.Profile()

        profiler.enable()
        handler.validate_source_ids(sources)
        profiler.disable()

        stat = pstats.Stats(profiler, stream=stdout)
        stat.print_stats()


if __name__ == "__main__":
    unittest.main()
