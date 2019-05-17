"""
Core dispatcher
"""
from .index import database


def create_db(config):
    """
    Create a new database
    """
    if config.index.path.exists():
        raise ValueError(f"Database {config.index.path} already exists")
    database.create_db(config.index.path)


def dry(config):
    """
    Dry run
    """
    database.connect(config.index.path)
    # dry run
    # ++ TODO


def archive(config):
    pass
    # live run
    # ++ TODO
