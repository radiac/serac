"""
Test serac/crypto.py
"""
from pathlib import Path

from serac.crypto import decrypt, encrypt

from .mocks import FilesystemTest


class TestCrypto(FilesystemTest):
    """
    Test Crypto operations
    """

    def test_encrypt(self, fs):
        fs.create_file("/test/raw.txt", contents="value")
        with Path("/test/raw.txt").open("rb") as src:
            with Path("/test/encrypted.txt").open("wb") as dest:
                encrypt(src, dest, "secret")

        with Path("/test/raw.txt").open("r") as f:
            contents = f.read()
        assert contents == "value"

        with Path("/test/encrypted.txt").open("rb") as f:
            contents = f.read()
        assert contents != ""
        assert contents != "value"

    def test_decrypt(self, fs):
        # Encrypt so we can decrypt
        fs.create_file("/test/raw.txt", contents="value")
        with Path("/test/raw.txt").open("rb") as src:
            with Path("/test/encrypted.txt").open("wb") as dest:
                encrypt(src, dest, "secret")

        encrypted = Path("/test/encrypted.txt")
        with encrypted.open("rb") as src:
            with Path("/test/decrypted.txt").open("wb") as dest:
                decrypt(src, dest, "secret", encrypted.stat().st_size)

        with Path("/test/decrypted.txt").open("r") as f:
            contents = f.read()
        assert contents == "value"
