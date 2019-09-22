"""
Test restore() in serac/index/index.py
"""
from datetime import datetime
from pathlib import Path
from time import time

import pytest

from serac.exceptions import FileExists, SeracException
from serac.index.index import Pattern, restore

from .test_index import IndexTestBase


class TestIndexRestore(IndexTestBase):
    def test_restore_file__from_head__restores_single_file(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        restored = restore(
            archive_config=self.get_archive_config(),
            timestamp=int(time()),
            destination_path=Path("/retrieved"),
            pattern=Pattern("/src/dir/three.txt"),
        )

        assert restored == {"/src/dir/three.txt": True}
        assert Path("/retrieved/three.txt").is_file()
        assert Path("/retrieved/three.txt").read_text() == "updated"

    def test_restore_file__from_past__restores_single_file(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        restored = restore(
            archive_config=self.get_archive_config(),
            timestamp=int(initial_time.timestamp()),
            destination_path=Path("/retrieved"),
            pattern=Pattern("/src/dir/three.txt"),
        )

        assert restored == {"/src/dir/three.txt": True}
        assert Path("/retrieved").is_dir()
        assert Path("/retrieved/three.txt").is_file()
        assert Path("/retrieved/three.txt").read_text() == "three"

    def test_restore_dir__from_head__restores_some_files(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        restored = restore(
            archive_config=self.get_archive_config(),
            timestamp=int(time()),
            destination_path=Path("/retrieved"),
            pattern=Pattern("/src/dir"),
        )

        assert restored == {
            "/src/dir/three.txt": True,
            "/src/dir/four.txt": True,
            "/src/dir/subdir/five.txt": True,
        }
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
            destination_path=Path("/retrieved"),
            pattern=Pattern("/src/dir"),
        )

        assert restored == {
            "/src/dir/three.txt": True,
            "/src/dir/four.txt": True,
            "/src/dir/subdir/five.txt": True,
        }
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
            destination_path=Path("/retrieved"),
        )

        assert restored == {
            "/src/one.txt": True,
            "/src/two.txt": True,
            "/src/dir/three.txt": True,
            "/src/dir/four.txt": True,
            "/src/dir/subdir/five.txt": True,
        }
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
            destination_path=Path("/retrieved"),
        )

        assert restored == {
            "/src/one.txt": True,
            "/src/two.txt": True,
            "/src/dir/three.txt": True,
            "/src/dir/four.txt": True,
            "/src/dir/subdir/five.txt": True,
        }
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
            destination_path=Path("/retrieved"),
            pattern=Pattern("/does/not.exist"),
            missing_ok=True,
        )
        assert restored == {}

    def test_restore_missing__missing_not_ok__raises_exception(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)

        with pytest.raises(SeracException) as e:
            restore(
                archive_config=self.get_archive_config(),
                timestamp=int(time()),
                destination_path=Path("/retrieved"),
                pattern=Pattern("/does/not.exist"),
                missing_ok=False,
            )
        assert str(e.value) == "Requested path not found in archive"

    def test_restore_missing_empty__missing_not_ok__raises_exception(self, fs, freezer):
        with pytest.raises(SeracException) as e:
            restore(
                archive_config=self.get_archive_config(),
                timestamp=int(time()),
                destination_path=Path("/retrieved"),
                missing_ok=False,
            )
        assert str(e.value) == "Archive is empty"

    def test_state_at_datetime__raise_exception(self, fs):
        now = datetime.now()

        with pytest.raises(ValueError) as e:
            restore(
                archive_config=self.get_archive_config(),
                timestamp=now,
                destination_path=Path("/retrieved"),
                missing_ok=False,
            )
        assert str(e.value) == "Can only restore using a timestamp"

    def test_restore_dir__file_exists__restores_other_files(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        Path("/retrieved/three.txt").write_text("original")
        restored = restore(
            archive_config=self.get_archive_config(),
            timestamp=int(time()),
            destination_path=Path("/retrieved"),
            pattern=Pattern("/src/dir"),
        )

        assert len(restored) == 3
        assert isinstance(restored["/src/dir/three.txt"], FileExists)
        assert restored["/src/dir/four.txt"] is True
        assert restored["/src/dir/subdir/five.txt"] is True

        assert Path("/retrieved/three.txt").is_file()
        assert Path("/retrieved/three.txt").read_text() == "original"
        assert Path("/retrieved/four.txt").is_file()
        assert Path("/retrieved/four.txt").read_text() == "four"
        assert Path("/retrieved/subdir/five.txt").is_file()
        assert Path("/retrieved/subdir/five.txt").read_text() == "five"
