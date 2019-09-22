"""
Serac exceptions
"""


class SeracException(Exception):
    msg = "Serac exception"
    short = "error"

    def __init__(self, msg=None, short=None):
        if msg is not None:
            self.msg = msg
        if short is not None:
            self.short = short

    def __str__(self):
        return self.msg


class ArchiveUnavailable(SeracException):
    """
    Used when retrieving objects from storage when the archived object is unavailable,
    ie is frozen in S3 Glacier
    """

    msg = "Archived object is not currently available"
    short = "object unavailable"


class FileExists(SeracException):
    """
    Used when trying to write to a path
    """

    msg = "File already exists"
    short = "file exists"
