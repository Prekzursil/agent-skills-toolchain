"""Source adapters behind one uniform ``poll()`` protocol (grill S5).

Four adapters cover the source universe:

* ``local-file-tail``  — read the WHOLE logfile (never a fixed tail, grill S6b),
  optionally keeping only regex-matching lines.
* ``file-exists-glob`` — count files matching a glob, newest mtime as liveness.
* ``http-json``        — fetch a JSON body from a URL.
* ``process-pid``      — is a pid alive?

Every adapter returns a :class:`~core.models.PollResult`; a failed poll sets
``error`` (BLIND state, grill S7) rather than fabricating a "done" verdict.

All real I/O sits behind injectable dependencies (``FileSystem``, ``http_get``,
``pid_alive``, ``clock``) so the adapter logic reaches 100% branch coverage with
no real network/process, and the thin real defaults are covered with tmp files.
"""

from __future__ import annotations

import glob as _glob
import json
import os
import re
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

from .models import PollResult, TaskSpec

Clock = Callable[[], float]
HttpGetter = Callable[[str], str]
PidProbe = Callable[[int], bool]


class AdapterError(ValueError):
    """Raised when a spec cannot be turned into a working adapter."""


class FileSystem(Protocol):
    """Minimal filesystem surface the file adapters depend on."""

    def stat(self, path: str) -> tuple[bool, float | None, int | None]:
        """Return ``(exists, mtime, size)``; ``(False, None, None)`` if absent."""
        ...

    def read_text(self, path: str) -> str: ...

    def glob(self, pattern: str) -> list[str]: ...


class RealFileSystem:
    """Default :class:`FileSystem` backed by :mod:`pathlib`/:mod:`glob`."""

    def stat(self, path: str) -> tuple[bool, float | None, int | None]:
        p = Path(path)
        if not p.exists():
            return (False, None, None)
        st = p.stat()
        return (True, st.st_mtime, st.st_size)

    def read_text(self, path: str) -> str:
        return Path(path).read_text(encoding="utf-8")

    def glob(self, pattern: str) -> list[str]:
        return sorted(_glob.glob(pattern))


def default_http_get(url: str, *, timeout: float = 5.0) -> str:
    """Fetch ``url`` and return its decoded body (blocking, stdlib urllib)."""
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # type: ignore[arg-type]
        data = cast("bytes", resp.read())
    return data.decode("utf-8")


