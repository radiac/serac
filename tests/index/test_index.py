"""
Test serac/index/index.py
"""
from datetime import datetime, timedelta
import os
from pathlib import Path
from time import time

from pyfakefs.fake_filesystem import FakeFile

from serac.index.index import get_state_at, scan, restore
from serac.index.models import Action, File

from ..mocks import DatabaseTest, FilesystemTest, gen_file, mock_file_archive


class TestIndexGetState(DatabaseTest):
    def test_single_entry__get_latest(self):
        now = datetime.now()
        earlier = now - timedelta(days=7)

        file1 = gen_file(path="foo", action=Action.ADD, last_modified=earlier)
        file2 = gen_file(path="foo", action=Action.CONTENT, last_modified=now)
        state = get_state_at(timestamp=int(now.timestamp()))

        assert file1 != file2
        assert state == {Path("foo"): file2}
        assert state[Path("foo")].action == Action.CONTENT

    def test_multiple_entries__get_latest(self):
        now = datetime.now()
        earlier = now - timedelta(days=7)

        file1 = gen_file(path="one", action=Action.ADD, last_modified=earlier)
        file2 = gen_file(path="one", action=Action.CONTENT, last_modified=now)
        file3 = gen_file(path="two", action=Action.ADD, last_modified=earlier)
        file4 = gen_file(path="two", action=Action.CONTENT, last_modified=now)
        state = get_state_at(timestamp=int(now.timestamp()))

        assert file1 != file2
        assert file3 != file4
        assert state == {Path("one"): file2, Path("two"): file4}
        assert state[Path("one")].action == Action.CONTENT
        assert state[Path("two")].action == Action.CONTENT

    def test_multiple_entries__get_earlier(self):
        now = datetime.now()
        earlier = now - timedelta(days=7)

        file1 = gen_file(path="one", action=Action.ADD, last_modified=earlier)
        file2 = gen_file(path="one", action=Action.CONTENT, last_modified=now)
        file3 = gen_file(path="two", action=Action.ADD, last_modified=earlier)
        file4 = gen_file(path="two", action=Action.CONTENT, last_modified=now)
        state = get_state_at(timestamp=int(earlier.timestamp()))

        assert file1 != file2
        assert file3 != file4
        assert state == {Path("one"): file1, Path("two"): file3}
        assert state[Path("one")].action == Action.ADD
        assert state[Path("two")].action == Action.ADD

    def test_deleted_entry__not_included(self):
        now = datetime.now()
        earlier = now - timedelta(days=7)

        file1 = gen_file(path="one", action=Action.ADD, last_modified=earlier)
        file2 = gen_file(path="one", action=Action.CONTENT, last_modified=now)
        file3 = gen_file(path="two", action=Action.ADD, last_modified=earlier)
        file4 = gen_file(path="two", action=Action.DELETE, last_modified=now)
        state = get_state_at(timestamp=int(now.timestamp()))

        assert file1 != file2
        assert file3 != file4
        assert state == {Path("one"): file2}
        assert state[Path("one")].action == Action.CONTENT


