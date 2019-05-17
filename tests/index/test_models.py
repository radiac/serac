"""
Test serac/index/models.py
"""
from datetime import datetime, timedelta

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
