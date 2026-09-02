"""Tiny library imported by the critical suite.

A missing package-data / import-path regression is fatal to the installed
console-script arm and invisible to a working-tree ``python -m`` arm.
"""

PACKAGE_DATA_TOKEN = "tst0333-packaged"


def add(left: int, right: int) -> int:
    return left + right
