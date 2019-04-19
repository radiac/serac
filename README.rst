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

To run serac::

    /path/to/venv/bin/serac /path/to/serac.conf


To run tests::

    cd serac/repo
    . ../venv/bin/activate
    pytest --flake8 --mypy --cov=serac --cov-report=term --cov-report=html


Configuration
=============

Configure serac using a config file::

    [source]
    # Define the source for the backups

    # List of paths to include and exclude (glob patterns)
    include = /path/to/source
    include = /path/somewhere/else
    exclude = /path/to/source/unprocessed
    exclude = /path/somehwere/else/*.jpg

    # Optional root path - defaults to the lowest common path between includes
    root = /

    [destination]
    # Define where the backups are saved

    # Backup to a local path
    #storage = local
    #path = /path/to/backup

    # Backup to S3
    storage = s3
    s3_key = 4p1_k3y
    s3_secret = 53cr3t
    s3_bucket = arn:aws:s3:::my_bucket_name
    s3_path = path/within/bucket

    # Encrypt backups with this password
    password = l0ng_s3cr3t

    [index]
    # Define how indexed files are treated

    # Location where indexes are stored
    # This should then be backed up by another service, eg duplicity
    path = /path/to/indexes

    # Attributes to collect
    ownership = yes
    permissions = no
