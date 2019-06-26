"""
Storage base class
"""
from __future__ import annotations

from configparser import ConfigParser
from typing import Any, BinaryIO, Dict

from ..crypto import encrypt, decrypt


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
        return {}

    def store(self, local_path: str, id: int, password: str):
        source: BinaryIO
        with open(local_path, "rb") as source:
            destination = self.write(str(id))
            encrypt(source=source, destination=destination, password=password)
            destination.close()

    def retrieve(self, local_path: str, id: int, password: str):
        source_size = self.get_size(str(id))
        source = self.read(str(id))
        destination: BinaryIO
        with open(local_path, "wb") as destination:
            decrypt(source, destination, password, source_size)
        source.close()

    def get_size(self, filename: str) -> int:
        """
        Return the size of the file
        """
        raise NotImplementedError("Storage.get_size must be implemented by subclasses")

    def read(self, filename: str) -> BinaryIO:
        """
        Return an IO object to read from
        """
        raise NotImplementedError("Storage.read must be implemented by subclasses")

    def write(self, filename: str) -> BinaryIO:
        """
        Return an IO object to write to
        """
        raise NotImplementedError("Storage.write must be implemented by subclasses")
