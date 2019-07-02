"""
Test serac/commands.py
"""
from click.testing import CliRunner

from serac.commands import cli

from .mocks import DatabaseTest, FilesystemTest


class CliTest(DatabaseTest, FilesystemTest):
    def run(self, *args):
        runner = CliRunner()
        return runner.invoke(cli, args)


class TestCli(CliTest):
    def test_test(self, *args):
        result = self.run("does_not_exist.conf", "test")
        assert result.exit_code == 2
        assert 'File "does_not_exist.conf" does not exist.' in result.output
