"""Shared test harness for tools/plugin probes.

IMP-0023: throwaway plugin payload fixtures for the install probes.
IMP-0066: ``start_shared_service`` - a live loopback TCP health service whose
survival the pressure-guard probes check.
"""
from __future__ import annotations

import hashlib
import json
import os
import select
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def _sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def v1_files() -> dict[str, str]:
    return {
        "skills/alpha/SKILL.md": "# alpha v1\nbody-one\n",
        "hooks/post.py": "print('v1')\n",
    }


def v2_files() -> dict[str, str]:
    return {
        "skills/alpha/SKILL.md": "# alpha v2\nbody-two\n",
        "hooks/post.py": "print('v2')\n",
        "skills/beta/SKILL.md": "# beta\n",
    }


def write_tree(root: Path, files: dict[str, str]) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for rel, body in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8", newline="\n")
    return root


def expected_census(files: dict[str, str]) -> dict[str, str]:
    return {rel: _sha(body.encode("utf-8")) for rel, body in files.items()}


def projection_for(payload: Path, plugin_id: str = "demo-plugin") -> dict[str, Any]:
    payload = Path(payload)
    entries = []
    for path in sorted(payload.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(payload).as_posix()
        entries.append(
            {
                "source": rel,
                "live": rel,
                "sha256": _sha(path.read_bytes()),
            }
        )
    return {"plugin_id": plugin_id, "entries": entries}


def write_projection(path: Path, projection: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(projection, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def kill_mid_activate(home: Path, payload: Path, proj_path: Path, pause: Path) -> int:
    """Start installer subprocess, pause before live swap, SIGKILL, return nonzero."""
    pause = Path(pause)
    pause.write_text("hold\n", encoding="utf-8")
    env = os.environ.copy()
    env["IMP0023_PAUSE_BEFORE_SWAP"] = str(pause)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    script = (
        "import os, time, sys\n"
        "from pathlib import Path\n"
        "p = Path(os.environ['IMP0023_PAUSE_BEFORE_SWAP'])\n"
        "while p.is_file():\n"
        "    time.sleep(0.02)\n"
        "sys.exit(0)\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        env=env,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    try:
        proc.send_signal(signal.SIGKILL)
    except Exception:
        proc.kill()
    rc = proc.wait(timeout=10)
    return rc if rc != 0 else 1


# --------------------------------------------------------------------------- IMP-0066

SHARED_SERVICE_SCRIPT = Path(__file__).resolve().parent / "shared_service.py"


class SharedService:
    """Handle on a live ``shared_service.py`` child: pid, port, health check, shutdown."""

    def __init__(self, proc: subprocess.Popen[bytes], port: int) -> None:
        self.proc = proc
        self.port = port
        self.host = "127.0.0.1"

    @property
    def pid(self) -> int:
        return self.proc.pid

    def _exchange(self, line: bytes, timeout: float) -> bytes:
        with socket.create_connection((self.host, self.port), timeout=timeout) as conn:
            conn.sendall(line + b"\n")
            data = b""
            while not data.endswith(b"\n") and len(data) < 256:
                chunk = conn.recv(64)
                if not chunk:
                    break
                data += chunk
        return data.strip()

    def healthy(self, timeout: float = 2.0) -> bool:
        """True when the service still accepts a connection and answers PING with PONG."""
        if self.proc.poll() is not None:
            return False
        try:
            return self._exchange(b"PING", timeout) == b"PONG"
        except OSError:
            return False

    def close(self, timeout: float = 5.0) -> int | None:
        """Ask the service to quit over its own protocol, then reap it (force only if it ignores QUIT)."""
        if self.proc.poll() is None:
            try:
                self._exchange(b"QUIT", timeout=2.0)
            except OSError:
                pass
            try:
                self.proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=timeout)
        if self.proc.stdout is not None:
            self.proc.stdout.close()
        return self.proc.returncode

    def __enter__(self) -> "SharedService":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def start_shared_service(timeout: float = 15.0) -> SharedService:
    """Spawn ``shared_service.py`` and wait (bounded) for its ``PORT <n>`` banner."""
    proc = subprocess.Popen(
        [sys.executable, "-B", str(SHARED_SERVICE_SCRIPT)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
        cwd=str(SHARED_SERVICE_SCRIPT.parent),
    )
    assert proc.stdout is not None
    fd = proc.stdout.fileno()
    deadline = time.monotonic() + timeout
    buf = b""
    while b"\n" not in buf:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or proc.poll() is not None:
            proc.kill()
            proc.wait(timeout=5)
            raise RuntimeError(
                f"shared_service.py did not announce a port within {timeout}s (exit={proc.returncode})"
            )
        readable, _, _ = select.select([fd], [], [], remaining)
        if not readable:
            continue
        chunk = os.read(fd, 256)
        if not chunk:
            proc.wait(timeout=5)
            raise RuntimeError(f"shared_service.py closed stdout before its banner (exit={proc.returncode})")
        buf += chunk
    banner = buf.split(b"\n", 1)[0].decode("utf-8", "replace").split()
    if len(banner) != 2 or banner[0] != "PORT" or not banner[1].isdigit():
        proc.kill()
        proc.wait(timeout=5)
        raise RuntimeError(f"unexpected shared_service.py banner {banner!r}")
    service = SharedService(proc, int(banner[1]))
    if not service.healthy(timeout=timeout):
        service.close()
        raise RuntimeError(f"shared service on port {service.port} failed its first health check")
    return service
