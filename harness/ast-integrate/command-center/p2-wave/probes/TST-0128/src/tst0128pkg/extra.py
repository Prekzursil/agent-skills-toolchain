"""Packaging-sensitive module.

Omitted from a planted install so the console script's collection set shrinks
while a source-tree ``python -m`` run still imports this file from the tree.
"""

MARKER = "tst0128-packaged-extra"


def secret() -> str:
    return MARKER
