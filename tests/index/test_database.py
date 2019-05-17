"""
Test serac/index/database.py
"""
from peewee import CharField

from serac.index.database import Model

from ..mocks import MockDatabase


def test_connect():
    with MockDatabase() as test_db:  # noqa

        class FakeModel(Model):
            name = CharField()

    FakeModel.create(name="test")
