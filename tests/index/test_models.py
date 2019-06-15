"""
Test serac/index/models.py
"""
from datetime import datetime, timedelta

from serac.config import DestinationConfig
from serac.storage import Local
from serac.index.models import File

from ..mocks import DatabaseTest, gen_file


class TestDatabaseTest(DatabaseTest):
    """
    Test the DatabaseTest base class operates as expected
    """

    def test_create_first__object_is_only_item(self):
        file = gen_file(path="/tmp/foo")
        files = File.select()
        assert len(files) == 1
        assert files[0].path == file.path

    def test_create_second__object_is_only_item(self):
        """
        Ensure db is wiped between tests
        """
        file = gen_file(path="/tmp/bar")
        files = File.select()
        assert len(files) == 1
        assert files[0].path == file.path

    def test_create_multiple__all_returned(self):
        now = datetime.now()
        earlier = now - timedelta(days=7)

        file1 = gen_file(path="/tmp/foo", last_modified=earlier)
        file2 = gen_file(path="/tmp/foo", last_modified=now)
        files = File.select()
        assert len(files) == 2
        assert list(files) == [file1, file2]


def TestFile(DatabaseTest, FilesystemTest):
    """
    Test the File model
    """

    def test_metadata(self, fs):
        fs.create_file("/tmp/foo", contents="unencrypted")
        file = File(path="/tmp/foo")
        file.refresh_metadata_from_disk()
        assert file.size == len("unencrypted")
        # ++ TODO: Test other attributes:
        #   freeze time and check last modified
        #   set uid and gid

    def test_archive(self, fs):
        fs.create_file("/src/foo", contents="unencrypted")
        file = File(path="/src/foo")
        destination_config = DestinationConfig(
            storage=Local(path="/dest/"), password="secret"
        )
        file.archive(destination_config)

        # ++ TODO
        # Check Archived db object exists
        # Check file exists in/dest/
        # Check it has been encrypted
        # Check we can decrypt it
