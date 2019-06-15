"""
Mock objects
"""
from datetime import datetime
from pathlib import Path
import shutil
from typing import Type

from peewee import Database, SqliteDatabase

from serac import storage
from serac.config import DestinationConfig
from serac.index import database
from serac.index import models


class BaseTest:
    """
    Abstract base for base test classes

    Simplifies using multiple base test classes on a single test class
    """

    def setup_method(self):
        pass

    def teardown_method(self):
        pass


class DatabaseTest(BaseTest):
    """
    Base for test classes which use the database
    """

    def setup_method(self):
        database.create_db(filename=":memory:")
        super().setup_method()

    def teardown_method(self):
        database.get_current_db().close()
        super().teardown_method()


class FilesystemTest(BaseTest):
    """
    Base for test classes which use the file system
    """

    def mock_fs(self, fs):
        """
        Create mock filesystem ready for testing against
        """
        fs.create_file("/src/one.txt", contents="one")
        fs.create_file("/src/two.txt", contents="two")
        fs.create_file("/src/dir/three.txt", contents="three")
        fs.create_file("/src/dir/four.txt", contents="four")
        fs.create_file("/src/dir/subdir/five.txt", contents="five")
        fs.create_file("/alt/six.txt", contents="six")
        fs.create_file("/alt/seven.txt", contents="seven")

    def get_destination(self):
        return DestinationConfig(
            storage=storage.Local(path="/dest/"), password="secret"
        )


class LiveFilesystemTest(BaseTest):
    """
    Base for test classes which use the real file system
    """

    TEST_ROOT = Path.cwd()
    TEST_PATH = TEST_ROOT / "serac-fs-test"

    def setup_method(self):
        super().setup_method()

        assert self.TEST_ROOT.is_dir()
        assert not self.TEST_PATH.is_dir()
        self.TEST_PATH.mkdir(exist_ok=False)

    def mock_fs(self):
        self.create_file("src/one.txt", contents="one")
        self.create_file("src/two.txt", contents="two")
        self.create_file("src/dir/three.txt", contents="three")
        self.create_file("src/dir/four.txt", contents="four")
        self.create_file("src/dir/subdir/five.txt", contents="five")
        self.create_file("alt/six.txt", contents="six")
        self.create_file("alt/seven.txt", contents="seven")

    def create_file(self, filename: str, contents: str) -> None:
        path = self.TEST_PATH / filename
        path.parent.mkdir(exist_ok=True)
        with path.open(mode="w") as file:
            file.write(contents)

    def get_path(self, filename: str) -> Path:
        return self.TEST_PATH / filename

    def teardown_method(self):
        super().teardown_method()
        shutil.rmtree(self.TEST_PATH)


class MockDatabase:
    """
    Context manager to create an in-memory sqlite database and create any
    Models defined within the context. The database will be closed at the
    when execution leaves the context variable's scope, at the end of the test

    Example:

        def test_create():
            with MockDatabase() as tdb:
                class FakeModel(Model):
                    name = CharField()
            FakeModel.create(name='test')
    """

    db_cls: Type[Database]
    filename: str
    test_db: Database
    main_db: Database

    def __init__(self, db_cls: Database = SqliteDatabase, filename: str = ":memory:"):
        self.db_cls = db_cls
        self.filename = filename

    def __enter__(self) -> Database:
        """
        Start context by:
        * switching current db to test db
        * returning self so destructor called at end of test scope, not context
        """
        self.test_db = self.db_cls(None)
        self.main_db = database.get_current_db()
        database.set_current_db(self.test_db)
        return self

    def __exit__(self, *args):
        """
        End context by:
        * creating test db
        * switching back to main db
        """
        database.create_db(filename=self.filename, database=self.test_db)
        database.set_current_db(self.main_db)

    def __del__(self):
        """
        Once this context leaves scope, clean up all records
        """
        # Close db - this is not done automatically
        self.test_db.close()

        # Remove from models registry
        del database.models[self.test_db]


def gen_archived(**kwargs):
    attrs = dict(hash="abc", size=123)
    attrs.update(kwargs)
    return models.Archived.create(**attrs)


def gen_file(**kwargs):
    archived = kwargs.get("archived")
    if not isinstance(archived, models.Archived):
        archived_attrs = {}
        if archived is not None:
            archived_attrs["hash"] = archived
        archived = gen_archived(**archived_attrs)

    attrs = dict(
        path="/tmp/foo",
        archived=archived,
        action=models.Action.ADD,
        last_modified=datetime.now(),
        owner=1000,
        group=1000,
        permissions=644,
    )
    attrs.update(kwargs)
    return models.File.create(**attrs)


def mock_file_archive(self: models.File, hash: str = "hash") -> None:
    self.archived = models.Archived.create(hash=self.calculate_hash(), size=self.size)
    self.save()
