"""
Local storage
"""
from __future__ import annotations

from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Dict

from .base import Storage


if TYPE_CHECKING:
    from configparser import ConfigParser  # pragma: no cover


class Local(Storage):
    """
    Local storage
    """

    path: Path

    @classmethod
    def parse_config(cls, config: ConfigParser) -> Dict[str, Any]:
        path = config.get("path", "")
        if not path:
            raise ValueError("Local storage requires a path")
        return {"path": Path(path)}

    def __init__(self, path: Path) -> None:
        self.path = path

    def get_size(self, archive_id: str) -> int:
        file: Path = self.path / archive_id
        return file.stat().st_size

    def read(self, archive_id: str) -> IO[bytes]:
        handle: IO[bytes] = open(self.path / archive_id, "rb")
        return handle

    def write(self, archive_id: str) -> IO[bytes]:
        handle: IO[bytes] = open(self.path / archive_id, "wb")
        return handle
