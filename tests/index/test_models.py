"""
Test serac/index/models.py
"""
import grp
import pwd
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from pyfakefs import fake_filesystem

from serac import crypto
from serac.config import ArchiveConfig
from serac.index.models import (
    Action,
    Archived,
    File,
    _gid_cache,
    _uid_cache,
    gid_to_name,
    uid_to_name,
)
from serac.storage import Local

from ..mocks import DatabaseTest, FilesystemTest, FlawedStorage, gen_file


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
        files = list(File.select())

        assert len(files) == 2
        assert file1 != file2
        assert file1 in files
        assert file2 in files


class TestFile(DatabaseTest, FilesystemTest):
    """
    Test the File model
    """

    def test_to_string(self):
        file = File(path=Path("/tmp/foo"))
        assert str(file) == "/tmp/foo"

    def test_metadata__file_missing__raises_exception(self, fs):
        file = File(path=Path("/tmp/foo"))
        with pytest.raises(ValueError) as e:
            file.refresh_metadata_from_disk()
        assert str(e.value) == "File /tmp/foo has disappeared"

    def test_metadata__file_not_a_file__raises_exception(self, fs):
        fs.create_dir("/tmp/foo")
        file = File(path=Path("/tmp/foo"))
        with pytest.raises(ValueError) as e:
            file.refresh_metadata_from_disk()
        assert str(e.value) == "File /tmp/foo is not a file"

    def test_metadata__collected(self, freezer, fs):
        frozen_time = datetime(2001, 1, 1, 1, 1, 1)
        freezer.move_to(frozen_time)

        uid = 100
        gid = 200
        fake_filesystem.set_uid(uid)
        fake_filesystem.set_gid(gid)
        fs.create_file("/tmp/foo", contents="unencrypted")
        file = File(path=Path("/tmp/foo"))

        file.refresh_metadata_from_disk()
        assert file.size == len("unencrypted")
        assert file.last_modified == frozen_time.timestamp()
        assert file.owner == uid
        assert file.group == gid

    def test_metadata__collected__last_modified_change_detected(self, fs, freezer):
        # Create file
        frozen_time = datetime(2001, 1, 1, 1, 1, 1)
        freezer.move_to(frozen_time)
        fake_file = fs.create_file("/tmp/foo", contents="unencrypted")
        file = File(path=Path("/tmp/foo"))
        file.refresh_metadata_from_disk()

        # Modify file
        frozen_time_modified = datetime(2001, 1, 1, 1, 1, 2)
        freezer.move_to(frozen_time_modified)
        with file.path.open("w") as handle:
            handle.write("modified")
        fake_file.st_mtime = datetime.timestamp(frozen_time_modified)
        file_modified = file.clone()
        file_modified.refresh_metadata_from_disk()

        # Last modified dates are different, objects are not the same
        assert file.last_modified == frozen_time.timestamp()
        assert file_modified.last_modified == frozen_time_modified.timestamp()
        assert file != file_modified

    def test_size__before_metadata__raises_exception(self, fs):
        file = File(path=Path("/tmp/foo"))
        with pytest.raises(ValueError) as e:
            file.size
        assert str(e.value) == "Cannot access size without metadata"

    def test_archive(self, fs):
        fs.create_file("/src/foo", contents="unencrypted")
        fs.create_dir("/dest")
        file = File(path=Path("/src/foo"), action=Action.ADD)
        archive_config = ArchiveConfig(
            storage=Local(path=Path("/dest/")), password="secret"
        )
        file.refresh_metadata_from_disk()
        file.archive(archive_config)

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

    def test_archive_file__storage_broken__error_raised(self, fs):
        # Create a file with enough data to overwhelm the kernel buffer
        fs.create_file("/src/foo", contents="unencrypted" * 1024 * 1024)
        file = File(path=Path("/src/foo"), action=Action.ADD)
        archive_config = ArchiveConfig(storage=FlawedStorage(), password="secret")
        file.refresh_metadata_from_disk()

        with pytest.raises(ValueError) as e:
            file.archive(archive_config)
        assert str(e.value).startswith("Unable to archive /src/foo: ")

        # Check File object does not exist in db
        assert file.id is None
        files = File.select()
        assert len(files) == 0

        # Check the archived object does exist
        archives = Archived.select()
        assert len(archives) == 1
        assert archives[0].hash == ""

    def test_archive_twice__action_forbidden_error_raised(self, fs):
        # This is such an edge case, but test for it to be safe
        fs.create_file("/src/foo", contents="unencrypted")
        fs.create_dir("/dest")
        file = File(path=Path("/src/foo"), action=Action.ADD)
        archive_config = ArchiveConfig(
            storage=Local(path=Path("/dest/")), password="secret"
        )
        file.refresh_metadata_from_disk()
        file.archive(archive_config)

        # Now archive it again
        with pytest.raises(ValueError) as e:
            file.archive(archive_config)
        assert str(e.value) == "Cannot archive a file twice"

    def test_restore(self, fs):
        archive_config = ArchiveConfig(
            storage=Local(path=Path("/dest/")), password="secret"
        )

        # Create an archived file
        fs.create_file("/src/foo", contents="unencrypted")
        fs.create_dir("/dest")
        file = File(path=Path("/src/foo"), action=Action.ADD)
        file.refresh_metadata_from_disk()
        file.archive(archive_config)

        # Now check we can restore it
        fs.create_dir("/restore")
        file.restore(archive_config, to=Path("/restore/file"))
        decrypted = Path("/restore/file")
        with decrypted.open("r") as handle:
            assert handle.read() == "unencrypted"


