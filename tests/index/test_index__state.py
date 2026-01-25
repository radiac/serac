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

    def test_deleted_entry__visible_at_earlier_timestamp(self):
        """Test that a deleted file is still visible when querying at a timestamp before deletion."""
        now = datetime.now()
        earlier = now - timedelta(days=7)

        file1 = gen_file(path="deleted_file", action=Action.ADD, last_modified=earlier)
        file2 = gen_file(path="deleted_file", action=Action.DELETE, last_modified=now)

        # At the earlier timestamp, file should be visible
        state_earlier = State.at(timestamp=int(earlier.timestamp()))
        assert Path("deleted_file") in state_earlier
        assert state_earlier[Path("deleted_file")].action == Action.ADD

        # At the current timestamp, file should be gone
        state_now = State.at(timestamp=int(now.timestamp()))
        assert Path("deleted_file") not in state_now

    def test_file_with_multiple_changes__returns_correct_version(self):
        """Test that we get the correct version of a file that went through add->content->metadata->delete."""
        now = datetime.now()
        day1 = now - timedelta(days=4)
        day2 = now - timedelta(days=3)
        day3 = now - timedelta(days=2)
        day4 = now - timedelta(days=1)

        file1 = gen_file(path="changing", action=Action.ADD, last_modified=day1)
        file2 = gen_file(path="changing", action=Action.CONTENT, last_modified=day2)
        file3 = gen_file(path="changing", action=Action.METADATA, last_modified=day3)
        file4 = gen_file(path="changing", action=Action.DELETE, last_modified=day4)

        # Query at each point in time
        state1 = State.at(timestamp=int(day1.timestamp()))
        assert state1[Path("changing")].action == Action.ADD

        state2 = State.at(timestamp=int(day2.timestamp()))
        assert state2[Path("changing")].action == Action.CONTENT

        state3 = State.at(timestamp=int(day3.timestamp()))
        assert state3[Path("changing")].action == Action.METADATA

        state4 = State.at(timestamp=int(day4.timestamp()))
        assert Path("changing") not in state4

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
