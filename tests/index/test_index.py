"""
Test serac/index/index.py

Feature tests are broken into additional files
"""
from datetime import datetime
from pathlib import Path
from time import time

from pyfakefs.fake_filesystem import FakeFile

from serac.index.index import Pattern, scan

from ..mocks import DatabaseTest, FilesystemTest


class TestIndexPattern:
    def test_pattern_eq__is_equal(self):
        assert Pattern("/foo") == Pattern("/foo")

    def test_pattern_eq__is_not_equal(self):
        assert Pattern("/foo") != Pattern("/bar")


class IndexTestBase(DatabaseTest, FilesystemTest):
    """
    Base class for use in other index tests
    """

    def mock_initial(self, fs):
        self.mock_fs(fs)
        fs.create_dir("/dest")
        fs.create_dir("/retrieved")
        changeset = scan(includes=["/src/"])
        changeset.commit(archive_config=self.get_archive_config())

    def mock_update(self, fs):
        Path("/src/dir/three.txt").write_text("updated")
        FakeFile("/src/dir/three.txt", filesystem=fs).st_mtime = int(time())
        changeset = scan(includes=["/src/"])
        changeset.commit(archive_config=self.get_archive_config())

    def mock_two_states(self, fs, freezer):
        initial_time = datetime(2001, 1, 1, 1, 1, 1)
        freezer.move_to(initial_time)
        self.mock_initial(fs)
        update_time = datetime(2001, 1, 1, 1, 1, 2)
        freezer.move_to(update_time)
        self.mock_update(fs)
        return initial_time, update_time