class TestUserGroup:
    """
    Test uid_to_name, gid_to_name, File.user_display and File.group_display

    We're not disabling the caches, so each test needs to use a separate ID
    """

    def teardown_method(self):
        _uid_cache.clear()
        _gid_cache.clear()

    def test_uid_known__returns_name(self, monkeypatch, mocker):
        def return_name(uid):
            assert uid == 100
            obj = mocker.MagicMock(name="pw_name")
            obj.pw_name = "foo"
            return obj

        monkeypatch.setattr(pwd, "getpwuid", return_name)

        assert uid_to_name(100) == "foo"

    def test_uid_unknown__returns_uid(self, monkeypatch):
        def return_name(uid):
            raise KeyError("Unknown")

        monkeypatch.setattr(pwd, "getpwuid", return_name)

        assert uid_to_name(100) == "100"

    def test_file_user_display(self, monkeypatch):
        # Monkeypatch something to raise an AttributeError and return the ID as a str
        monkeypatch.setattr(pwd, "getpwuid", lambda x: None)
        file = File()
        file.owner = 100
        assert file.owner_display == "100"

    def test_gid_known__returns_name(self, monkeypatch, mocker):
        def return_name(gid):
            assert gid == 100
            obj = mocker.MagicMock(name="gr_name")
            obj.gr_name = "foo"
            return obj

        monkeypatch.setattr(grp, "getgrgid", return_name)

        assert gid_to_name(100) == "foo"

    def test_gid_unknown__returns_gid(self, monkeypatch):
        def return_name(gid):
            raise KeyError("Unknown")

        monkeypatch.setattr(grp, "getgrgid", return_name)

        assert gid_to_name(100) == "100"

    def test_file_group_display(self, monkeypatch):
        monkeypatch.setattr(grp, "getgrgid", lambda x: None)
        file = File()
        file.group = 100
        assert file.group_display == "100"


class TestFilePermissions:
    """
    Test of File.permissions_display
    """

    def assert_permission(self, mask, human):
        file = File()
        file.permissions = int(str(mask), 8)
        assert file.permissions_display == human

    def test_no_bits(self):
        self.assert_permission(0, "-" * 10)

    def test_read_all(self):
        self.assert_permission(444, "-r--r--r--")

    def test_read_write_owner__read_others(self):
        self.assert_permission(644, "-rw-r--r--")

    def test_read_write_execute_owner__read_execute_group__read_public(self):
        self.assert_permission(754, "-rwxr-xr--")

    def test_execute_owner__write_group__write_execute_public(self):
        self.assert_permission(123, "---x-w--wx")


class TestFileHumanLastModified:
    """
    Test of File.get_human_last_modified
    """

    def test_not_set(self):
        file = File()
        assert file.get_human_last_modified() == ["", "", "", ""]

    def test_timestamp_converted(self):
        now = datetime(2001, 1, 2, 3, 4, 5)
        file = File()
        file.last_modified = now.timestamp()
        assert file.get_human_last_modified() == ["Jan", "02", "2001", "03:04"]


class TestArchivedHumanSize:
    """
    Test of Archived.get_human_size
    """

    def assert_size(self, bytes, size, unit):
        archived = Archived()
        archived.size = bytes
        actual = archived.get_human_size()
        assert actual == (size, unit)

    def test_bytes(self):
        self.assert_size(1000, 1000, "")

    def test_kibibytes(self):
        self.assert_size(1000 * 1024, 1000, "K")

    def test_mebibyte(self):
        self.assert_size(1000 * 1024 * 1024, 1000, "M")

    def test_gibibyte(self):
        self.assert_size(1000 * 1024 * 1024 * 1024, 1000, "G")

    def test_tebibyte(self):
        self.assert_size(1000 * 1024 * 1024 * 1024 * 1024, 1000, "T")

    def test_pebibyte(self):
        self.assert_size(1000 * 1024 * 1024 * 1024 * 1024 * 1024, 1000 * 1024, "T")
