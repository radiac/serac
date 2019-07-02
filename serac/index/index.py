"""
Index management
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from fnmatch import fnmatchcase
from glob import iglob
from itertools import chain
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from peewee import fn

from .models import Action, File, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import DestinationConfig


class Changeset:
    """
    Set of changes from an index scan
    """

    added: Dict[Path, File]
    content: Dict[Path, File]
    metadata: Dict[Path, File]
    deleted: Dict[Path, File]

    def __init__(self):
        self.added = defaultdict(File)
        self.content = defaultdict(File)
        self.metadata = defaultdict(File)
        self.deleted = defaultdict(File)

    def commit(self, destination: DestinationConfig) -> None:
        for file in chain(self.metadata.values(), self.deleted.values()):
            file.save()

        for file in chain(self.added.values(), self.content.values()):
            file.archive(destination)


def get_state_at(when: datetime) -> Dict[Path, File]:
    file_fields = File._meta.sorted_fields + [
        fn.MAX(File.last_modified).alias("latest_modified")
    ]
    files = (
        File.select(*file_fields)
        .where(File.last_modified <= when)
        .group_by(File.path)
        .having(File.action != Action.DELETE)
    )
    return {file.path: file for file in files}


def is_excluded(path: Path, excludes: List[str]) -> bool:
    for pattern in excludes:
        if fnmatchcase(str(path), pattern):
            return True
    return False


def scan(includes: List[str], excludes: Optional[List[str]] = None) -> Changeset:
    """
    Scan specified path and return a Changeset
    """
    path: Path
    path_str: str
    file: File

    include_paths: Iterator[Path] = chain.from_iterable(
        ((Path(globbed) for globbed in iglob(path_str)) for path_str in includes)
    )

    changeset = Changeset()
    last_state = get_state_at(when=datetime.now())

    while True:
        # Get next path
        try:
            path = next(include_paths)
        except StopIteration:
            break

        # Run exclusions
        if excludes and is_excluded(path, excludes):
            continue

        # Examine path
        if path.is_dir():
            # Valid path, but we don't index dirs themselves - search it
            include_paths = chain(include_paths, path.iterdir())
            continue

        # Create File and collect metadata
        file = File(path=path)
        file.refresh_metadata_from_disk()

        # Diff path against last_state (removing so we know we've seen it)
        last_file = last_state.pop(path, None)
        if last_file is None:
            # Added
            file.action = Action.ADD
            changeset.added[path] = file

        elif file != last_file:
            # Something changed

            # If last_modified changed, check the hash
            file_hash = file.calculate_hash()
            if file_hash != last_file.archived.hash:
                # Content has changed
                file.action = Action.CONTENT
                changeset.content[path] = file
            else:
                # Just metadata
                file.action = Action.METADATA
                file.archived = last_file.archived
                changeset.metadata[path] = file

    # All remaining files in the state were deleted
    changeset.deleted = {
        path: file.clone(action=Action.DELETE) for path, file in last_state.items()
    }
    return changeset