class TestIndexScan(DatabaseTest, FilesystemTest):
    def test_single_dir__all_files_add(self, fs):
        self.mock_fs(fs)
        changeset = scan(includes=["/src/"])

        assert len(changeset.added.keys()) == 5
        assert Path("/src/one.txt") in changeset.added
        assert Path("/src/two.txt") in changeset.added
        assert Path("/src/dir/three.txt") in changeset.added
        assert Path("/src/dir/four.txt") in changeset.added
        assert Path("/src/dir/subdir/five.txt") in changeset.added

        assert len(changeset.content.keys()) == 0
        assert len(changeset.metadata.keys()) == 0
        assert len(changeset.deleted.keys()) == 0

    def test_glob_exclude__exclusions_not_listed(self, fs):
        self.mock_fs(fs)
        changeset = scan(includes=["/src"], excludes=["/src/dir/*.txt"])

        assert len(changeset.added.keys()) == 2
        assert Path("/src/one.txt") in changeset.added
        assert Path("/src/two.txt") in changeset.added

    def test_glob_and_exact_exclude__exclusions_not_listed(self, fs):
        self.mock_fs(fs)
        changeset = scan(includes=["/src"], excludes=["/src/one.txt", "/src/dir/*.txt"])

        assert len(changeset.added.keys()) == 1
        assert Path("/src/two.txt") in changeset.added

    def test_path_exclude__exclusions_not_listed(self, fs):
        self.mock_fs(fs)
        changeset = scan(includes=["/src"], excludes=["*/subdir"])

        assert len(changeset.added.keys()) == 4
        assert Path("/src/one.txt") in changeset.added
        assert Path("/src/two.txt") in changeset.added
        assert Path("/src/dir/three.txt") in changeset.added
        assert Path("/src/dir/four.txt") in changeset.added

    def test_multiple_dir__all_collected(self, fs):
        self.mock_fs(fs)
        changeset = scan(includes=["/src", "/alt"])

        assert len(changeset.added.keys()) == 7
        assert Path("/src/one.txt") in changeset.added
        assert Path("/src/two.txt") in changeset.added
        assert Path("/src/dir/three.txt") in changeset.added
        assert Path("/src/dir/four.txt") in changeset.added
        assert Path("/src/dir/subdir/five.txt") in changeset.added
        assert Path("/alt/six.txt") in changeset.added
        assert Path("/alt/seven.txt") in changeset.added

    def test_change_content(self, monkeypatch, fs):
        self.mock_fs(fs)
        monkeypatch.setattr(File, "archive", mock_file_archive)

        changeset = scan(includes=["/src"])
        changeset.commit(destination=self.get_destination())

        Path("/src/one.txt").write_text("one updated")
        Path("/src/dir/three.txt").write_text("three updated")
        changeset = scan(includes=["/src"])
        changeset.commit(destination=self.get_destination())

        assert len(changeset.added.keys()) == 0
        assert len(changeset.content.keys()) == 2
        assert Path("/src/one.txt") in changeset.content
        assert Path("/src/dir/three.txt") in changeset.content
        assert len(changeset.metadata.keys()) == 0
        assert len(changeset.deleted.keys()) == 0

    def test_change_metadata(self, monkeypatch, fs):
        self.mock_fs(fs)
        monkeypatch.setattr(File, "archive", mock_file_archive)

        changeset = scan(includes=["/src"])
        changeset.commit(destination=self.get_destination())

        Path("/src/one.txt").chmod(0o444)
        os.chown("/src/dir/three.txt", 1, 1)
        changeset = scan(includes=["/src"])
        changeset.commit(destination=self.get_destination())

        assert len(changeset.added.keys()) == 0
        assert len(changeset.content.keys()) == 0
        assert len(changeset.metadata.keys()) == 2
        assert Path("/src/one.txt") in changeset.metadata
        assert Path("/src/dir/three.txt") in changeset.metadata
        assert len(changeset.deleted.keys()) == 0

    def test_delete(self, monkeypatch, fs):
        self.mock_fs(fs)
        monkeypatch.setattr(File, "archive", mock_file_archive)

        changeset = scan(includes=["/src"])
        changeset.commit(destination=self.get_destination())

        Path("/src/one.txt").unlink()
        Path("/src/dir/three.txt").unlink()
        changeset = scan(includes=["/src"])
        changeset.commit(destination=self.get_destination())

        assert len(changeset.added.keys()) == 0
        assert len(changeset.content.keys()) == 0
        assert len(changeset.metadata.keys()) == 0
        assert len(changeset.deleted.keys()) == 2
        assert Path("/src/one.txt") in changeset.deleted
        assert Path("/src/dir/three.txt") in changeset.deleted


class TestIndexRestore(DatabaseTest, FilesystemTest):
    def mock_initial(self, fs):
        self.mock_fs(fs)
        fs.create_dir("/dest")
        fs.create_dir("/retrieved")
        changeset = scan(includes=["/src/"])
        changeset.commit(destination=self.get_destination())

    def mock_update(self, fs):
        Path("/src/dir/three.txt").write_text("updated")
        FakeFile("/src/dir/three.txt", filesystem=fs).st_mtime = int(time())
        changeset = scan(includes=["/src/"])
        changeset.commit(destination=self.get_destination())

    def test_restore_file__from_head__restores_single_file(self, fs):
        self.mock_initial(fs)
        self.mock_update(fs)
        restored = restore(
            destination=self.get_destination(),
            timestamp=int(time()),
            out_path=Path("/retrieved"),
            archive_path=Path("/src/dir/three.txt"),
        )

        assert restored == 1
        assert Path("/retrieved/three.txt").is_file()
        assert Path("/retrieved/three.txt").read_text() == "updated"

    def test_restore_file__from_past__restores_single_file(self, fs, freezer):
        initial_time = datetime(2001, 1, 1, 1, 1, 1)
        freezer.move_to(initial_time)
        self.mock_initial(fs)
        update_time = datetime(2001, 1, 1, 1, 1, 2)
        freezer.move_to(update_time)
        self.mock_update(fs)

        restored = restore(
            destination=self.get_destination(),
            out_path=Path("/retrieved"),
            archive_path=Path("/src/dir/three.txt"),
            timestamp=int(initial_time.timestamp()),
        )

        assert restored == 1
        assert Path("/retrieved").is_dir()
        assert Path("/retrieved/three.txt").is_file()
        assert Path("/retrieved/three.txt").read_text() == "three"

    # TODO
    # test_restore_dir__from_head__restores_some_files(self, fs)
    # test_restore dir__from_past__restores_some_files(self, fs)

    # test_restore_all__from_head__restores_all_files(self, fs)
    # test_restore_all__from_past__restores_all_files(self, fs)

    # test_restore_missing__missing_ok__returns_zero(self, fs)
    # test_restore_missing__missing_not_ok__raises_exception(self, fs)
