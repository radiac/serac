"""
Light wrapper around the encryption library
"""
from typing import IO

from pyAesCrypt import decryptStream, encryptStream


# Encryption/decryption buffer size - 64K
BUFFER_SIZE = 64 * 1024


def encrypt(source: IO[bytes], destination: IO[bytes], password: str) -> None:
    encryptStream(source, destination, password, BUFFER_SIZE)


def decrypt(
    source: IO[bytes], destination: IO[bytes], password: str, source_size: int
) -> None:
    decryptStream(source, destination, password, BUFFER_SIZE, source_size)
