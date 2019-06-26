"""
Test serac/storage/base.py
"""
from serac.storage import storage_registry


def test_registry__storage_classes_registered():
    assert list(storage_registry.keys()) == ["local", "s3"]
