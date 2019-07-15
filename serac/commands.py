"""
Commands
"""
import click
from pathlib import Path
from time import time
from typing import Dict, Optional

from .config import Config
from .index import Changeset, database, scan, get_state_at, File


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
    "--path", "filter_str", help="Path to file", type=click.Path(exists=False)
)
@click.pass_context
def show(ctx, filter_str: Optional[str] = None, timestamp: Optional[int] = None):
    """
    Show the status of the archive
    """
    config: Config = ctx.obj["config"]

    if not timestamp:
        timestamp = int(time())

    database.connect(config.index.path)
    state: Dict[Path, File] = get_state_at(timestamp)
    path: Path

    filter_path = None
    if filter_str:
        filter_path = Path(filter_str)

    found = 0
    for path in sorted(state):
        if filter_path and filter_path != path and filter_path not in path.parents:
            continue
        found += 1
    if not found:
        if filter_path:
            raise click.ClickException(f"No files found at {filter_str}")
        else:
            raise click.ClickException("No files found")

    database.disconnect()


@cli.command()
@click.argument("out", type=click.Path(exists=False))
@click.option(
    "--at",
    "timestamp",
    help="Date and time (or timestamp) to go back to",
    type=Timestamp(),
)
@click.option(
    "--archive",
    "archive_str",
    help="Path to file in archive",
    type=click.Path(exists=False),
)
@click.pass_context
def restore(
    ctx, out: str, timestamp: Optional[int] = None, archive_str: Optional[str] = None
):
    """
    Restore from the archive
    """
    config: Config = ctx.obj["config"]
    database.connect(config.index.path)

    if not timestamp:
        timestamp = int(time())

    archive_path: Optional[Path]
    if archive_str:
        archive_path = Path(archive_str)
    else:
        archive_path = None

    restored = restore(
        archive_config=config.archive,
        timestamp=timestamp,
        out_path=Path(out),
        archive_path=archive_path,
        missing_ok=True,
    )

    if restored:
        print(f"Restored {restored} file{'' if restored == 1 else 's'}")
    else:
        raise click.ClickException(f"Path not found")

    database.disconnect()


if __name__ == "__main__":
    cli(obj={})
