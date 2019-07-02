"""
Storage on AWS S3
"""
from configparser import ConfigParser
from typing import Any, Dict, IO

import boto3
from smart_open import open

from .base import Storage


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

    def get_s3_path(self, archive_id: str):
        return f"s3://{self.key}:{self.secret}@{self.bucket}/{self.path}/{archive_id}"

    def get_size(self, archive_id: str) -> int:
        session = boto3.Session(
            aws_access_key_id=self.key, aws_secret_access_key=self.secret
        )
        s3 = session.resource("s3")
        obj = s3.Object(bucket_name=self.bucket, key=f"{self.path}/{archive_id}")
        return obj.content_length

    def read(self, archive_id: str) -> IO[bytes]:
        return open(self.get_s3_path(archive_id), "rb")

    def write(self, archive_id: str) -> IO[bytes]:
        return open(self.get_s3_path(archive_id), "wb")
