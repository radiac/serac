"""
Mock objects
"""
from datetime import datetime
from typing import Type

from peewee import Database, SqliteDatabase
from pyfakefs.fake_filesystem_unittest import Patcher

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
        database.create_db(filename=':memory:')
        super().setup_method()

    def teardown_method(self):
        database.get_current_db().close()
        super().teardown_method()


class FilesystemTest(BaseTest):
    """
    Base for test classes which use the file system
    """
    patcher = Patcher()

    def setup_method(self):
        self.patcher.setUp()
        super().setup_method()

    def teardown_method(self):
        self.patcher.tearDown()
        super().teardown_method()


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

    def __init__(
        self,
        db_cls: Database = SqliteDatabase,
        filename: str = ':memory:',
    ):
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


def gen_stored(**kwargs):
    attrs = dict(
        hash='abc',
    )
    attrs.update(kwargs)
    return models.Stored.create(**attrs)


def gen_file(**kwargs):
    stored = kwargs.get('stored')
    if not isinstance(stored, models.Stored):
        stored_attrs = {}
        if stored is not None:
            stored_attrs['hash'] = stored
        stored = gen_stored(**stored_attrs)

    attrs = dict(
        path='/tmp/foo',
        stored=stored,
        action=models.Action.ADD,
        last_modified=datetime.now(),
        size=12345,
        owner=1000,
        group=1000,
        permissions=644,
    )
    attrs.update(kwargs)
    return models.File.create(**attrs)
