"""
Local storage
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, BinaryIO, Dict, TYPE_CHECKING

from .base import Storage

if TYPE_CHECKING:
    from configparser import ConfigParser


class Local(Storage):
    """
    Local storage
    """

    path: Path

    @classmethod
    def parse_config(cls, config: ConfigParser) -> Dict[str, Any]:
        return {"path": config.get("path", "")}

    def __init__(self, path: str) -> None:
        if not path:
            raise ValueError("Local storage requires a path")

        self.path = Path(path)

    def get_size(self, filename: str) -> int:
        file: Path = self.path / filename
        return file.stat().st_size

    def read(self, filename: str) -> BinaryIO:
        handle: BinaryIO = open(self.path / filename, "rb")
        return handle

    def write(self, filename: str) -> BinaryIO:
        handle: BinaryIO = open(self.path / filename, "wb")
        return handle
