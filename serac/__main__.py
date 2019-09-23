"""
Invoke the command line when called directly
"""
from .commands import cli


if __name__ == "__main__":
    cli(obj={}, prog_name="serac")
