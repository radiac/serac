import os

from doc8 import doc8


def test_doc8():
    result = doc8(paths=[os.getcwd()], extension=[".rst"])

    assert result.total_errors == 0, result.report()
