"""
Storage base class
"""
from configparser import ConfigParser
from typing import Any, Dict


storage_registry = {}


class StorageType(type):
    def __init__(cls, name, bases, attrs):
        super().__init__(name, bases, attrs)
        storage_registry[name] = cls


class Storage:
    __metaclass__ = StorageType

    @classmethod
    def from_config(cls, config: ConfigParser) -> Storage:
        kwargs: Dict[str: Any] = cls.parse_config(config)
        return cls(**kwargs)

    def parse_config(cls, config: ConfigParser) -> Dict[str, Any]:
        return {}
