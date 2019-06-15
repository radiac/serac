"""
Storage on AWS S3
"""
from configparser import ConfigParser
from typing import Any, BinaryIO, Dict

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
                raise ValueError(f"Local storage requires a {attr}")

    def get_s3_path(self, filename: str):
        return f"s3://{self.key}:{self.secret}@{self.bucket}/{self.path}/{filename}"

    def get_size(self, filename: str) -> int:
        session = boto3.Session(
            aws_access_key_id=self.key, aws_secret_access_key=self.secret
        )
        s3 = session.resource("s3")
        obj = s3.Object(bucket_name=self.bucket, key=f"{self.path}/{filename}")
        return obj.content_length

    def read(self, filename: str) -> BinaryIO:
        return open(self.get_s3_path(filename), "rb")

    def write(self, filename: str) -> BinaryIO:
        return open(self.get_s3_path(filename), "wb")
