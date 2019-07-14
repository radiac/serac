"""
Confirm that non-trivial test mocks function as expected
"""
from pathlib import Path

from .mocks import FilesystemTest


class TestFakeFs(FilesystemTest):
    """
    Confirm expectations about pyfakefs
    """

    def test_confirm_pyfakefs_base_class__fake_fs_works(self, fs):
        self.mock_fs(fs)
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
