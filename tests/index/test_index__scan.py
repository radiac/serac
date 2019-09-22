"""
Test scan() in serac/index/index.py
"""
import os
from pathlib import Path

from serac.index.index import scan
from serac.index.models import File

from ..mocks import DatabaseTest, FilesystemTest, mock_file_archive


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
