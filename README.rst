=====
Serac
=====

Incremental permanent data archiver with encryption.

Designed for permanently backing up data which does not change frequently,
suitable for write-only storage such as Amazon Glacier.


Installation
============

This requires Python 3.7.

During development, install in a virtual environment::

    mkdir serac
    cd serac
    git clone <path-to-repo> repo
    virtualenv --python=python3.7 venv
    . venv/bin/activate
    pip install pip-tools
    cd repo
    pip-sync


Usage
=====

Serac must always be run with the config file path as the first argument, then
the command to perform as the second argument.

To run serac::

    /path/to/venv/bin/serac CONFIG COMMAND [OPTIONS]

To run during development::

    python -m serac.commands CONFIG COMMAND [OPTIONS]

To run tests::

    cd serac/repo
    . ../venv/bin/activate
    pytest


Commands
--------

After that it accepts one of the following commands:

`test`
    Test the configuration file

`init`
    Initialise an index for a new config by creating the database

`archive`
    Archive any changes since the last archive was performed

`ls [--at=DATE] [--pattern=PATTERN]`
    Show the state of the archive.

    This follows the roughly the same layout as `ls -l`, with the following columns:

        * File permissions
        * Owner (as it will be restored to on this system)
        * Group (as it will be restored to on this system)
        * Size (in kibi/mebib/gibibytes, or in bytes if not specified)
        * Last modified date (this year if not specified)
        * Last modified timestamp (temporary - for use in calls to `ls` and `restore`)
        * Path (as it was on the originating system)

`restore DESTINATION [--at=DATE] [--pattern=PATTERN]`
    Restore some or all of an archive

Arguments
~~~~~~~~~

`DATE`
    This must be a unix timestamp. Date strings are not yet supported.

`PATTERN`
    This can either be an exact path to a file, or a partial path to a directory.
    Globs are not yet supported.


Configuration
=============

Configure serac using a config file::

    [source]
    # Define the source for the backups

    # List of paths to include and exclude (glob patterns)
    include =
        /path/to/source
        /path/somewhere/else
    exclude =
        /path/to/source/unprocessed
        /path/somewhere/else/*.jpg

    [archive]
    # Define where the backups are saved

    # Backup to a local path
    #storage = local
    #path = /path/to/backup

    # Backup to S3
    storage = s3
    key = 4p1_k3y
    secret = 53cr3t
    bucket = arn:aws:s3:::my_bucket_name
    path = path/within/bucket

    # Encrypt backups with this password
    password = l0ng_s3cr3t

    [index]
    # Define how indexed files are treated

    # Location for index database
    # This should then be backed up by another service, eg duplicity
    path = /path/to/index.sqlite
