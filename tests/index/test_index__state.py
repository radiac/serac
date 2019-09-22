"""
Test State class in serac/index/index.py
"""
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from serac.index.index import State
from serac.index.models import Action

from ..mocks import DatabaseTest, gen_file


class TestIndexState(DatabaseTest):
    def test_single_entry__get_latest(self):
        now = datetime.now()
        earlier = now - timedelta(days=7)

        file1 = gen_file(path="foo", action=Action.ADD, last_modified=earlier)
        file2 = gen_file(path="foo", action=Action.CONTENT, last_modified=now)
        state = State.at(timestamp=int(now.timestamp()))

        assert file1 != file2
        assert state == {Path("foo"): file2}
        assert state[Path("foo")].action == Action.CONTENT

    def test_multiple_entries__get_latest(self):
        now = datetime.now()
        earlier = now - timedelta(days=7)

        file1 = gen_file(path="one", action=Action.ADD, last_modified=earlier)
        file2 = gen_file(path="one", action=Action.CONTENT, last_modified=now)
        file3 = gen_file(path="two", action=Action.ADD, last_modified=earlier)
        file4 = gen_file(path="two", action=Action.CONTENT, last_modified=now)
        state = State.at(timestamp=int(now.timestamp()))

        assert file1 != file2
        assert file3 != file4
        assert state == {Path("one"): file2, Path("two"): file4}
        assert state[Path("one")].action == Action.CONTENT
        assert state[Path("two")].action == Action.CONTENT

    def test_multiple_entries__get_earlier(self):
        now = datetime.now()
        earlier = now - timedelta(days=7)

        file1 = gen_file(path="one", action=Action.ADD, last_modified=earlier)
        file2 = gen_file(path="one", action=Action.CONTENT, last_modified=now)
        file3 = gen_file(path="two", action=Action.ADD, last_modified=earlier)
        file4 = gen_file(path="two", action=Action.CONTENT, last_modified=now)
        state = State.at(timestamp=int(earlier.timestamp()))

        assert file1 != file2
        assert file3 != file4
        assert state == {Path("one"): file1, Path("two"): file3}
        assert state[Path("one")].action == Action.ADD
        assert state[Path("two")].action == Action.ADD

    def test_deleted_entry__not_included(self):
        now = datetime.now()
        earlier = now - timedelta(days=7)

        file1 = gen_file(path="one", action=Action.ADD, last_modified=earlier)
        file2 = gen_file(path="one", action=Action.CONTENT, last_modified=now)
        file3 = gen_file(path="two", action=Action.ADD, last_modified=earlier)
        file4 = gen_file(path="two", action=Action.DELETE, last_modified=now)
        state = State.at(timestamp=int(now.timestamp()))

        assert file1 != file2
        assert file3 != file4
        assert state == {Path("one"): file2}
        assert state[Path("one")].action == Action.CONTENT

    def test_state_at_datetime__raise_exception(self):
        now = datetime.now()

        with pytest.raises(ValueError) as e:
            State.at(timestamp=now)
        assert str(e.value) == "Can only get state using a timestamp"

    def test_state_by_path__returns_in_order(self):
        now = datetime.now()

        file1 = gen_file(path="b", action=Action.ADD, last_modified=now)
        file2 = gen_file(path="a", action=Action.CONTENT, last_modified=now)
        state = State.at(timestamp=int(now.timestamp()))

        assert state.by_path() == [file2, file1]
