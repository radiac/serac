"""
Commands
"""
import click
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from .config import Config
from .index import Changeset, database, scan, get_state_at, File


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
        raise ValueError(f"Index database {config.index.path} already exists")
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
    changeset.commit(destination=config.destination)
    database.disconnect()


@cli.command()
@click.option(
    "--at",
    help="Date and tme to go back to",
    type=click.DateTime(),  # type: ignore  # due to typeshed issue
)
@click.option("--path", "path_str", help="Path to file", type=click.Path(exists=False))
@click.pass_context
def show(ctx, path_str: Optional[str] = None, at: Optional[datetime] = None):
    """
    Show the status of the archive
    """
    config: Config = ctx.obj["config"]

    if not at:
        at = datetime.now()

    database.connect(config.index.path)
    state: Dict[Path, File] = get_state_at(at)
    path: Path

    if path_str:
        path = Path(path_str)
        if path in state:
            print(path)
        else:
            print("File not found")

    else:
        for path in sorted(state):
            print(path)
        if not state:
            print("No files found")

    database.disconnect()


@cli.command()
@click.argument("dest", type=click.Path(exists=False))
@click.option(
    "--at",
    help="Date and tme to go back to",
    type=click.DateTime(),  # type: ignore  # due to typeshed issue
)
@click.option(
    "--path", "path_str", help="Path to file to restore", type=click.Path(exists=False)
)
@click.pass_context
def restore(
    ctx, dest: str, at: Optional[datetime] = None, path_str: Optional[str] = None
):
    """
    Restore from the archive
    """
    config: Config = ctx.obj["config"]
    database.connect(config.index.path)
    dest_path = Path(dest)

    if not at:
        at = datetime.now()
    state: Dict[Path, File] = get_state_at(at)
    path: Path

    if path_str:
        path = Path(path_str)
        if path in state:
            file: File = state[path]
            file.restore(destination=config.destination, to=dest_path / file.path.name)
        else:
            print("File not found")
    else:
        for path, file in state.items():
            target_path = dest_path / file.path.relative_to("/")
            target_path.parent.mkdir(parents=True)
            file.restore(destination=config.destination, to=target_path)

    database.disconnect()


if __name__ == "__main__":
    cli(obj={})
