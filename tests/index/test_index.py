"""
Test serac/index/index.py
"""
from datetime import datetime, timedelta

from serac.index.index import get_state_at
from serac.index.models import Action

from ..mocks import DatabaseTest, FilesystemTest, gen_file


class TestIndexGetState(DatabaseTest):
    def test_single_entry__get_latest(self):
        now = datetime.now()
        earlier = now - timedelta(days=7)

        file1 = gen_file(path='foo', action=Action.ADD, last_modified=earlier)
        file2 = gen_file(path='foo', action=Action.CHANGE, last_modified=now)
        state = get_state_at(when=now)

        assert file1 != file2
        assert state == {
            'foo': file2,
        }
        assert state['foo'].action == Action.CHANGE

    def test_multiple_entries__get_latest(self):
        now = datetime.now()
        earlier = now - timedelta(days=7)

        file1 = gen_file(path='one', action=Action.ADD, last_modified=earlier)
        file2 = gen_file(path='one', action=Action.CHANGE, last_modified=now)
        file3 = gen_file(path='two', action=Action.ADD, last_modified=earlier)
        file4 = gen_file(path='two', action=Action.CHANGE, last_modified=now)
        state = get_state_at(when=now)

        assert file1 != file2
        assert file3 != file4
        assert state == {
            'one': file2,
            'two': file4,
        }
        assert state['one'].action == Action.CHANGE
        assert state['two'].action == Action.CHANGE

    def test_deleted_entry__not_included(self):
        now = datetime.now()
        earlier = now - timedelta(days=7)

        file1 = gen_file(path='one', action=Action.ADD, last_modified=earlier)
        file2 = gen_file(path='one', action=Action.CHANGE, last_modified=now)
        file3 = gen_file(path='two', action=Action.ADD, last_modified=earlier)
        file4 = gen_file(path='two', action=Action.DELETE, last_modified=now)
        state = get_state_at(when=now)

        assert file1 != file2
        assert file3 != file4
        assert state == {
            'one': file2,
        }
        assert state['one'].action == Action.CHANGE


class TestIndexScan(FilesystemTest):
    def mock_fs(self):
        fs = self.patcher.fs
        fs.create_file('/src/one.txt', contents='one')
        fs.create_file('/src/two.txt', contents='two')
        fs.create_file('/src/dir/three.txt', contents='three')
        fs.create_file('/src/dir/four.txt', contents='four')
        fs.create_file('/src/dir/subdir/five.txt', contents='five')

    def test_confirm_pyfakefs_base_class__fake_fs_works(self):
        self.patcher.fs.create_file('/foo/bar', contents='test')
        with open('/foo/bar') as f:
            contents = f.read()
        assert contents == 'test'
