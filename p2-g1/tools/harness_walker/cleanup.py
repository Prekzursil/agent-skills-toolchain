"""NUL-safe fixture cleanup for the hostile-tree probes (TST-0335).

Windows resolves a final NUL component to the console device on every
unprefixed open, so a plain ``shutil.rmtree`` dies with WinError 87 on a
fixture that plants a real ``reserved/NUL`` entry. Removal must go through
the extended-length form, which disables device resolution.
"""
from __future__ import annotations

import os
import shutil
from types import TracebackType
from typing import Any

from harness_walker.paths import extended_length_form


def unlink_hostile(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        os.unlink(extended_length_form(path))


def rmtree_hostile(root: str | os.PathLike[str]) -> None:
    root_s = str(root)

    def onerror(func, path, exc_info):
        try:
            unlink_hostile(path)
        except OSError:
            raise exc_info[1]

    try:
        shutil.rmtree(root_s, onerror=onerror)
    except PermissionError:
        shutil.rmtree(root_s, ignore_errors=True)


class hostile_tempdir:
    """tempfile.TemporaryDirectory twin whose cleanup is NUL-safe."""

    def __init__(self, prefix: str = "tst0335-") -> None:
        self._prefix = prefix
        self.name: str = ""

    def __enter__(self) -> str:
        import tempfile

        self.name = tempfile.mkdtemp(prefix=self._prefix)
        return self.name

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        rmtree_hostile(self.name)
        return False


def build_and_walk(root: str) -> Any:
    from harness_walker.fixtures import build_hostile_tree
    from harness_walker.walker import walk_tree

    meta = build_hostile_tree(root)
    return meta, walk_tree(root)
