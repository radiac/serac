"""
Commands
"""
import click
from datetime import datetime
from pathlib import Path
from time import time
from typing import Optional

from .config import Config
from .index import Changeset, Pattern, State, database, scan, search, restore


class Timestamp(click.DateTime):  # type: ignore  # due to typeshed issue
    """
    Store a datetime or timestamp
    """

    def get_metavar(self, param):
        return "[timestamp|{}]".format("|".join(self.formats))

    def convert(self, value, param, ctx) -> int:
        if value.isdigit():
            return value
        try:
            dt = super().convert(value, param, ctx)
        except click.BadParameter:
            self.fail(
                "invalid datetime format: {}. (choose from timestamp, {})".format(
                    value, ", ".join(self.formats)
                )
            )
        return int(dt.timestamp())

    def __repr__(self):
        return "Timstamp"


@click.group()
@click.argument(
    "config",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True),
)
@click.pass_context
def cli(ctx, config):
    try:
        ctx.obj["config"] = Config(config)
    except Exception as e:
        raise click.ClickException(f"Invalid config: {e}")


@cli.command()
@click.pass_context
def test(ctx):
    """
    Test the config file is valid
    """
    # If it reaches this, the config file has been parsed
    print("Config file syntax is correct")


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
    print("Index database created")


@cli.command()
@click.pass_context
def archive(ctx):
    """
    Scan and archive any changes
    """
    config: Config = ctx.obj["config"]
    database.connect(config.index.path)
    changeset: Changeset = scan(
        includes=config.source.includes, excludes=config.source.excludes
    )
    changeset.commit(archive_config=config.archive)
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
        print(
            f"{file.permissions_display} "
            f"{file.owner_display:<8.8} "
            f"{file.group_display:<8.8} "
            f"{int(size_num):>4} "
            f"{size_unit:<2} "
            f"{m_month:<3} {m_day.lstrip('0'):>2} "
            f"{m_time if m_year == this_year else m_year:>5} "
            f"{file.last_modified} "
            f"{file.path}"
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
@click.pass_context
def cmd_restore(
    ctx,
    destination: str,
    timestamp: Optional[int] = None,
    pattern_str: Optional[str] = None,
):
    """
    Restore from the archive
    """
    config: Config = ctx.obj["config"]
    database.connect(config.index.path)

    if not timestamp:
        timestamp = int(time())

    restored = restore(
        archive_config=config.archive,
        timestamp=timestamp,
        destination_path=Path(destination),
        pattern=Pattern(pattern_str),
        missing_ok=True,
    )

    if restored:
        print(f"Restored {restored} file{'' if restored == 1 else 's'}")
    else:
        raise click.ClickException(f"Path not found")

    database.disconnect()


if __name__ == "__main__":
    cli(obj={})
