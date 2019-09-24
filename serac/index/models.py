"""
Database models
"""
from __future__ import annotations

import grp
import pwd
from datetime import datetime
from enum import IntEnum
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from peewee import CharField, ForeignKeyField, IntegerField, TextField

from .database import EnumField, Model, PathField


if TYPE_CHECKING:
    from ..config import ArchiveConfig  # pragma: no cover


_uid_cache: Dict[int, str] = {}
_gid_cache: Dict[int, str] = {}


def uid_to_name(uid: int) -> str:
    """
    Given a system user, try to resolve it on the current system
    """
    if uid not in _uid_cache:
        try:
            _uid_cache[uid] = pwd.getpwuid(uid).pw_name
        except (AttributeError, KeyError):
            _uid_cache[uid] = str(uid)
    return _uid_cache[uid]


def gid_to_name(gid: int) -> str:
    """
    Given a system group, try to resolve it on the current system
    """
    if gid not in _gid_cache:
        try:
            _gid_cache[gid] = grp.getgrgid(gid).gr_name
        except (AttributeError, KeyError):
            _gid_cache[gid] = str(gid)
    return _gid_cache[gid]


class Action(IntEnum):
    ADD = 1
    CONTENT = 2
    METADATA = 3
    DELETE = 4


class Archived(Model):
    """
    Represents an object stored in the archive

    Identified by a sha256 hash
    """

    hash: Union[TextField, str] = CharField(max_length=64)
    size: Union[IntegerField, int] = IntegerField()

    def get_human_size(self):
        size = self.size
        for unit in ["", "K", "M", "G", "T"]:
            if size < 1024:
                break
            if unit != "T":
                size /= 1024.0
        return size, unit


class File(Model):
    """
    A file at a path
    """

    path: Union[PathField, Path] = PathField()
    archived: Union[ForeignKeyField, Archived] = ForeignKeyField(
        Archived, backref="files"
    )
    action: Union[EnumField, Action] = EnumField(Action)
    last_modified: Union[IntegerField, int] = IntegerField()
    owner: Union[IntegerField, int] = IntegerField()
    group: Union[IntegerField, int] = IntegerField()
    permissions: Union[IntegerField, int] = IntegerField()

    _meta_fields = [
        # attributes
        "last_modified",
        "owner",
        "group",
        "permissions",
        #
        # cached property, calculated or read from self.archived
        "size",
    ]
    _cached_hash: Optional[str] = None
    _size: Optional[int] = None

    def __str__(self):
        return str(self.path)

    def __eq__(self, other) -> bool:
        """
        Check if path and metadata match
        """
        return self.path == other.path and all(
            [getattr(self, attr) == getattr(other, attr) for attr in self._meta_fields]
        )

    def clone(self, **overrides) -> File:
        # Copy all field values
        attrs: Dict[str, Any] = {
            field_name: getattr(self, field_name)
            for field_name in File._meta.fields.keys()
            if field_name not in ["id", "archived"]
        }
        try:
            attrs["archived"] = self.archived
        except Archived.DoesNotExist:
            pass
        attrs.update(overrides)
        return File(**attrs)

    def refresh_metadata_from_disk(self) -> None:
        """
        Update metadata by checking the path on disk
        """
        if not self.path.exists():
            raise ValueError(f"File {self.path} has disappeared")
        if not self.path.is_file():
            raise ValueError(f"File {self.path} is not a file")
        stat = self.path.stat()
        self.last_modified = int(stat.st_mtime)
        self._size = stat.st_size
        self.owner = stat.st_uid
        self.group = stat.st_gid
        self.permissions = stat.st_mode

    @property
    def size(self) -> int:
        if self._size is None:
            try:
                if self.archived:
                    return self.archived.size
            except Archived.DoesNotExist:
                raise ValueError("Cannot access size without metadata")
        return self._size  # type: ignore  # mypy doesn't understand

    @property
    def owner_display(self) -> str:
        """
        Return the owner username according to this system
        """
        return uid_to_name(self.owner)

    @property
    def group_display(self) -> str:
        """
        Return the owner username according to this system
        """
        return gid_to_name(self.group)

    @property
    def permissions_display(self) -> str:
        """
        Return permissions as a human-readable 10 character string, eg:

            -rwxr-xr-x
        """
        if not self.permissions:
            return "-" * 10
        parts = ["-"]
        bits = [(4, "r"), (2, "w"), (1, "x")]
        for perm_char in oct(self.permissions)[-3:]:
            perm = int(perm_char)
            for bit, label in bits:
                if perm >= bit:
                    parts.append(label)
                    perm -= bit
                else:
                    parts.append("-")
        return "".join(parts)

    def get_human_last_modified(self) -> List[str]:
        """
        Return last modified date as tuple ready to be rendered as a
        human-readable string::

            (month_abbr, day_num, year, HH:MM)
        """
        if not self.last_modified:
            return ["", "", "", ""]

        dt = datetime.utcfromtimestamp(self.last_modified)
        dt_local = dt.astimezone()
        return dt_local.strftime("%b %d %Y %H:%M").split(" ")

    def calculate_hash(self, force=False) -> str:
        """
        Calculate file hash
        """
        # Based on:
        #   https://gist.github.com/aunyks/042c2798383f016939c40aa1be4f4aaf
        if not self._cached_hash:
            # Specify how many bytes of the file you want to open at a time
            block_size = 65536
            sha = sha256()
            with self.path.open("rb") as file:
                file_buffer = file.read(block_size)
                while len(file_buffer) > 0:
                    sha.update(file_buffer)
                    file_buffer = file.read(block_size)

            self._cached_hash = sha.hexdigest()

        return self._cached_hash

    def archive(self, archive_config: ArchiveConfig) -> None:
        """
        Push to the archive

        Creates Archived object and sets it on this object, saving this File object
        """
        # Ensure this object is not yet in the database
        # If it is, it will already have been archived (File.archived is required)
        if self.id:
            raise ValueError("Cannot archive a file twice")

        # Create Archived object with hash to get ID
        # This should be created regardless of whether the archive succeeds
        archived = Archived.create(hash=self.calculate_hash(), size=self.size)

        try:
            # Store the file
            archive_config.storage.store(
                local_path=self.path,
                archive_id=str(archived.id),
                password=archive_config.password,
            )

        except Exception as e:
            # Null the Archived hash rather than delete it, to prevent it being reused
            archived.hash = ""
            archived.save()
            raise ValueError(f"Unable to archive {self.path}: {e}")

        else:
            # Link archived object to this file
            self.archived = archived
            self.save()

    def restore(self, archive_config: ArchiveConfig, to: Path) -> None:
        """
        Restore from the archive
        """
        archive_config.storage.retrieve(
            local_path=to,
            archive_id=str(self.archived.id),
            password=archive_config.password,
        )
