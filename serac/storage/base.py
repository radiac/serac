"""
Storage base class
"""
from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path
from typing import IO, Any, Dict

from ..crypto import decrypt, encrypt
from ..exceptions import FileExists


storage_registry = {}


class StorageType(type):
    def __init__(cls, name, bases, attrs):
        super().__init__(name, bases, attrs)
        if attrs.get("abstract", False):
            return
        storage_registry[name.lower()] = cls


class Storage(metaclass=StorageType):

    abstract = True

    def __init__(self, **kwargs: Dict[str, Any]):
        pass

    @classmethod
    def from_config(cls, config: ConfigParser) -> Storage:
        kwargs: Dict[str, Any] = cls.parse_config(config)
        return cls(**kwargs)

    @classmethod
    def parse_config(cls, config: ConfigParser) -> Dict[str, Any]:
        raise NotImplementedError(
            "Storage.parse_config must be implemented by subclasses"
        )  # pragma: no cover

    def store(self, local_path: Path, archive_id: str, password: str) -> None:
        source: IO[bytes]
        with local_path.open("rb") as source:
            destination = self.write(archive_id)
            encrypt(source=source, destination=destination, password=password)
            destination.close()

    def retrieve(self, local_path: Path, archive_id: str, password: str) -> None:
        # Don't want to retrieve it if it already exists
        if local_path.exists():
            raise FileExists(local_path)

        source_size = self.get_size(archive_id)
        source = self.read(archive_id)
        destination: IO[bytes]
        with local_path.open("wb") as destination:
            decrypt(source, destination, password, source_size)
        source.close()

    def get_size(self, archive_id: str) -> int:
        """
        Return the size of the file
        """
        raise NotImplementedError(
            "Storage.get_size must be implemented by subclasses"
        )  # pragma: no cover

    def read(self, archive_id: str) -> IO[bytes]:
        """
        Return an IO object to read from
        """
        raise NotImplementedError(
            "Storage.read must be implemented by subclasses"
        )  # pragma: no cover

    def write(self, archive_id: str) -> IO[bytes]:
        """
        Return an IO object to write to
        """
        raise NotImplementedError(
            "Storage.write must be implemented by subclasses"
        )  # pragma: no cover
