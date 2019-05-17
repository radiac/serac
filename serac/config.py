"""
Config parsing
"""
from configparser import ConfigParser
from pathlib import Path
from typing import List, Union

from .storage import Storage, storage_registry


class SectionConfig:
    """
    Base for section config objects
    """
    @property
    def section_name(self):
        return self.__name__[:-len('Config')].lower()

    def parse(self, section: ConfigParser):
        raise NotImplementedError()


class SourceConfig(SectionConfig):
    """
    Source config container
    """
    includes: List[str]
    excludes: List[str]

    def parse(self, section: ConfigParser) -> None:
        self.includes = section.get('include', '').split()
        self.excludes = section.get('exclude', '').split()

        if not self.includes:
            raise ValueError(
                'The source section must declare at least one include'
            )


class DestinationConfig(SectionConfig):
    """
    Destination config container
    """
    storage: Storage
    password: Union[str, None]

    def parse(self, section: ConfigParser) -> None:
        storage_type = section.get('storage', '')
        self.password = section.get('password', '')

        if not storage_type:
            raise ValueError(
                'The destination section must declare a storage type'
            )

        # Look up storage type in registry and get it to parse config
        storage_cls = storage_registry.get(storage_type)
        if not storage_cls:
            raise ValueError(
                f'The destination storage {storage_type} is not recognised'
            )
        self.storage = storage_cls.from_config(section)


class IndexConfig(SectionConfig):
    """
    Index config container
    """
    path: str

    def parse(self, section: ConfigParser) -> None:
        self.path = section.get('path', '')

        if not self.path:
            raise ValueError('The index section must declare a path')


class Config:
    """
    Configuration file loader
    """
    sections = ['source', 'destination', 'index']
    source: SourceConfig
    destination: DestinationConfig
    index: IndexConfig

    def __init__(self, path: Path = None) -> None:
        if path:
            self.load(path)

    def load(self, path: Path) -> None:
        parser = ConfigParser()
        parser.read(path)

        if sorted(parser.sections()) != sorted(self.sections):
            raise ValueError(
                'Invalid config file; must contain source, destination and '
                f'index sections; instead found {", ".join(parser.sections())}'
            )

        self.source = SourceConfig()
        self.destination = DestinationConfig()
        self.index = IndexConfig()
        for section in self.sections:
            getattr(self, section).parse(parser[section])
