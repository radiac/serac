"""
Database models
"""
from enum import IntEnum
from hashlib import sha256
from pathlib import Path

from peewee import CharField, DateTimeField, IntegerField, ForeignKeyField, TextField

from .database import Model, EnumField


class Action(IntEnum):
    ADD = 1
    CHANGE = 2
    META = 3
    DELETE = 4


class Stored(Model):
    """
    Represents a stored object

    Identified by a sha256 hash
    """

    hash = CharField(max_length=64)


class File(Model):
    """
    A file at a path
    """

    path = TextField()
    stored = ForeignKeyField(Stored, backref="files")
    action = EnumField(Action)
    last_modified = DateTimeField()
    size = IntegerField()
    owner = IntegerField()
    group = IntegerField()
    permissions = IntegerField()

    _cached_hash: str

    def get_path(self):
        """
        Return a pathlib.Path for self.path
        """
        return Path(self.path)

    def refresh_metadata_from_disk(self):
        """
        Update metadata by checking the path on disk
        """
        stat = self.get_path().stat()
        self.last_modified = stat.st_mtime
        self.size = stat.st_size
        self.owner = stat.st_uid
        self.group = stat.st_gid
        self.permissions = stat.st_mode

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

    def has_metadata_changed(self, other):
        """
        Check if path and metadata match
        """
        return not (
            self.path == other.path
            and self.last_modified == other.last_modified
            and self.size == other.size
            and self.owner == other.owner
            and self.group == other.group
            and self.permissions == other.permissions
        )
