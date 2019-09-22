"""
Test serac/index/database.py
"""
from pathlib import Path

import pytest
from peewee import CharField, SqliteDatabase

from serac.index.database import (
    Model,
    connect,
    create_db,
    disconnect,
    get_current_db,
    set_current_db,
)

from ..mocks import MockDatabase, TmpFs


def test_create():
    # Database uses C libraries so doesn't work with pyfakefs
    test_db = SqliteDatabase(None)
    main_db = get_current_db()
    set_current_db(test_db)

    with TmpFs("index.sqlite") as filename:
        create_db(path=Path(filename))

    # Restore to main db
    set_current_db(main_db)


def test_connect():
    with MockDatabase() as test_db:  # noqa  # assign to var to have it in scope

        class FakeModel(Model):
            name = CharField()

    FakeModel.create(name="test")


def test_connect__does_not_exist__raises_exception(fs):
    # Stash main db and prep test db
    test_db = SqliteDatabase(None)
    main_db = get_current_db()
    set_current_db(test_db)

    with pytest.raises(ValueError) as e:
        connect(path=Path("/does/not/exist.sqlite"))
    assert str(e.value) == "Database does not exist"

    # Restore to main db
    set_current_db(main_db)


def test_disconnect__closes(mocker):
    # Stash main db and create test db
    main_db = get_current_db()

    class MockDb:
        close = mocker.stub()

    mock_db = MockDb()
    set_current_db(mock_db)

    disconnect()
    mock_db.close.assert_called_once()

    set_current_db(main_db)
