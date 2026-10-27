"""Lazy-shared vs eager stdio MCP activation pool (IMP-0065)."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterator
from contextlib import contextmanager

HERE = Path(__file__).resolve().parent
STUB = HERE / "stub_mcp_server.py"


class Mode(str, Enum):
    LAZY_SHARED = "lazy-shared"
    EAGER_STDIO = "eager-stdio"
    SHARED_HTTP = "shared-http"


class SharedServerDeadError(RuntimeError):
    pass


def _ensure_stub() -> Path:
    if STUB.is_file() and STUB.stat().st_size > 20:
        return STUB
    STUB.write_text(
        "#!/usr/bin/env python3\n"
        "import sys, time\n"
        "sys.stdout.write('ready\\n'); sys.stdout.flush()\n"
        "while True:\n"
        "    line = sys.stdin.readline()\n"
        "    if not line:\n"
        "        break\n"
        "    sys.stdout.write('{\"ok\": true}\\n'); sys.stdout.flush()\n"
        "    if 'exit' in line:\n"
        "        break\n"
        "    time.sleep(0.05)\n",
        encoding="utf-8",
    )
    return STUB


def process_table_count(mark: str) -> int:
    found = 0
    proc = Path("/proc")
    if not proc.is_dir():
        return found
    needle = mark.encode("utf-8")
    stub = b"stub_mcp_server.py"
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except (OSError, PermissionError):
            continue
        if stub in raw and needle in raw:
            found += 1
    return found


class _Session:
    def __init__(self, pool: "ActivationPool", session_id: str) -> None:
        self.pool = pool
        self.session_id = session_id
        self._proc: subprocess.Popen[str] | None = None

    def call(self, server: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        del server
        self.pool._ensure_process(self)
        return {"ok": True, "session": self.session_id, "echo": payload or {}}


class ActivationPool:
    def __init__(self, mode: Mode, mark: str) -> None:
        self.mode = Mode(mode)
        self.mark = mark
        self._shared: subprocess.Popen[str] | None = None
        self._children: list[subprocess.Popen[str]] = []

    def _spawn(self) -> subprocess.Popen[str]:
        stub = _ensure_stub()
        env = os.environ.copy()
        env["MCP_ACTIVATION_MARK"] = self.mark
        proc = subprocess.Popen(
            [sys.executable, "-B", str(stub), "--mark", self.mark, "stub_mcp_server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env=env,
        )
        self._children.append(proc)
        time.sleep(0.05)
        return proc

    def _ensure_process(self, session: _Session) -> None:
        if self.mode in {Mode.LAZY_SHARED, Mode.SHARED_HTTP}:
            if self._shared is not None and self._shared.poll() is not None:
                raise SharedServerDeadError("shared MCP child is dead")
            if self._shared is None:
                self._shared = self._spawn()
            session._proc = self._shared
            return
        if session._proc is None or session._proc.poll() is not None:
            session._proc = self._spawn()

    def open_session(self, session_id: str) -> _Session:
        sess = _Session(self, session_id)
        if self.mode is Mode.EAGER_STDIO:
            sess._proc = self._spawn()
        return sess

    def close(self) -> None:
        for proc in self._children:
            if proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
        self._children.clear()
        self._shared = None


@contextmanager
def make_pool(mode: Mode, mark: str) -> Iterator[ActivationPool]:
    pool = ActivationPool(mode, mark)
    try:
        yield pool
    finally:
        pool.close()
