"""
Storage on AWS S3
"""
from configparser import ConfigParser
from typing import Any, Dict

from .base import Storage


class S3(Storage):
    key: str
    secret: str
    bucket: str
    path: str

    @classmethod
    def parse_config(cls, config: ConfigParser) -> Dict[str, Any]:
        kwargs = {
            key: config.get(key, '')
            for key in ['key', 'secret', 'bucket', 'path']
        }

        return kwargs

    def __init__(self, key: str, secret: str, bucket: str, path: str) -> None:
        self.key = key
        self.secret = secret
        self.bucket = bucket
        self.path = path

        # Check required string values
        for attr in ['key', 'secret', 'bucket']:
            if not getattr(self, attr):
                raise ValueError(f'Local storage requires a {attr}')
