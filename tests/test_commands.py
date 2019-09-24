"""
Test serac/commands.py
"""
from datetime import datetime
from pathlib import Path
from time import time

from click.testing import CliRunner
from peewee import SqliteDatabase

from serac.commands import Timestamp, cli
from serac.config import ArchiveConfig
from serac.index.database import get_current_db, set_current_db
from serac.index.index import Pattern, State
from serac.index.models import Archived, File
from serac.reporter import NullReporter

from .mocks import (
    SAMPLE_CONFIG,
    SAMPLE_STORAGE_LOCAL,
    DatabaseTest,
    FilesystemTest,
    TmpFs,
)


# Timestamp to use in tests - 2001-01-30 00:00:00
JAN_30 = 980812800


class CliTestMixin:
    def run(self, *args):
        """
        Run command, config as first argument
        """
        runner = CliRunner()
        return runner.invoke(cli, args, obj={}, catch_exceptions=False)

    def cmd(self, fs, *args, index=None):
        """
        Create valid config and run specified command
        """
        self.gen_config(fs, "config.conf", index=index)
        return self.run("config.conf", *args)

    def gen_config(self, fs, filename, storage=SAMPLE_STORAGE_LOCAL, index=None):
        """
        Generate config file
        """
        # Create required paths
        if not Path("/path/to").exists():
            fs.create_dir("/path/to")
        if not Path("/path/to/backup").exists():
            fs.create_dir("/path/to/backup")
        contents = contents = SAMPLE_CONFIG.format(storage=storage)
        if index is not None:
            contents = contents.replace("/path/to/index.sqlite", index)

        fs.create_file(filename, contents=contents)


class TestCommandTest(CliTestMixin, DatabaseTest, FilesystemTest):
    def test_config_does_not_exist__raises_error(self):
        result = self.run("does_not_exist.conf", "test")
        assert result.exit_code == 2
        assert 'File "does_not_exist.conf" does not exist.' in result.output

    def test_config_does_exist_but_invalid__raises_error(self, fs):
        self.gen_config(fs, "invalid.conf", storage="INVALID")
        result = self.run("invalid.conf", "test")
        assert result.exit_code == 1
        assert "Invalid config: Source contains parsing errors" in result.output
        assert "[line 17]: 'INVALID\\n'" in result.output

    def test_config_does_exist_and_is_valid__passes(self, fs):
        self.gen_config(fs, "valid.conf")
        result = self.run("valid.conf", "test")
        assert result.exit_code == 0
        assert "Config file syntax is correct" in result.output


class TestCommandInit(CliTestMixin, FilesystemTest):
    def test_database_does_not_exist__database_created(self, fs):
        # Database uses C libraries so doesn't work with pyfakefs
        with TmpFs("index.sqlite") as filename:
            test_db = SqliteDatabase(None)
            main_db = get_current_db()
            set_current_db(test_db)

            result = self.cmd(fs, "init", index=filename)
            fs.add_real_file(filename)

            set_current_db(main_db)

            assert result.exit_code == 0
            assert Path(filename).is_file()
            assert "Index database created" in result.output

    def test_database_exists__exception_raised(self, fs):
        # Check is done in python
        filename = "/tmp/index.sqlite"
        path = Path(filename)
        path.touch()
        result = self.cmd(fs, "init", index=filename)
        assert result.exit_code == 1
        assert f"Index database {filename} already exists" in result.output


class TestCommandArchive(CliTestMixin, FilesystemTest):
    def test_archive(self, fs, mocker):
        mocked_changeset = mocker.MagicMock()
        mocked_scan = mocker.patch("serac.commands.scan", return_value=mocked_changeset)
        mocked_db_connect = mocker.patch("serac.index.database.connect")
        mocked_db_disconnect = mocker.patch("serac.index.database.disconnect")

        result = self.cmd(fs, "archive")
        mocked_scan.assert_called_once_with(
            includes=["/path/to/source", "/path/somewhere/else"],
            excludes=["/path/to/source/unprocessed", "/path/somewhere/else/*.jpg"],
        )
        mocked_changeset.commit.assert_called_once()
        mocked_db_connect.assert_called_once_with(Path("/path/to/index.sqlite"))
        mocked_db_disconnect.assert_called_once()

        assert result.exit_code == 0
        assert result.output == ""


