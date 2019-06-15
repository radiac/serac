"""
Database models
"""
from __future__ import annotations
from enum import IntEnum
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Optional, Union, TYPE_CHECKING

from peewee import CharField, DateTimeField, IntegerField, ForeignKeyField, TextField

from .database import Model, EnumField

if TYPE_CHECKING:
    from datetime import datetime

    from ..config import DestinationConfig


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


class File(Model):
    """
    A file at a path
    """

    path: Union[TextField, str] = TextField()
    archived: Union[ForeignKeyField, Archived] = ForeignKeyField(
        Archived, backref="files"
    )
    action: Union[EnumField, Action] = EnumField(Action)
    last_modified: Union[DateTimeField, datetime] = DateTimeField()
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
        return self.path

    def clone(self, **overrides) -> File:
        # Copy all field values
        attrs: Dict[str, Any] = {
            field_name: field
            for field_name, field in File._meta.fields.items()
            if not field_name == "id"
        }
        attrs.update(overrides)
        return File(**attrs)

    def get_path(self):
        """
        Return a pathlib.Path for self.path
        """
        path = Path(self.path)
        return path

    def refresh_metadata_from_disk(self):
        """
        Update metadata by checking the path on disk
        """
        path = self.get_path()
        if not path.exists():
            raise ValueError(f"File {self.path} has disappeared")
        if not path.is_file():
            raise ValueError(f"File {self.path} is not a file")
        stat = path.stat()
        self.last_modified = stat.st_mtime
        self._size = stat.st_size
        self.owner = stat.st_uid
        self.group = stat.st_gid
        self.permissions = stat.st_mode

    @property
    def size(self):
        if self._size is None:
            if self.archived:
                return self.archived.size
            raise ValueError("Cannot access size without a lookup")
        return self._size

    def has_metadata_changed(self, other):
        """
        Check if path and metadata match
        """
        return not (
            self.path == other.path
            and all(
                [
                    getattr(self, attr) == getattr(other, attr)
                    for attr in self._meta_fields
                ]
            )
        )

    def calculate_hash(self, force=False):
        """
        Calculate file hash
        """
        # Based on:
        #   https://gist.github.com/aunyks/042c2798383f016939c40aa1be4f4aaf
        if not self._cached_hash:
            # Specify how many bytes of the file you want to open at a time
            block_size = 65536
            sha = sha256()
            with self.get_path().open("rb") as file:
                file_buffer = file.read(block_size)
                while len(file_buffer) > 0:
                    sha.update(file_buffer)
                    file_buffer = file.read(block_size)

            self._cached_hash = sha.hexdigest()

        return self._cached_hash

    def archive(self, destination: DestinationConfig):
        """
        Push to the archive

        Creates Archived object and sets it on this object, saving this File object
        """
        # Create Archived object with hash to get ID
        # This should be created regardless of whether the archive succeeds
        archived = Archived.create(hash=self.calculate_hash(), size=self.size)

        try:
            # Store the file
            destination.storage.store(
                local_path=self.path, id=archived.id, password=destination.password
            )

        except Exception as e:
            # Null the Archived hash rather than delete it, to prevent it being reused
            archived.hash = None
            archived.save()

            # Remove this entry from the database to allow it to be re-run
            if self.id:
                self.delete()

            raise ValueError(f"Unable to archive {self.path}: {e}")

        else:
            # Link archived object to this file
            self.archived = archived
            self.save()
