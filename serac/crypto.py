"""
Light wrapper around the encryption library
"""
from typing import BinaryIO

from pyAesCrypt import encryptStream, decryptStream

# Encryption/decryption buffer size - 64K
BUFFER_SIZE = 64 * 1024


def encrypt(source: BinaryIO, destination: BinaryIO, password: str) -> None:
    encryptStream(source, destination, password, BUFFER_SIZE)


def decrypt(
    source: BinaryIO, destination: BinaryIO, password: str, source_size: int
) -> None:
    decryptStream(source, destination, password, BUFFER_SIZE, source_size)