class TestCommandLsBase(CliTestMixin, FilesystemTest, DatabaseTest):
    def fake_file(self, i):
        paths = [
            "/src/one.txt",
            "/src/two.txt",
            "/src/dir/three.txt",
            "/src/dir/four.txt",
            "/src/dir/subdir/five.txt",
            "/alt/six.txt",
            "/alt/seven.txt",
        ]
        file = File(
            path=Path(paths[i]),
            archived=Archived(size=102400),
            last_modified=JAN_30 - (i * 60 * 60 * 24),
            owner=100,
            group=100,
            permissions=int(str(644), 8),
        )
        return file

    def ls(
        self,
        fs,
        mocker,
        timestamp,
        pattern,
        files=None,
        at=None,
        expect_error=False,
        expect_failure=False,
    ):
        """
        expect_error: we're expecting an error in the command
        expect_failure: we're expecting an error before the command
        """
        # Patch out everything
        if files is None:
            files = [self.fake_file(i) for i in range(7)]
        mocked_state = State(files=files)
        mocked_search = mocker.patch("serac.commands.search", return_value=mocked_state)
        mocked_db_connect = mocker.patch("serac.index.database.connect")
        mocked_db_disconnect = mocker.patch("serac.index.database.disconnect")
        mocker.patch("serac.index.models.uid_to_name", return_value="user")
        mocker.patch("serac.index.models.gid_to_name", return_value="group")

        args = []
        if timestamp:
            if at is None:
                at = str(timestamp)
            args.extend(["--at", at])
        else:
            timestamp = int(time())
        if pattern:
            args.extend(["--pattern", pattern])
        result = self.cmd(fs, "ls", *args)

        # Check the cmd ran correctly
        if not expect_failure:
            mocked_search.assert_called_once_with(
                timestamp=timestamp, pattern=Pattern(pattern)
            )
            mocked_db_connect.assert_called_once_with(Path("/path/to/index.sqlite"))

            if not expect_error:
                # Won't disconnect if we exit with an error
                mocked_db_disconnect.assert_called_once()

        return result

    def assert_success(self, result):
        """
        Check the response was correct
        """
        # Because we've mocked out the search fn, we'll always get the same results
        assert result.exit_code == 0
        assert result.output.splitlines() == [
            "-rw-r--r-- user     group     100K {} {} {}".format(*opts)
            for opts in [
                ("Jan 24  2001", 980294400, "/alt/seven.txt"),
                ("Jan 25  2001", 980380800, "/alt/six.txt"),
                ("Jan 27  2001", 980553600, "/src/dir/four.txt"),
                ("Jan 26  2001", 980467200, "/src/dir/subdir/five.txt"),
                ("Jan 28  2001", 980640000, "/src/dir/three.txt"),
                ("Jan 30  2001", 980812800, "/src/one.txt"),
                ("Jan 29  2001", 980726400, "/src/two.txt"),
            ]
        ]


class TestCommandLs(TestCommandLsBase):
    """
    Test the LS command
    """

    def test_ls__no_args__search_with_no_args(self, fs, mocker, freezer):
        # Freeze time 1 year later so we get the year in the output, not hours
        freezer.move_to(datetime.utcfromtimestamp(JAN_30 + (60 * 60 * 24 * 365)))
        result = self.ls(fs, mocker, timestamp="", pattern="")
        self.assert_success(result)

    def test_ls__same_year__shown_with_hours(self, fs, mocker, freezer):
        # Freeze time 1 day later so we get the hours in the output, not years
        freezer.move_to(datetime.utcfromtimestamp(JAN_30 + (60 * 60 * 24)))
        result = self.ls(fs, mocker, timestamp="", pattern="")
        assert result.exit_code == 0
        assert result.output.splitlines() == [
            "-rw-r--r-- user     group     100K {} {} {}".format(*opts)
            for opts in [
                ("Jan 24 00:00", 980294400, "/alt/seven.txt"),
                ("Jan 25 00:00", 980380800, "/alt/six.txt"),
                ("Jan 27 00:00", 980553600, "/src/dir/four.txt"),
                ("Jan 26 00:00", 980467200, "/src/dir/subdir/five.txt"),
                ("Jan 28 00:00", 980640000, "/src/dir/three.txt"),
                ("Jan 30 00:00", 980812800, "/src/one.txt"),
                ("Jan 29 00:00", 980726400, "/src/two.txt"),
            ]
        ]

    def test_ls__timestamp_and_pattern__search_with_all_args(self, fs, mocker):
        result = self.ls(fs, mocker, timestamp=JAN_30, pattern="/src/dir")
        self.assert_success(result)

    def test_ls__no_results_no_pattern__raises_error(self, fs, mocker):
        result = self.ls(
            fs, mocker, timestamp="", pattern="", files=[], expect_error=True
        )
        assert result.exit_code == 1
        assert "No files found" in result.output

    def test_ls__no_results_with_pattern__raises_pattern_error(self, fs, mocker):
        result = self.ls(
            fs, mocker, timestamp="", pattern="/src", files=[], expect_error=True
        )
        assert result.exit_code == 1
        assert "No files found at /src" in result.output


