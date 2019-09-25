"""
Config parsing
"""
from __future__ import annotations

from configparser import ConfigParser, SectionProxy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Type, TypeVar

from .storage import Storage, storage_registry


T = TypeVar("T", bound="SectionConfig")


@dataclass
class SectionConfig:
    """
    Base for section config objects
    """

    @classmethod
    def from_config(cls: Type[T], config: SectionProxy) -> T:
        kwargs: Dict[str, Any] = cls.parse_config(config)
        # mypy has a problem with dataclasses, so ignore the typing error
        return cls(**kwargs)  # type: ignore

    @classmethod
    def parse_config(self, section: SectionProxy) -> Dict[str, Any]:
        raise NotImplementedError()  # pragma: no cover


@dataclass
class SourceConfig(SectionConfig):
    """
    Source config container
    """

    includes: List[str]
    excludes: List[str]

    @classmethod
    def parse_config(self, section: SectionProxy) -> Dict[str, Any]:
        includes = section.get("include", "").split()
        excludes = section.get("exclude", "").split()

        if not includes:
            raise ValueError("The source section must declare at least one include")

        return {"includes": includes, "excludes": excludes}


@dataclass
class ArchiveConfig(SectionConfig):
    """
    Archive config container
    """

    storage: Storage
    password: str

    @classmethod
    def parse_config(self, section: SectionProxy) -> Dict[str, Any]:
        storage_type = section.get("storage", "")
        password = section.get("password", "")

        if not storage_type:
            raise ValueError("The archive section must declare a storage type")

        # Look up storage type in registry and get it to parse config
        storage_cls = storage_registry.get(storage_type)
        if not storage_cls:
            raise ValueError(f"The archive storage '{storage_type}' is not recognised")
        storage = storage_cls.from_config(section)

        return {"storage": storage, "password": password}


@dataclass
class IndexConfig(SectionConfig):
    """
    Index config container
    """

    path: Path

    @classmethod
    def parse_config(self, section: SectionProxy) -> Dict[str, Any]:
        path_raw: str = section.get("path", "")

        if not path_raw:
            raise ValueError("The index section must declare a path")
        path = Path(path_raw)
        if not path.parent.exists():
            raise ValueError("The path for the index does not exist")

        return {"path": path}


class Config:
    """
    Configuration file loader
    """

    sections = ["source", "archive", "index"]
    source: SourceConfig
    archive: ArchiveConfig
    index: IndexConfig

    def __init__(self, filename: str = None) -> None:
        if filename:
            self.load(filename)

    def load(self, filename: str) -> None:
        parser = ConfigParser()

        # Let parsing errors go through unchanged
        parser.read(filename)

        if sorted(parser.sections()) != sorted(self.sections):
            raise ValueError(
                "Invalid config file; must contain source, archive and "
                f"index sections; instead found {', '.join(parser.sections())}"
            )

        self.source = SourceConfig.from_config(parser["source"])
        self.archive = ArchiveConfig.from_config(parser["archive"])
        self.index = IndexConfig.from_config(parser["index"])
