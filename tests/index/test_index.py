"""
Test serac/index/index.py
"""
from datetime import datetime, timedelta
from pathlib import Path

from serac.index.index import get_state_at, scan
from serac.index.models import Action

from ..mocks import DatabaseTest, FilesystemTest, gen_file


class TestIndexGetState(DatabaseTest):
    def test_single_entry__get_latest(self):
        now = datetime.now()
        earlier = now - timedelta(days=7)

        file1 = gen_file(path="foo", action=Action.ADD, last_modified=earlier)
        file2 = gen_file(path="foo", action=Action.CHANGE, last_modified=now)
        state = get_state_at(when=now)

        assert file1 != file2
        assert state == {"foo": file2}
        assert state["foo"].action == Action.CHANGE

    def test_multiple_entries__get_latest(self):
        now = datetime.now()
        earlier = now - timedelta(days=7)

        file1 = gen_file(path="one", action=Action.ADD, last_modified=earlier)
        file2 = gen_file(path="one", action=Action.CHANGE, last_modified=now)
        file3 = gen_file(path="two", action=Action.ADD, last_modified=earlier)
        file4 = gen_file(path="two", action=Action.CHANGE, last_modified=now)
        state = get_state_at(when=now)

        assert file1 != file2
        assert file3 != file4
        assert state == {"one": file2, "two": file4}
        assert state["one"].action == Action.CHANGE
        assert state["two"].action == Action.CHANGE

    def test_deleted_entry__not_included(self):
        now = datetime.now()
        earlier = now - timedelta(days=7)

        file1 = gen_file(path="one", action=Action.ADD, last_modified=earlier)
        file2 = gen_file(path="one", action=Action.CHANGE, last_modified=now)
        file3 = gen_file(path="two", action=Action.ADD, last_modified=earlier)
        file4 = gen_file(path="two", action=Action.DELETE, last_modified=now)
        state = get_state_at(when=now)

        assert file1 != file2
        assert file3 != file4
        assert state == {"one": file2}
        assert state["one"].action == Action.CHANGE


class TestIndexScan(DatabaseTest, FilesystemTest):
    def mock_fs(self):
        fs = self.patcher.fs
        fs.create_file("/src/one.txt", contents="one")
        fs.create_file("/src/two.txt", contents="two")
        fs.create_file("/src/dir/three.txt", contents="three")
        fs.create_file("/src/dir/four.txt", contents="four")
        fs.create_file("/src/dir/subdir/five.txt", contents="five")
        fs.create_file("/alt/six.txt", contents="one")
        fs.create_file("/alt/seven.txt", contents="two")

    def test_confirm_pyfakefs_base_class__fake_fs_works(self):
        self.mock_fs()
        assert Path("/src").is_dir()
        assert Path("/src/one.txt").is_file()
        assert Path("/src/two.txt").is_file()
        assert Path("/src/dir").is_dir()
        assert Path("/src/dir/three.txt").is_file()
        assert Path("/src/dir/four.txt").is_file()
        assert Path("/src/dir/subdir").is_dir()
        assert Path("/src/dir/subdir/five.txt").is_file()
        assert Path("/alt").is_dir()
        assert Path("/alt/six.txt").is_file()
        assert Path("/alt/seven.txt").is_file()

        with open("/src/one.txt") as f:
            contents = f.read()
        assert contents == "one"

    def test_scan_single_dir__all_files_add(self):
        self.mock_fs()
        changeset = scan(includes=["/src/"], excludes=[])

        assert len(changeset.added.keys()) == 5
        assert "/src/one.txt" in changeset.added
        assert "/src/two.txt" in changeset.added
        assert "/src/dir/three.txt" in changeset.added
        assert "/src/dir/four.txt" in changeset.added
        assert "/src/dir/subdir/five.txt" in changeset.added

        assert len(changeset.content.keys()) == 0
        assert len(changeset.meta.keys()) == 0
        assert len(changeset.deleted.keys()) == 0

    def test_scan_with_glob_exclude__exclusions_not_listed(self):
        self.mock_fs()
        changeset = scan(includes=["/src"], excludes=["/src/dir/*.txt"])

        assert len(changeset.added.keys()) == 2
        assert "/src/one.txt" in changeset.added
        assert "/src/two.txt" in changeset.added

    def test_scan_with_glob_and_exact_exclude__exclusions_not_listed(self):
        self.mock_fs()
        changeset = scan(includes=["/src"], excludes=["/src/one.txt", "/src/dir/*.txt"])

        assert len(changeset.added.keys()) == 1
        assert "/src/two.txt" in changeset.added

    def test_scan_with_path_exclude__exclusions_not_listed(self):
        self.mock_fs()
        changeset = scan(includes=["/src"], excludes=["*/subdir"])

        assert len(changeset.added.keys()) == 4
        assert "/src/one.txt" in changeset.added
        assert "/src/two.txt" in changeset.added
        assert "/src/dir/three.txt" in changeset.added
        assert "/src/dir/four.txt" in changeset.added

    def test_scan_multiple_dir__all_collected(self):
        self.mock_fs()

        changeset = scan(includes=["/src", "/alt"], excludes=[])

        assert len(changeset.added.keys()) == 7
        assert "/src/one.txt" in changeset.added
        assert "/src/two.txt" in changeset.added
        assert "/src/dir/three.txt" in changeset.added
        assert "/src/dir/four.txt" in changeset.added
        assert "/src/dir/subdir/five.txt" in changeset.added
        assert "/alt/six.txt" in changeset.added
        assert "/alt/seven.txt" in changeset.added
