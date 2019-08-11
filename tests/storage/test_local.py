"""
Test serac/storage/s3.py
"""
from configparser import ConfigParser
from io import BytesIO
from pathlib import Path

import pytest

from serac import crypto
from serac.storage import Local

from ..mocks import FilesystemTest


class TestLocal(FilesystemTest):
    def test_init__path_required(self):
        parser = ConfigParser()
        parser.read_string(
            """
            [archive]
            storage = local
            """
        )

        with pytest.raises(ValueError) as e:
            Local.parse_config(parser["archive"])
        assert str(e.value) == "Local storage requires a path"

    def test_store(self, fs):
        # This will be tested in a separate test, but we'll focus on the store aspect
        fs.create_file("/src/foo", contents="unencrypted")
        fs.create_dir("/store")
        storage = Local(path=Path("/store/"))

        # Encrypt and push to storage
        storage.store(
            local_path=Path("/src/foo"), archive_id=str("1"), password="secret"
        )

        # Check file exists in /store/
        dest_path = Path("/store/1")
        assert dest_path.is_file()

        # Check it has been encrypted and we can decrypt it
        decrypted = BytesIO()
        with dest_path.open("rb") as handle:
            crypto.decrypt(handle, decrypted, "secret", dest_path.stat().st_size)
        assert str(decrypted.getvalue(), "utf-8") == "unencrypted"

    def test_retrieve(self, fs):
        # Encrypt and deliver. This is tested in a separate test
        fs.create_file("/src/foo", contents="unencrypted")
        fs.create_dir("/store")
        fs.create_dir("/dest")
        storage = Local(path=Path("/store/"))
        storage.store(local_path=Path("/src/foo"), archive_id=str(1), password="secret")

        # Pull and decrypt from storage
        storage.retrieve(
            local_path=Path("/dest/bar"), archive_id=str(1), password="secret"
        )

        # Check file exists in /dest/
        dest_path = Path("/dest/bar")
        assert dest_path.is_file()

        # Check it has been decrypted
        with dest_path.open("r") as handle:
            content = handle.read()
        assert content == "unencrypted"
