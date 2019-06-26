"""
Test serac/index/models.py
"""
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

from pyfakefs import fake_filesystem

from serac import crypto
from serac.config import DestinationConfig
from serac.storage import Local
from serac.index.models import Action, Archived, File

from ..mocks import DatabaseTest, FilesystemTest, gen_file


class TestDatabaseTest(DatabaseTest):
    """
    Test the DatabaseTest base class operates as expected
    """

    def test_create_first__object_is_only_item(self):
        file = gen_file(path="/tmp/foo")
        files = File.select()
        assert len(files) == 1
        assert files[0].path == file.path

    def test_create_second__object_is_only_item(self):
        """
        Ensure db is wiped between tests
        """
        file = gen_file(path="/tmp/bar")
        files = File.select()
        assert len(files) == 1
        assert files[0].path == file.path

    def test_create_multiple__all_returned(self):
        now = datetime.now()
        earlier = now - timedelta(days=7)

        file1 = gen_file(path="/tmp/foo", last_modified=earlier)
        file2 = gen_file(path="/tmp/foo", last_modified=now)
        files = File.select()
        assert len(files) == 2
        assert list(files) == [file1, file2]


class TestFile(DatabaseTest, FilesystemTest):
    """
    Test the File model
    """

    def test_metadata_collected(self, freezer, fs):
        frozen_time = datetime(2001, 1, 1, 1, 1, 1)
        freezer.move_to(frozen_time)

        uid = 100
        gid = 200
        fake_filesystem.set_uid(uid)
        fake_filesystem.set_gid(gid)
        fs.create_file("/tmp/foo", contents="unencrypted")
        file = File(path="/tmp/foo")

        file.refresh_metadata_from_disk()
        assert file.size == len("unencrypted")
        assert file.last_modified == datetime.timestamp(frozen_time)
        assert file.owner == uid
        assert file.group == gid

    def test_metadata_collected__last_modified_change_detected(self, fs, freezer):
        # Create file
        frozen_time = datetime(2001, 1, 1, 1, 1, 1)
        freezer.move_to(frozen_time)
        fake_file = fs.create_file("/tmp/foo", contents="unencrypted")
        file = File(path="/tmp/foo")
        file.refresh_metadata_from_disk()

        # Modify file
        frozen_time_modified = datetime(2001, 1, 1, 1, 1, 2)
        freezer.move_to(frozen_time)
        with file.get_path().open("w") as handle:
            handle.write("modified")
        fake_file.st_mtime = datetime.timestamp(frozen_time_modified)
        file_modified = file.clone()
        file_modified.refresh_metadata_from_disk()

        # Last modified dates are different, objects are not the same
        assert file.last_modified == datetime.timestamp(frozen_time)
        assert file_modified.last_modified == datetime.timestamp(frozen_time_modified)
        assert file != file_modified

    def test_archive(self, fs):
        fs.create_file("/src/foo", contents="unencrypted")
        fs.create_dir("/dest")
        file = File(path="/src/foo", action=Action.ADD)
        destination_config = DestinationConfig(
            storage=Local(path="/dest/"), password="secret"
        )
        file.refresh_metadata_from_disk()
        file.archive(destination_config)

        # Check Archived db object exists
        assert file.archived.id > 0
        archives = Archived.select()
        assert len(archives) == 1
        assert archives[0].id == file.archived.id

        # Check file exists in/dest/
        dest_path = Path(f"/dest/{file.archived.id}")
        assert dest_path.is_file()

        # Check it has been encrypted and we can decrypt it
        decrypted = BytesIO()
        with dest_path.open("rb") as handle:
            crypto.decrypt(handle, decrypted, "secret", dest_path.stat().st_size)
        assert str(decrypted.getvalue(), "utf-8") == "unencrypted"
