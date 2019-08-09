"""
Test serac/index/index.py
"""
from datetime import datetime, timedelta
import os
from pathlib import Path
from time import time

import pytest
from pyfakefs.fake_filesystem import FakeFile

from serac.index.index import Pattern, State, scan, search, restore
from serac.index.models import Action, File

from ..mocks import DatabaseTest, FilesystemTest, gen_file, mock_file_archive


class TestIndexGetState(DatabaseTest):
    def test_single_entry__get_latest(self):
        now = datetime.now()
        earlier = now - timedelta(days=7)

        file1 = gen_file(path="foo", action=Action.ADD, last_modified=earlier)
        file2 = gen_file(path="foo", action=Action.CONTENT, last_modified=now)
        state = State.at(timestamp=int(now.timestamp()))

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
        state = State.at(timestamp=int(now.timestamp()))

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
        state = State.at(timestamp=int(earlier.timestamp()))

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
        state = State.at(timestamp=int(now.timestamp()))

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
        changeset.commit(archive_config=self.get_archive_config())

        Path("/src/one.txt").write_text("one updated")
        Path("/src/dir/three.txt").write_text("three updated")
        changeset = scan(includes=["/src"])
        changeset.commit(archive_config=self.get_archive_config())

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
        changeset.commit(archive_config=self.get_archive_config())

        Path("/src/one.txt").chmod(0o444)
        os.chown("/src/dir/three.txt", 1, 1)
        changeset = scan(includes=["/src"])
        changeset.commit(archive_config=self.get_archive_config())

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
        changeset.commit(archive_config=self.get_archive_config())

        Path("/src/one.txt").unlink()
        Path("/src/dir/three.txt").unlink()
        changeset = scan(includes=["/src"])
        changeset.commit(archive_config=self.get_archive_config())

        assert len(changeset.added.keys()) == 0
        assert len(changeset.content.keys()) == 0
        assert len(changeset.metadata.keys()) == 0
        assert len(changeset.deleted.keys()) == 2
        assert Path("/src/one.txt") in changeset.deleted
        assert Path("/src/dir/three.txt") in changeset.deleted


class IndexTestBase(DatabaseTest, FilesystemTest):
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


