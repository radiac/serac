"""
Index management
"""
from __future__ import annotations

from collections import defaultdict
from fnmatch import fnmatchcase
from glob import iglob
from itertools import chain
from pathlib import Path
from time import time
from typing import Dict, Iterator, List, Optional

from peewee import fn

from .models import Action, File, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import ArchiveConfig


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

    def commit(self, archive_config: ArchiveConfig) -> None:
        for file in chain(self.metadata.values(), self.deleted.values()):
            file.save()

        for file in chain(self.added.values(), self.content.values()):
            file.archive(archive_config)


def get_state_at(timestamp: int) -> Dict[Path, File]:
    """
    Get the state of the index at a given timestamp
    """
    if not isinstance(timestamp, int):
        # This is going to be a common error, and we don't want to convert it
        # ourselves - we won't have the timezone info and we'll make a mistake
        raise ValueError("Can only get state using a timestamp")

    file_fields = File._meta.sorted_fields + [
        fn.MAX(File.last_modified).alias("latest_modified")
    ]
    files = (
        File.select(*file_fields)
        .where(File.last_modified <= timestamp)
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
    last_state = get_state_at(timestamp=int(time()))

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


def search(timestamp: int, filter_str: Optional[str] = None):
    """
    Search the index at the specified timestamp matching the specified filter string.

    Returns a list of File objects, ordered by path
    """
    state: Dict[Path, File] = get_state_at(timestamp)
    path: Path

    filter_path = None
    if filter_str:
        filter_path = Path(filter_str)

    files: List[File]
    if filter_path:
        files = [
            file
            for path, file in state.items()
            if filter_path == path or filter_path in path.parents
        ]
    else:
        files = list(state.values())

    return files


def restore(
    archive_config: ArchiveConfig,
    timestamp: int,
    out_path: Path,
    archive_path: Optional[Path] = None,
    missing_ok: bool = False,
) -> int:
    """
    Restore one or more files as they were at the specified timestamp, to the
    specified out path.

    If no archive path is specified, restores all files with their full paths
    under the specified target path.

    If an archive path is specified, restores that file or all files under that
    path into the specified target path.
    """
    if not isinstance(timestamp, int):
        # This is going to be a common error, and we don't want to convert it
        # ourselves - we won't have the timezone info and we'll make a mistake
        raise ValueError("Can only restore using a timestamp")
    state: Dict[Path, File] = get_state_at(timestamp)

    if archive_path in state:
        if out_path.is_dir():
            out_path /= archive_path.name

    path: Path
    file: File
    restored = 0
    for path, file in state.items():
        if not archive_path or archive_path == path or archive_path in path.parents:
            if archive_path:
                target_path = out_path / file.path.relative_to(archive_path)
            else:
                target_path = out_path / file.path.relative_to("/")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            file.restore(archive_config=archive_config, to=target_path)
            restored += 1

    if not missing_ok and not restored:
        if archive_path:
            raise FileNotFoundError("Requested path not found in archive")
        else:
            raise FileNotFoundError("Archive is empty")

    return restored