class TestTimestamp(TestCommandLsBase):
    """
    Test the timestamp class (using ls where necessary)
    """

    def test_timestamp_is_string__parsed_ok(self, fs, mocker):
        result = self.ls(
            fs, mocker, at="2001-01-30", timestamp=JAN_30, pattern="/src/dir"
        )
        self.assert_success(result)

    def test_invalid_timestamp__raises_error(self, fs, mocker):
        result = self.ls(
            fs, mocker, timestamp="wrong", pattern="", files=[], expect_failure=True
        )
        assert result.exit_code == 2
        assert (
            "invalid datetime format: wrong. (choose from timestamp," in result.output
        )

    def test_metavar__renders_ok(self):
        assert (
            Timestamp().get_metavar("x")
            == "[timestamp|%Y-%m-%d|%Y-%m-%dT%H:%M:%S|%Y-%m-%d %H:%M:%S]"
        )


class TestCommandRestore(CliTestMixin, FilesystemTest, DatabaseTest):
    def fake_restored(self, n):
        return {f"/path/{i}": True for i in range(n)}

    def test_restore__no_args__restore_with_time(self, fs, mocker, freezer):
        # Patch out everything
        freezer.move_to(datetime(2001, 1, 30))
        mocked_restore = mocker.patch(
            "serac.commands.restore", return_value=self.fake_restored(1)
        )
        mocked_db_connect = mocker.patch("serac.index.database.connect")
        mocked_db_disconnect = mocker.patch("serac.index.database.disconnect")

        result = self.cmd(fs, "restore", "/dest")

        assert result.exit_code == 0
        assert result.output == ""

        archive_config = mocker.MagicMock(spec=ArchiveConfig)
        archive_config.__eq__.return_value = True
        mocked_restore.assert_called_once_with(
            archive_config=archive_config,
            timestamp=JAN_30,
            destination_path=Path("/dest"),
            pattern=Pattern(""),
            missing_ok=True,
            report_class=NullReporter,
        )
        mocked_db_connect.assert_called_once_with(Path("/path/to/index.sqlite"))
        mocked_db_disconnect.assert_called_once()

    def test_restore__multiple_files__message_empty(self, fs, mocker):
        # Patch out everything
        mocker.patch("serac.commands.restore", return_value=self.fake_restored(2))
        mocker.patch("serac.index.database.connect")
        mocker.patch("serac.index.database.disconnect")

        result = self.cmd(fs, "restore", "/dest")

        assert result.exit_code == 0
        assert result.output == ""

    def test_restore__multiple_files_verbose__message_ok(self, capsys, fs, mocker):
        # Patch out everything
        mocker.patch("serac.commands.restore", return_value=self.fake_restored(2))
        mocker.patch("serac.index.database.connect")
        mocker.patch("serac.index.database.disconnect")

        result = self.cmd(fs, "restore", "/dest", "--verbose")

        assert result.exit_code == 0
        assert "Restored 2 files" in result.output

    def test_restore__no_files__raises_exception(self, fs, mocker, freezer):
        # Patch out everything
        mocker.patch("serac.commands.restore", return_value={})
        mocker.patch("serac.index.database.connect")
        mocker.patch("serac.index.database.disconnect")

        result = self.cmd(fs, "restore", "/dest")

        assert result.exit_code == 1
        assert "Path not found" in result.output
