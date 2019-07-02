"""
Test serac/config.py
"""
from pathlib import Path

from serac.config import Config, SourceConfig, DestinationConfig, IndexConfig
from serac.storage import Local, S3


SAMPLE = """# Sample config file

[source]
# Define the source for the backups

# List of paths to include and exclude (glob patterns)
include =
    /path/to/source
    /path/somewhere/else
exclude =
    /path/to/source/unprocessed
    /path/somewhere/else/*.jpg

[destination]
# Define where the backups are saved

{storage}

# Encrypt backups with this password
password = l0ng_s3cr3t

[index]
# Define how indexed files are treated

# Location where indexes are stored
# This should then be backed up by another service, eg duplicity
path = /path/to/indexes
"""

storage_local = """# Backup to a local path
storage = local
path = /path/to/backup
"""

storage_s3 = """# Backup to S3
storage = s3
key = 4p1_k3y
secret = 53cr3t
bucket = arn:aws:s3:::my_bucket_name
path = path/within/bucket
"""


def test_parser_source(fs):
    fs.create_file("/sample.conf", contents=SAMPLE.format(storage=storage_local))
    fs.create_dir("/path/to/indexes")
    fs.create_dir("/path/to/backup")
    config = Config(path=Path("/sample.conf"))

    assert isinstance(config.source, SourceConfig)
    assert config.source.includes == ["/path/to/source", "/path/somewhere/else"]
    assert config.source.excludes == [
        "/path/to/source/unprocessed",
        "/path/somewhere/else/*.jpg",
    ]


def test_parser_destimation__local(fs):
    fs.create_file("/sample.conf", contents=SAMPLE.format(storage=storage_local))
    fs.create_dir("/path/to/indexes")
    fs.create_dir("/path/to/backup")
    config = Config(path=Path("/sample.conf"))

    assert isinstance(config.destination, DestinationConfig)
    assert isinstance(config.destination.storage, Local)
    assert config.destination.storage.path == Path("/path/to/backup")
    assert config.destination.password == "l0ng_s3cr3t"


def test_parser_destimation__s3(fs):
    fs.create_file("/sample.conf", contents=SAMPLE.format(storage=storage_s3))
    fs.create_dir("/path/to/indexes")
    config = Config(path=Path("/sample.conf"))

    assert isinstance(config.destination, DestinationConfig)
    assert isinstance(config.destination.storage, S3)
    assert config.destination.storage.key == "4p1_k3y"
    assert config.destination.storage.secret == "53cr3t"
    assert config.destination.storage.bucket == "arn:aws:s3:::my_bucket_name"
    assert config.destination.storage.path == "path/within/bucket"
    assert config.destination.password == "l0ng_s3cr3t"


def test_parser_index(fs):
    fs.create_file("/sample.conf", contents=SAMPLE.format(storage=storage_local))
    fs.create_dir("/path/to/indexes")
    fs.create_dir("/path/to/backup")
    config = Config(path=Path("/sample.conf"))

    assert isinstance(config.index, IndexConfig)
    assert config.index.path == Path("/path/to/indexes")
