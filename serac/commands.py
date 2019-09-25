"""
Commands
"""
import fcntl
import sys
from datetime import datetime
from pathlib import Path
from time import time
from typing import Dict, Optional, Type, Union

import click

from .config import Config
from .exceptions import SeracException
from .index import Changeset, Pattern, State, database, restore, scan, search
from .reporter import NullReporter, Reporter, StdoutReporter


class Timestamp(click.DateTime):  # type: ignore  # due to typeshed issue
    """
    Store a datetime or timestamp
    """

    def get_metavar(self, param):
        return "[timestamp|{}]".format("|".join(self.formats))

    def convert(self, value, param, ctx) -> int:
        if value.isdigit():
            return int(value)
        try:
            dt = super().convert(value, param, ctx)
        except click.BadParameter:
            self.fail(
                "invalid datetime format: {}. (choose from timestamp, {})".format(
                    value, ", ".join(self.formats)
                )
            )
        return int(dt.timestamp())

    def __repr__(self):  # pragma: no cover
        return "Timestamp"


@click.group()
@click.argument(
    "config",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True),
)
@click.pass_context
def cli(ctx, config: str):
    try:
        ctx.obj["config"] = Config(config)
    except Exception as e:
        raise click.ClickException(f"Invalid config: {e}")

    # Lock - only one process on a config at a time
    ctx.obj["lock"] = open(config, "r")
    try:
        fcntl.flock(ctx.obj["lock"], fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        raise click.ClickException(
            f"Config {config} is already in use by another process"
        )


@cli.command()
@click.pass_context
def test(ctx):
    """
    Test the config file is valid
    """
    # If it reaches this, the config file has been parsed
    sys.stdout.write("Config file syntax is correct\n")


@cli.command()
@click.pass_context
def init(ctx):
    """
    Create a new index database
    """
    config: Config = ctx.obj["config"]
    if config.index.path.exists():
        raise click.ClickException(f"Index database {config.index.path} already exists")
    database.create_db(config.index.path)
    database.disconnect()
    sys.stdout.write("Index database created\n")


@cli.command()
@click.option("--verbose", "-v", is_flag=True, default=False)
@click.pass_context
def archive(ctx, verbose: bool = False):
    """
    Scan and archive any changes
    """
    report_class: Type[Reporter] = NullReporter
    if verbose:
        report_class = StdoutReporter

    config: Config = ctx.obj["config"]
    database.connect(config.index.path)

    if verbose:
        sys.stdout.write("Scanning...\n")
    changeset: Changeset = scan(
        includes=config.source.includes, excludes=config.source.excludes
    )
    changeset.commit(archive_config=config.archive, report_class=report_class)
    database.disconnect()


@cli.command()
@click.option(
    "--at",
    "timestamp",
    help="Date and time (or timestamp) to go back to",
    type=Timestamp(),
)
@click.option(
    "--pattern", "pattern_str", help="Path to file", type=click.Path(exists=False)
)
@click.pass_context
def ls(ctx, pattern_str: Optional[str] = None, timestamp: Optional[int] = None):
    """
    Show the status of the archive
    """
    config: Config = ctx.obj["config"]

    if not timestamp:
        timestamp = int(time())

    database.connect(config.index.path)

    files: State = search(timestamp=timestamp, pattern=Pattern(pattern_str))

    if not files:
        if pattern_str:
            raise click.ClickException(f"No files found at {pattern_str}")
        else:
            raise click.ClickException("No files found")
        # If no files found, code will not proceed past this condition

    this_year = str(datetime.now().astimezone().year)
    for file in files.by_path():
        size_num, size_unit = file.archived.get_human_size()
        m_month, m_day, m_year, m_time = file.get_human_last_modified()
        sys.stdout.write(
            f"{file.permissions_display} "
            f"{file.owner_display:<8.8} "
            f"{file.group_display:<8.8} "
            f"{int(size_num):>4}{size_unit:<1} "
            f"{m_month:<3} {m_day.lstrip('0'):>2} "
            f"{m_time if m_year == this_year else m_year:>5} "
            f"{file.last_modified} "
            f"{file.path}"
            "\n"
        )

    database.disconnect()


@cli.command("restore")
@click.argument("destination", type=click.Path(exists=False))
@click.option(
    "--at",
    "timestamp",
    help="Date and time (or timestamp) to go back to",
    type=Timestamp(),
)
@click.option(
    "--pattern",
    "pattern_str",
    help="Path to file in archive",
    type=click.Path(exists=False),
)
@click.option(
    "--verbose", "-v", default=False, is_flag=True, help="Provide a progress report"
)
@click.pass_context
def cmd_restore(
    ctx,
    destination: str,
    timestamp: Optional[int] = None,
    pattern_str: Optional[str] = None,
    verbose: bool = False,
):
    """
    Restore from the archive
    """
    config: Config = ctx.obj["config"]
    database.connect(config.index.path)

    if not timestamp:
        timestamp = int(time())

    report_class: Type[Reporter] = NullReporter
    if verbose:
        report_class = StdoutReporter

    restored: Dict[str, Union[bool, SeracException]] = restore(
        archive_config=config.archive,
        timestamp=timestamp,
        destination_path=Path(destination),
        pattern=Pattern(pattern_str),
        missing_ok=True,
        report_class=report_class,
    )

    if restored:
        if verbose:
            sys.stdout.write(
                f"Restored {len(restored)} file{'' if len(restored) == 1 else 's'}\n"
            )
    else:
        raise click.ClickException(f"Path not found")

    database.disconnect()