class TestIndexSearch(IndexTestBase):
    def test_search_file__from_head__finds_single_file(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        results = search(timestamp=int(time()), pattern=Pattern("/src/dir/three.txt"))

        assert len(results) == 1
        assert Path("/src/dir/three.txt") in results
        assert results[Path("/src/dir/three.txt")].last_modified == int(
            update_time.timestamp()
        )

    def test_search_file__from_past__finds_single_file(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        results = search(
            timestamp=int(initial_time.timestamp()),
            pattern=Pattern("/src/dir/three.txt"),
        )

        assert len(results) == 1
        assert Path("/src/dir/three.txt") in results
        assert results[Path("/src/dir/three.txt")].last_modified == int(
            initial_time.timestamp()
        )

    def test_search_dir__from_head__finds_some_files(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        results = search(timestamp=int(time()), pattern=Pattern("/src/dir"))

        assert len(results) == 3
        assert Path("/src/dir/three.txt") in results
        assert (
            results[Path("/src/dir/three.txt")].last_modified == update_time.timestamp()
        )
        assert Path("/src/dir/four.txt") in results
        assert Path("/src/dir/subdir/five.txt") in results

    def test_search_dir__from_past__finds_some_files(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        results = search(
            timestamp=int(initial_time.timestamp()), pattern=Pattern("/src/dir")
        )

        assert len(results) == 3
        assert Path("/src/dir/three.txt") in results
        assert (
            results[Path("/src/dir/three.txt")].last_modified
            == initial_time.timestamp()
        )
        assert Path("/src/dir/four.txt") in results
        assert Path("/src/dir/subdir/five.txt") in results

    def test_search_all__from_head__finds_all_files(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        results = search(timestamp=int(time()))

        assert len(results) == 5
        assert Path("/src/one.txt") in results
        assert Path("/src/two.txt") in results
        assert Path("/src/dir/three.txt") in results
        assert (
            results[Path("/src/dir/three.txt")].last_modified == update_time.timestamp()
        )
        assert Path("/src/dir/four.txt") in results
        assert Path("/src/dir/subdir/five.txt") in results

    def test_search_all__from_past__finds_all_files(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        results = search(timestamp=int(initial_time.timestamp()))

        assert len(results) == 5
        assert Path("/src/one.txt") in results
        assert Path("/src/two.txt") in results
        assert Path("/src/dir/three.txt") in results
        assert (
            results[Path("/src/dir/three.txt")].last_modified
            == initial_time.timestamp()
        )
        assert Path("/src/dir/four.txt") in results
        assert Path("/src/dir/subdir/five.txt") in results

    def test_search_missing__returns_zero(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        results = search(timestamp=int(time()), pattern=Pattern("/does/not.exist"))
        assert len(results) == 0


class TestIndexRestore(IndexTestBase):
    def test_restore_file__from_head__restores_single_file(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        restored = restore(
            archive_config=self.get_archive_config(),
            timestamp=int(time()),
            out_path=Path("/retrieved"),
            pattern=Pattern("/src/dir/three.txt"),
        )

        assert restored == 1
        assert Path("/retrieved/three.txt").is_file()
        assert Path("/retrieved/three.txt").read_text() == "updated"

    def test_restore_file__from_past__restores_single_file(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        restored = restore(
            archive_config=self.get_archive_config(),
            timestamp=int(initial_time.timestamp()),
            out_path=Path("/retrieved"),
            pattern=Pattern("/src/dir/three.txt"),
        )

        assert restored == 1
        assert Path("/retrieved").is_dir()
        assert Path("/retrieved/three.txt").is_file()
        assert Path("/retrieved/three.txt").read_text() == "three"

    def test_restore_dir__from_head__restores_some_files(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        restored = restore(
            archive_config=self.get_archive_config(),
            timestamp=int(time()),
            out_path=Path("/retrieved"),
            pattern=Pattern("/src/dir"),
        )

        assert restored == 3
        assert Path("/retrieved/three.txt").is_file()
        assert Path("/retrieved/three.txt").read_text() == "updated"
        assert Path("/retrieved/four.txt").is_file()
        assert Path("/retrieved/four.txt").read_text() == "four"
        assert Path("/retrieved/subdir/five.txt").is_file()
        assert Path("/retrieved/subdir/five.txt").read_text() == "five"

    def test_restore_dir__from_past__restores_some_files(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        restored = restore(
            archive_config=self.get_archive_config(),
            timestamp=int(initial_time.timestamp()),
            out_path=Path("/retrieved"),
            pattern=Pattern("/src/dir"),
        )

        assert restored == 3
        assert Path("/retrieved/three.txt").is_file()
        assert Path("/retrieved/three.txt").read_text() == "three"
        assert Path("/retrieved/four.txt").is_file()
        assert Path("/retrieved/four.txt").read_text() == "four"
        assert Path("/retrieved/subdir/five.txt").is_file()
        assert Path("/retrieved/subdir/five.txt").read_text() == "five"

    def test_restore_all__from_head__restores_all_files(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        restored = restore(
            archive_config=self.get_archive_config(),
            timestamp=int(time()),
            out_path=Path("/retrieved"),
        )

        assert restored == 5
        assert Path("/retrieved/src/one.txt").is_file()
        assert Path("/retrieved/src/one.txt").read_text() == "one"
        assert Path("/retrieved/src/two.txt").is_file()
        assert Path("/retrieved/src/two.txt").read_text() == "two"
        assert Path("/retrieved/src/dir/three.txt").is_file()
        assert Path("/retrieved/src/dir/three.txt").read_text() == "updated"
        assert Path("/retrieved/src/dir/four.txt").is_file()
        assert Path("/retrieved/src/dir/four.txt").read_text() == "four"
        assert Path("/retrieved/src/dir/subdir/five.txt").is_file()
        assert Path("/retrieved/src/dir/subdir/five.txt").read_text() == "five"

    def test_restore_all__from_past__restores_all_files(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        restored = restore(
            archive_config=self.get_archive_config(),
            timestamp=int(initial_time.timestamp()),
            out_path=Path("/retrieved"),
        )

        assert restored == 5
        assert Path("/retrieved/src/one.txt").is_file()
        assert Path("/retrieved/src/one.txt").read_text() == "one"
        assert Path("/retrieved/src/two.txt").is_file()
        assert Path("/retrieved/src/two.txt").read_text() == "two"
        assert Path("/retrieved/src/dir/three.txt").is_file()
        assert Path("/retrieved/src/dir/three.txt").read_text() == "three"
        assert Path("/retrieved/src/dir/four.txt").is_file()
        assert Path("/retrieved/src/dir/four.txt").read_text() == "four"
        assert Path("/retrieved/src/dir/subdir/five.txt").is_file()
        assert Path("/retrieved/src/dir/subdir/five.txt").read_text() == "five"

    def test_restore_missing__missing_ok__returns_zero(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        restored = restore(
            archive_config=self.get_archive_config(),
            timestamp=int(time()),
            out_path=Path("/retrieved"),
            pattern=Pattern("/does/not.exist"),
            missing_ok=True,
        )
        assert restored == 0

    def test_restore_missing__missing_not_ok__raises_exception(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)

        with pytest.raises(FileNotFoundError) as e:
            restore(
                archive_config=self.get_archive_config(),
                timestamp=int(time()),
                out_path=Path("/retrieved"),
                pattern=Pattern("/does/not.exist"),
                missing_ok=False,
            )
        assert str(e.value) == "Requested path not found in archive"

    def test_restore_missing_empty__missing_not_ok__raises_exception(self, fs, freezer):
        with pytest.raises(FileNotFoundError) as e:
            restore(
                archive_config=self.get_archive_config(),
                timestamp=int(time()),
                out_path=Path("/retrieved"),
                missing_ok=False,
            )
        assert str(e.value) == "Archive is empty"
