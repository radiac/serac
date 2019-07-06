"""
Test serac/commands.py
"""
from click.testing import CliRunner

from serac.commands import cli

from .mocks import DatabaseTest, FilesystemTest, SAMPLE_CONFIG, SAMPLE_STORAGE_LOCAL


class CliTest(DatabaseTest, FilesystemTest):
    def run(self, *args):
        runner = CliRunner()
        return runner.invoke(cli, args, obj={})

    def gen_config(self, fs, filename, storage=SAMPLE_STORAGE_LOCAL):
        fs.create_file(filename, contents=SAMPLE_CONFIG.format(storage=storage))
        # Create required paths
        fs.create_dir("/path/to/indexes")
        fs.create_dir("/path/to/backup")


class TestCli(CliTest):
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
