"""
Test serac/storage/s3.py

These tests are disabled by default. Set environment variables to test:
    SERAC_TEST_S3=1 S3_KEY="key" S3_SECRET="secret" \
        S3_BUCKET="bucket_name" S3_PATH="test" pytest
"""
from io import BytesIO
import os
from pathlib import Path

import boto3
import pytest

from serac import crypto
from serac.storage import S3

from ..mocks import FilesystemTest


@pytest.mark.skipif(
    not os.getenv("SERAC_TEST_S3", ""), reason="Not running S3 integration tests"
)
class TestS3(FilesystemTest):
    @property
    def S3(self):
        return S3(
            key=os.environ["S3_KEY"],
            secret=os.environ["S3_SECRET"],
            bucket=os.environ["S3_BUCKET"],
            path=os.environ["S3_PATH"],
        )

    @property
    def boto3(self):
        return boto3.Session(
            aws_access_key_id=os.environ["S3_KEY"],
            aws_secret_access_key=os.environ["S3_SECRET"],
        )

    def get_s3_object(self, filename):
        s3 = self.boto3.resource("s3")
        return s3.Object(
            bucket_name=os.environ["S3_BUCKET"],
            key=f"{os.environ['S3_PATH']}/{filename}",
        )

    def teardown_method(self):
        obj = self.get_s3_object("1")
        obj.delete()
        super().teardown_method()

    def test_store(self, fs):
        # This will be tested in a separate test, but we'll focus on the store aspect
        fs.create_file("/src/foo", contents="unencrypted")
        storage = self.S3

        # Encrypt and push to storage
        storage.store(local_path="/src/foo", id=1, password="secret")

        # Check file exists in S3
        assert storage.get_size("1") > 0
        obj = self.get_s3_object("1")
        data = obj.get()["Body"].read()

        # Check it has been encrypted and we can decrypt it
        encrypted = BytesIO()
        encrypted.write(data)
        decrypted = BytesIO()
        crypto.decrypt(encrypted, decrypted, "secret", len(data))
        assert str(decrypted.getvalue(), "utf-8") == "unencrypted"

    def test_retrieve(self, fs):
        # Encrypt and deliver. This is tested in a separate test
        fs.create_file("/src/foo", contents="unencrypted")
        fs.create_dir("/store")
        fs.create_dir("/dest")
        storage = self.S3
        storage.store(local_path="/src/foo", id=1, password="secret")

        # Pull and decrypt from storage
        storage.retrieve(local_path="/dest/bar", id=1, password="secret")

        # Check file exists in /dest/
        dest_path = Path(f"/dest/bar")
        assert dest_path.is_file()

        # Check it has been decrypted
        with dest_path.open("r") as handle:
            content = handle.read()
        assert content == "unencrypted"
