"""
Storage on AWS S3
"""
from configparser import ConfigParser
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import IO, Any, Dict

import boto3
from smart_open import open

from ..exceptions import ArchiveUnavailable, FileExists
from .base import Storage


# Number of days to restore a file from Glacier for
RESTORE_DAYS = 1


class StorageClass(Enum):
    STANDARD = "STANDARD"
    GLACIER = "GLACIER"
    DEEP_ARCHIVE = "DEEP_ARCHIVE"


class ObjectFrozen(ArchiveUnavailable):
    msg = "Object is frozen"
    short = "frozen"


class ObjectRetrieving(ArchiveUnavailable):
    msg = "Object is not yet available"
    short = "retrieve in progress"


class S3(Storage):
    key: str
    secret: str
    bucket: str
    path: str

    @classmethod
    def parse_config(cls, config: ConfigParser) -> Dict[str, Any]:
        kwargs = {
            key: config.get(key, "") for key in ["key", "secret", "bucket", "path"]
        }

        return kwargs

    def __init__(self, key: str, secret: str, bucket: str, path: str) -> None:
        self.key = key
        self.secret = secret
        self.bucket = bucket
        self.path = path

        # Check required string values
        for attr in ["key", "secret", "bucket"]:
            if not getattr(self, attr):
                raise ValueError(f"S3 storage requires a {attr}")

    @property
    def s3_resource(self) -> boto3.resources.base.ServiceResource:
        session = boto3.Session(
            aws_access_key_id=self.key, aws_secret_access_key=self.secret
        )
        s3 = session.resource("s3")
        return s3

    def get_s3_path(self, archive_id: str):
        return f"s3://{self.key}:{self.secret}@{self.bucket}/{self.path}/{archive_id}"

    def get_s3_object(self, archive_id: str) -> boto3.resources.base.ServiceResource:
        obj = self.s3_resource.Object(
            bucket_name=self.bucket, key=f"{self.path}/{archive_id}"
        )
        return obj

    @lru_cache()
    def check_is_available(self, archive_id: str) -> bool:
        obj = self.get_s3_object(archive_id)

        # If it's in standard S3, nothing preventing us
        if obj.storage_class not in [StorageClass.GLACIER, StorageClass.DEEP_ARCHIVE]:
            return True

        # It's in glacier - check its restore state
        if obj.restore is None:
            # Restoration not started
            raise ObjectFrozen()

        elif 'ongoing-request="true"' in obj.restore:
            # Restoration in progress
            raise ObjectRetrieving()

        elif 'ongoing-request="false"' in obj.restore:
            # Restoration complete
            return True

        raise ValueError(f"Unknown restore state: {obj.restore}")

    def retrieve(self, local_path: Path, archive_id: str, password: str) -> None:
        """
        Check if the file is available on S3 to restore to the destination, and if not
        start the S3 restore so it will be available soon
        """
        # This check will be done again in super().retrieve, but we don't want to
        # request thawing the glacier object unnecessarily.
        if local_path.exists():
            raise FileExists(local_path)

        try:
            self.check_is_available()
        except ObjectFrozen:
            # Object is frozen, start the thaw
            self.start_s3_restore(archive_id)
            raise
        # Unhandled exceptions will include ``ObjectRetrieving``

        # File is available, start the restore
        super().retrieve(
            local_path=local_path, archive_id=archive_id, password=password
        )

    def get_size(self, archive_id: str) -> int:
        obj = self.get_s3_object(archive_id)
        return obj.content_length

    def start_s3_restore(self, archive_id: str) -> None:
        restore_request = {
            "OutputLocation": {
                "S3": {
                    "BucketName": "destination-bucket",
                    "Prefix": "destination-prefix",
                }
            },
            "Days": RESTORE_DAYS,
        }
        self.s3_resource.restore_object(
            Bucket="bucket-name",
            Key=f"{self.path}/{archive_id}",
            RestoreRequest=restore_request,
        )

    def read(self, archive_id: str) -> IO[bytes]:
        return open(self.get_s3_path(archive_id), "rb")

    def write(self, archive_id: str) -> IO[bytes]:
        return open(self.get_s3_path(archive_id), "wb")
