"""
Test search() in serac/index/index.py
"""
from pathlib import Path
from time import time

from serac.index.index import Pattern, search

from .test_index import IndexTestBase


class TestIndexSearch(IndexTestBase):
    def test_search_file__from_head__finds_single_file(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        results = search(timestamp=int(time()), pattern=Pattern("/src/dir/three.txt"))

        assert len(results) == 1
        assert Path("/src/dir/three.txt") in results
        assert results[Path("/src/dir/three.txt")].last_modified == int(
            update_time.timestamp()
        )

    def test_search_file__from_past__finds_single_file(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        results = search(
            timestamp=int(initial_time.timestamp()),
            pattern=Pattern("/src/dir/three.txt"),
        )

        assert len(results) == 1
        assert Path("/src/dir/three.txt") in results
        assert results[Path("/src/dir/three.txt")].last_modified == int(
            initial_time.timestamp()
        )

    def test_search_dir__from_head__finds_some_files(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        results = search(timestamp=int(time()), pattern=Pattern("/src/dir"))

        assert len(results) == 3
        assert Path("/src/dir/three.txt") in results
        assert (
            results[Path("/src/dir/three.txt")].last_modified == update_time.timestamp()
        )
        assert Path("/src/dir/four.txt") in results
        assert Path("/src/dir/subdir/five.txt") in results

    def test_search_dir__from_past__finds_some_files(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        results = search(
            timestamp=int(initial_time.timestamp()), pattern=Pattern("/src/dir")
        )

        assert len(results) == 3
        assert Path("/src/dir/three.txt") in results
        assert (
            results[Path("/src/dir/three.txt")].last_modified
            == initial_time.timestamp()
        )
        assert Path("/src/dir/four.txt") in results
        assert Path("/src/dir/subdir/five.txt") in results

    def test_search_all__from_head__finds_all_files(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        results = search(timestamp=int(time()))

        assert len(results) == 5
        assert Path("/src/one.txt") in results
        assert Path("/src/two.txt") in results
        assert Path("/src/dir/three.txt") in results
        assert (
            results[Path("/src/dir/three.txt")].last_modified == update_time.timestamp()
        )
        assert Path("/src/dir/four.txt") in results
        assert Path("/src/dir/subdir/five.txt") in results

    def test_search_all__from_past__finds_all_files(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        results = search(timestamp=int(initial_time.timestamp()))

        assert len(results) == 5
        assert Path("/src/one.txt") in results
        assert Path("/src/two.txt") in results
        assert Path("/src/dir/three.txt") in results
        assert (
            results[Path("/src/dir/three.txt")].last_modified
            == initial_time.timestamp()
        )
        assert Path("/src/dir/four.txt") in results
        assert Path("/src/dir/subdir/five.txt") in results

    def test_search_missing__returns_zero(self, fs, freezer):
        initial_time, update_time = self.mock_two_states(fs, freezer)
        results = search(timestamp=int(time()), pattern=Pattern("/does/not.exist"))
        assert len(results) == 0