def default_pid_alive(pid: int) -> bool:
    """True if ``pid`` refers to a live process (signal-0 probe)."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


class Adapter(Protocol):
    """The single method every source adapter exposes."""

    def poll(self) -> PollResult: ...


class LocalFileTailAdapter:
    """Read a logfile whole; optionally keep only regex-matching lines."""

    def __init__(
        self,
        path: str,
        pattern: str | None = None,
        *,
        fs: FileSystem | None = None,
    ) -> None:
        self.path = path
        self.pattern = re.compile(pattern) if pattern else None
        self.fs: FileSystem = fs or RealFileSystem()

    def poll(self) -> PollResult:
        exists, mtime, size = self.fs.stat(self.path)
        if not exists:
            return PollResult(exists=False, mtime=None, liveness=False)
        try:
            text = self.fs.read_text(self.path)
        except OSError as exc:
            return PollResult(
                exists=True, mtime=mtime, size=size, liveness=False, error=str(exc)
            )
        all_lines = text.splitlines()  # WHOLE record — grill S6b, no fixed tail
        if self.pattern is not None:
            lines = [ln for ln in all_lines if self.pattern.search(ln)]
        else:
            lines = all_lines
        return PollResult(
            exists=True, mtime=mtime, lines=lines, size=size, liveness=True
        )


class FileExistsGlobAdapter:
    """Count files matching a glob; newest mtime is the liveness signal."""

    def __init__(self, pattern: str, *, fs: FileSystem | None = None) -> None:
        self.pattern = pattern
        self.fs: FileSystem = fs or RealFileSystem()

    def poll(self) -> PollResult:
        matches = self.fs.glob(self.pattern)
        mtime: float | None = None
        for match in matches:
            m_exists, m_mtime, _ = self.fs.stat(match)
            if m_exists and m_mtime is not None and (mtime is None or m_mtime > mtime):
                mtime = m_mtime
        count = len(matches)
        exists = count > 0
        return PollResult(
            exists=exists,
            mtime=mtime,
            lines=list(matches),
            count=count,
            liveness=exists,
        )


class HttpJsonAdapter:
    """Fetch and parse a JSON object from a URL."""

    def __init__(
        self,
        url: str,
        *,
        http_get: HttpGetter | None = None,
        clock: Clock = time.time,
    ) -> None:
        self.url = url
        self.http_get: HttpGetter = http_get or default_http_get
        self.clock = clock

    def poll(self) -> PollResult:
        try:
            body = self.http_get(self.url)
        except Exception as exc:  # noqa: BLE001 - any transport error → BLIND
            return PollResult(exists=False, mtime=None, liveness=False, error=str(exc))
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            return PollResult(
                exists=True, mtime=None, liveness=False, error=f"invalid json: {exc}"
            )
        if not isinstance(data, dict):
            return PollResult(
                exists=True,
                mtime=None,
                liveness=False,
                error="json root is not an object",
            )
        return PollResult(
            exists=True,
            mtime=self.clock(),
            lines=[body],
            liveness=True,
            raw=cast("dict[str, object]", data),
        )


class ProcessPidAdapter:
    """Report whether a pid is alive (process-up liveness plane)."""

    def __init__(
        self,
        pid: int,
        *,
        pid_alive: PidProbe | None = None,
        clock: Clock = time.time,
    ) -> None:
        self.pid = pid
        self.pid_alive: PidProbe = pid_alive or default_pid_alive
        self.clock = clock

    def poll(self) -> PollResult:
        alive = self.pid_alive(self.pid)
        return PollResult(
            exists=alive, mtime=self.clock() if alive else None, liveness=alive
        )


def _require_str(cfg: dict[str, object], key: str, task_id: str) -> str:
    value = cfg.get(key)
    if not isinstance(value, str) or not value:
        raise AdapterError(f"task '{task_id}': config.{key} must be a non-empty string")
    return value


def _require_int(cfg: dict[str, object], key: str, task_id: str) -> int:
    value = cfg.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise AdapterError(f"task '{task_id}': config.{key} must be an integer")
    return value


def adapter_from_spec(
    spec: TaskSpec,
    *,
    fs: FileSystem | None = None,
    http_get: HttpGetter | None = None,
    pid_alive: PidProbe | None = None,
    clock: Clock = time.time,
) -> Adapter:
    """Build the concrete adapter a :class:`TaskSpec` selects.

    Raises :class:`AdapterError` for an unknown adapter name or missing config.
    """
    cfg = spec.config
    if spec.adapter == "local-file-tail":
        path = _require_str(cfg, "path", spec.id)
        pattern_raw = cfg.get("pattern")
        pattern = pattern_raw if isinstance(pattern_raw, str) and pattern_raw else None
        return LocalFileTailAdapter(path, pattern, fs=fs)
    if spec.adapter == "file-exists-glob":
        pattern = _require_str(cfg, "pattern", spec.id)
        return FileExistsGlobAdapter(pattern, fs=fs)
    if spec.adapter == "http-json":
        url = _require_str(cfg, "url", spec.id)
        return HttpJsonAdapter(url, http_get=http_get, clock=clock)
    if spec.adapter == "process-pid":
        pid = _require_int(cfg, "pid", spec.id)
        return ProcessPidAdapter(pid, pid_alive=pid_alive, clock=clock)
    raise AdapterError(f"task '{spec.id}': unknown adapter '{spec.adapter}'")
