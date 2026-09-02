#!/usr/bin/env python3
"""Process-level mkdir/open trace scoped to a destination root.

Independent of the writer's self-reported counters: wraps os.mkdir /
os.makedirs / os.open and io.open (pathlib.Path.write_bytes uses io.open,
not the os.open Python object).
"""
from __future__ import annotations

import io
import os
from pathlib import Path


def _mode_creates(mode: object) -> bool:
    text = str(mode)
    return any(ch in text for ch in "wax+")


class DestTrace:
    def __init__(self, dest: Path | str) -> None:
        self.dest_abs = os.path.abspath(os.fspath(dest))
        self.events: list[tuple[str, str]] = []
        self._real_os_open = os.open
        self._real_io_open = io.open
        self._real_mkdir = os.mkdir
        self._real_makedirs = os.makedirs
        self._installed = False

    def _under(self, path: object) -> bool:
        try:
            ap = os.path.abspath(os.fspath(path))
        except TypeError:
            return False
        return ap == self.dest_abs or ap.startswith(self.dest_abs + os.sep)

    def _note(self, kind: str, path: object) -> None:
        self.events.append((kind, os.path.abspath(os.fspath(path))))

    def install(self) -> None:
        if self._installed:
            return
        trace = self

        def wrapped_os_open(path, flags, *args, **kwargs):  # type: ignore[no-untyped-def]
            if trace._under(path) and flags & os.O_CREAT:
                trace._note("os.open", path)
            return trace._real_os_open(path, flags, *args, **kwargs)

        def wrapped_io_open(file, mode="r", *args, **kwargs):  # type: ignore[no-untyped-def]
            if trace._under(file) and _mode_creates(mode):
                trace._note("io.open", file)
            return trace._real_io_open(file, mode, *args, **kwargs)

        def wrapped_mkdir(path, *args, **kwargs):  # type: ignore[no-untyped-def]
            if trace._under(path):
                trace._note("mkdir", path)
            return trace._real_mkdir(path, *args, **kwargs)

        def wrapped_makedirs(path, *args, **kwargs):  # type: ignore[no-untyped-def]
            if trace._under(path):
                trace._note("makedirs", path)
            return trace._real_makedirs(path, *args, **kwargs)

        os.open = wrapped_os_open  # type: ignore[assignment]
        io.open = wrapped_io_open  # type: ignore[assignment]
        os.mkdir = wrapped_mkdir  # type: ignore[assignment]
        os.makedirs = wrapped_makedirs  # type: ignore[assignment]
        self._installed = True

    def restore(self) -> None:
        if not self._installed:
            return
        os.open = self._real_os_open  # type: ignore[assignment]
        io.open = self._real_io_open  # type: ignore[assignment]
        os.mkdir = self._real_mkdir  # type: ignore[assignment]
        os.makedirs = self._real_makedirs  # type: ignore[assignment]
        self._installed = False

    def __enter__(self) -> "DestTrace":
        self.install()
        return self

    def __exit__(self, *exc: object) -> None:
        self.restore()
