"""
Test serac/config.py
"""
from configparser import ConfigParser
from pathlib import Path

import pytest

from serac.config import ArchiveConfig, Config, IndexConfig, SourceConfig
from serac.storage import S3, Local

from .mocks import SAMPLE_CONFIG, SAMPLE_STORAGE_LOCAL, SAMPLE_STORAGE_S3


def test_parser_source__valid(fs):
    fs.create_file(
        "/sample.conf", contents=SAMPLE_CONFIG.format(storage=SAMPLE_STORAGE_LOCAL)
    )
    fs.create_dir("/path/to")
    fs.create_dir("/path/to/backup")
    config = Config(filename="/sample.conf")

    assert isinstance(config.source, SourceConfig)
    assert config.source.includes == ["/path/to/source", "/path/somewhere/else"]
    assert config.source.excludes == [
        "/path/to/source/unprocessed",
        "/path/somewhere/else/*.jpg",
    ]


def test_parser_source__missing_includes__raises_exception():
    parser = ConfigParser()
    parser.read_string(
        """
        [source]
        excludes = one
        """
    )

    with pytest.raises(ValueError) as e:
        SourceConfig.from_config(parser["source"])
    assert str(e.value) == "The source section must declare at least one include"


def test_parser_archive__local(fs):
    fs.create_file(
        "/sample.conf", contents=SAMPLE_CONFIG.format(storage=SAMPLE_STORAGE_LOCAL)
    )
    fs.create_dir("/path/to")
    fs.create_dir("/path/to/backup")
    config = Config(filename="/sample.conf")

    assert isinstance(config.archive, ArchiveConfig)
    assert isinstance(config.archive.storage, Local)
    assert config.archive.storage.path == Path("/path/to/backup")
    assert config.archive.password == "l0ng_s3cr3t"


def test_parser_archive__s3(fs):
    fs.create_file(
        "/sample.conf", contents=SAMPLE_CONFIG.format(storage=SAMPLE_STORAGE_S3)
    )
    fs.create_dir("/path/to")
    config = Config(filename="/sample.conf")

    assert isinstance(config.archive, ArchiveConfig)
    assert isinstance(config.archive.storage, S3)
    assert config.archive.storage.key == "4p1_k3y"
    assert config.archive.storage.secret == "53cr3t"
    assert config.archive.storage.bucket == "arn:aws:s3:::my_bucket_name"
    assert config.archive.storage.path == "path/within/bucket"
    assert config.archive.password == "l0ng_s3cr3t"


def test_parser_archive__missing_storage_type__raises_exception():
    parser = ConfigParser()
    parser.read_string(
        """
        [archive]
        password=set
        """
    )

    with pytest.raises(ValueError) as e:
        ArchiveConfig.from_config(parser["archive"])
    assert str(e.value) == "The archive section must declare a storage type"


def test_parser_archive__unknown_storage_type__raises_exception():
    parser = ConfigParser()
    parser.read_string(
        """
        [archive]
        storage=invalid
        password=set
        """
    )

    with pytest.raises(ValueError) as e:
        ArchiveConfig.from_config(parser["archive"])
    assert str(e.value) == "The archive storage 'invalid' is not recognised"


def test_parser_index(fs):
    fs.create_file(
        "/sample.conf", contents=SAMPLE_CONFIG.format(storage=SAMPLE_STORAGE_LOCAL)
    )
    fs.create_dir("/path/to")
    fs.create_dir("/path/to/backup")
    config = Config(filename="/sample.conf")

    assert isinstance(config.index, IndexConfig)
    assert config.index.path == Path("/path/to/index.sqlite")


def test_parser_index__path_missing__raises_exception():
    parser = ConfigParser()
    parser.read_string(
        """
        [index]
        missing=path
        """
    )

    with pytest.raises(ValueError) as e:
        IndexConfig.from_config(parser["index"])
    assert str(e.value) == "The index section must declare a path"


def test_parser_index__path_does_not_exit__raises_exception():
    parser = ConfigParser()
    parser.read_string(
        """
        [index]
        path=/does/not/exist
        """
    )

    with pytest.raises(ValueError) as e:
        IndexConfig.from_config(parser["index"])
    assert str(e.value) == "The path for the index does not exist"


def test_parser_config__sections_missing__raises_exception(fs):
    fs.create_file(
        "/sample.conf",
        contents=(
            """
            [invalid]
            config=file
            """
        ),
    )

    with pytest.raises(ValueError) as e:
        Config(filename="/sample.conf")
    assert str(e.value) == (
        "Invalid config file; must contain source, archive and "
        f"index sections; instead found invalid"
    )


def test_parser_config__archive_section_missing__raises_exception(fs):
    fs.create_file(
        "/sample.conf",
        contents="""
            [source]
            includes=value
            [index]
            path=somewhere
        """,
    )

    with pytest.raises(ValueError) as e:
        Config(filename="/sample.conf")
    assert str(e.value) == (
        "Invalid config file; must contain source, archive and "
        f"index sections; instead found source, index"
    )
