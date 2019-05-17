"""
Index management
"""
from collections import defaultdict
from datetime import datetime
from glob import iglob
from itertools import chain
from pathlib import Path
from typing import Dict, List

from peewee import fn

from .models import Action, File


class Changeset:
    """
    Set of changes from an index scan
    """
    added: Dict[str, File]
    content: Dict[str, File]
    meta: Dict[str, File]
    deleted: Dict[str, File]

    def __init__(self):
        self.added = defaultdict(File)
        self.content = defaultdict(File)
        self.meta = defaultdict(File)
        self.deleted = defaultdict(File)


def get_state_at(when: datetime) -> Dict[str, File]:
    file_fields = File._meta.sorted_fields + [
        fn.MAX(File.last_modified).alias('latest_modified')
    ]
    files = (
        File
        .select(*file_fields)
        .where(File.last_modified <= when)
        .group_by(File.path)
        .having(File.action != Action.DELETE)
    )
    return {file.path: file for file in files}


def scan(includes: List[str], excludes: List[str]) -> Changeset:
    """
    Scan specified path and return a Changeset
    """
    path_str: str
    include_paths = chain(*[
        iglob(path_str) for path_str in includes
    ])
    exclude_matches = chain(*[
        iglob(path_str) for path_str in excludes
    ])

    changeset = Changeset()
    last_state = get_state_at(when=datetime.now())

    path: Path
    while True:
        # Get next valid path
        try:
            path_str = next(include_paths)
        except StopIteration:
            break
        if path_str in exclude_matches:
            continue

        # Examine path
        path = Path(path_str)
        if path.is_dir():
            # Valid path, but we don't index dirs themselves - search it
            include_paths = chain(include_paths, [path_str])
            continue

        # Create File and collect metadata
        file = File(path=path)
        file.refresh_metadata_from_disk()

        # Diff path against last_state (removing so we know we've seen it)
        last_file = last_state.pop(path_str, None)
        if last_file is None:
            # Added
            changeset.added[path_str] = file

        elif file.has_metadata_changed(last_file):
            # Something changed

            # If last_modified changed, check the hash
            file_hash = file.calculate_hash()
            if file_hash != last_file.stored.hash:
                # Content has changed
                changeset.content[path_str] = file
            else:
                # Just metadata
                changeset.meta[path_str] = file

    # All remaining files in the state were deletd
    changeset.deleted = last_state
    return changeset
