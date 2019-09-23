"""
Report classes for realtime feedback on long-running tasks
"""
import sys
from typing import IO


class Reporter:
    """
    Base reporter class
    """

    file: str
    status: str

    def __init__(self, file: str, status: str):
        self.file = file
        self.status = status

    def update(self, status: str):
        self.status = status

    def complete(self, status: str):
        self.update(status)


class NullReporter(Reporter):
    def __init__(self, file: str, status: str):
        pass

    def update(self, status: str):
        pass

    def complete(self, status: str):
        pass


class StreamReporter(Reporter):
    """
    Report to a stream
    """

    stream: IO[str]

    def __init__(self, file: str, status: str):
        super().__init__(file, status)
        self.stream.write(f"{file}... {status}")

    def update(self, status: str):
        super().update(status)
        self.stream.write(f"\r{self.file}... {status} ")

    def complete(self, status: str):
        self.update(status)
        self.stream.write("\n")


class StdoutReporter(StreamReporter):
    stream: IO[str] = sys.stdout
