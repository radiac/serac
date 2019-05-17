"""
Database object
"""
from __future__ import annotations

from collections import defaultdict
from enum import IntEnum
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Type

from peewee import (
    Database,
    SqliteDatabase,
    IntegerField,
    Model as BaseModel,
)


_db = SqliteDatabase(None)
models: DefaultDict[Database, List[Model]] = defaultdict(list)


def set_current_db(database: Database):
    global _db
    _db = database


def get_current_db():
    return _db


def connect(filename: str, create: bool = False, database: Database = None):
    if database is None:
        database = get_current_db()

    if not create and not Path(filename).is_file():
        raise ValueError('Database does not exist')

    database.init(filename)
    database.connect()
    if create:
        database.create_tables(models[database])


def create_db(filename: str, database: Database = None) -> None:
    connect(filename, create=True, database=database)


def disconnect(database: Database = None) -> None:
    if database is None:
        database = get_current_db()

    database.close()


class ModelMeta(type(BaseModel)):  # type: ignore # see mypy #4284
    """
    Metaclass wrapper for standard peewee model metaclass to automatically
    register a new model with the model registry
    """
    def __new__(cls, name, bases, attrs):
        # Ensure we've got a Meta class definition
        if 'Meta' not in attrs:
            attrs['Meta'] = type('Meta', (), {})

        # Set the database to the current db
        if getattr(attrs['Meta'], 'database', None) is None:
            setattr(attrs['Meta'], 'database', get_current_db())

        # Initialise metaclass as normal
        cls = super().__new__(cls, name, bases, attrs)

        # Log model so we can automatically create it
        models[cls._meta.database].append(cls)

        return cls


class Model(BaseModel, metaclass=ModelMeta):
    pass


class EnumField(IntegerField):
    """
    Field for integer enums
    """
    enum: Type[IntEnum]

    def __init__(
        self,
        enum: Type[IntEnum],
        *args: List[Any],
        **kwargs: Dict[str, Any],
    ) -> None:
        super().__init__(*args, **kwargs)
        self.enum = enum

    def db_value(self, value: IntEnum) -> int:
        return value.value

    def python_value(self, value: int) -> IntEnum:
        return self.enum(value)
