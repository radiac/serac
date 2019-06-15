"""
Test serac/index/index.py
"""
from datetime import datetime, timedelta
import os
from pathlib import Path

from serac.index.index import get_state_at, scan
from serac.index.models import Action, File

from ..mocks import DatabaseTest, FilesystemTest, gen_file, mock_file_archive


class TestIndexGetState(DatabaseTest):
    def test_single_entry__get_latest(self):
        now = datetime.now()
        earlier = now - timedelta(days=7)

        file1 = gen_file(path="foo", action=Action.ADD, last_modified=earlier)
        file2 = gen_file(path="foo", action=Action.CONTENT, last_modified=now)
        state = get_state_at(when=now)

        assert file1 != file2
        assert state == {"foo": file2}
        assert state["foo"].action == Action.CONTENT

    def test_multiple_entries__get_latest(self):
        now = datetime.now()
        earlier = now - timedelta(days=7)

        file1 = gen_file(path="one", action=Action.ADD, last_modified=earlier)
        file2 = gen_file(path="one", action=Action.CONTENT, last_modified=now)
        file3 = gen_file(path="two", action=Action.ADD, last_modified=earlier)
        file4 = gen_file(path="two", action=Action.CONTENT, last_modified=now)
        state = get_state_at(when=now)

        assert file1 != file2
        assert file3 != file4
        assert state == {"one": file2, "two": file4}
        assert state["one"].action == Action.CONTENT
        assert state["two"].action == Action.CONTENT

    def test_deleted_entry__not_included(self):
        now = datetime.now()
        earlier = now - timedelta(days=7)

        file1 = gen_file(path="one", action=Action.ADD, last_modified=earlier)
        file2 = gen_file(path="one", action=Action.CONTENT, last_modified=now)
        file3 = gen_file(path="two", action=Action.ADD, last_modified=earlier)
        file4 = gen_file(path="two", action=Action.DELETE, last_modified=now)
        state = get_state_at(when=now)

        assert file1 != file2
        assert file3 != file4
        assert state == {"one": file2}
        assert state["one"].action == Action.CONTENT


class TestIndexScan(DatabaseTest, FilesystemTest):
    def test_single_dir__all_files_add(self, fs):
        self.mock_fs(fs)
        changeset = scan(includes=["/src/"])

        assert len(changeset.added.keys()) == 5
        assert "/src/one.txt" in changeset.added
        assert "/src/two.txt" in changeset.added
        assert "/src/dir/three.txt" in changeset.added
        assert "/src/dir/four.txt" in changeset.added
        assert "/src/dir/subdir/five.txt" in changeset.added

        assert len(changeset.content.keys()) == 0
        assert len(changeset.metadata.keys()) == 0
        assert len(changeset.deleted.keys()) == 0

    def test_glob_exclude__exclusions_not_listed(self, fs):
        self.mock_fs(fs)
        changeset = scan(includes=["/src"], excludes=["/src/dir/*.txt"])

        assert len(changeset.added.keys()) == 2
        assert "/src/one.txt" in changeset.added
        assert "/src/two.txt" in changeset.added

    def test_glob_and_exact_exclude__exclusions_not_listed(self, fs):
        self.mock_fs(fs)
        changeset = scan(includes=["/src"], excludes=["/src/one.txt", "/src/dir/*.txt"])

        assert len(changeset.added.keys()) == 1
        assert "/src/two.txt" in changeset.added

    def test_path_exclude__exclusions_not_listed(self, fs):
        self.mock_fs(fs)
        changeset = scan(includes=["/src"], excludes=["*/subdir"])

        assert len(changeset.added.keys()) == 4
        assert "/src/one.txt" in changeset.added
        assert "/src/two.txt" in changeset.added
        assert "/src/dir/three.txt" in changeset.added
        assert "/src/dir/four.txt" in changeset.added

    def test_multiple_dir__all_collected(self, fs):
        self.mock_fs(fs)
        changeset = scan(includes=["/src", "/alt"])

        assert len(changeset.added.keys()) == 7
        assert "/src/one.txt" in changeset.added
        assert "/src/two.txt" in changeset.added
        assert "/src/dir/three.txt" in changeset.added
        assert "/src/dir/four.txt" in changeset.added
        assert "/src/dir/subdir/five.txt" in changeset.added
        assert "/alt/six.txt" in changeset.added
        assert "/alt/seven.txt" in changeset.added

    def test_change_content(self, monkeypatch, fs):
        self.mock_fs(fs)
        monkeypatch.setattr(File, "archive", mock_file_archive)

        changeset = scan(includes=["/src"])
        changeset.commit(destination=self.get_destination())

        Path("/src/one.txt").write_text("one updated")
        Path("/src/dir/three.txt").write_text("three updated")
        changeset = scan(includes=["/src"])

        assert len(changeset.added.keys()) == 0
        assert len(changeset.content.keys()) == 2
        assert "/src/one.txt" in changeset.content
        assert "/src/dir/three.txt" in changeset.content
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

        assert len(changeset.added.keys()) == 0
        assert len(changeset.content.keys()) == 0
        assert len(changeset.metadata.keys()) == 2
        assert "/src/one.txt" in changeset.metadata
        assert "/src/dir/three.txt" in changeset.metadata
        assert len(changeset.deleted.keys()) == 0

    def test_delete(self, monkeypatch, fs):
        self.mock_fs(fs)
        monkeypatch.setattr(File, "archive", mock_file_archive)

        changeset = scan(includes=["/src"])
        changeset.commit(destination=self.get_destination())

        Path("/src/one.txt").unlink()
        Path("/src/dir/three.txt").unlink()
        changeset = scan(includes=["/src"])

        assert len(changeset.added.keys()) == 0
        assert len(changeset.content.keys()) == 0
        assert len(changeset.metadata.keys()) == 0
        assert len(changeset.deleted.keys()) == 2
        assert "/src/one.txt" in changeset.deleted
        assert "/src/dir/three.txt" in changeset.deleted
