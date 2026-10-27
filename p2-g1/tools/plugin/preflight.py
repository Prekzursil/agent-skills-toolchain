"""Install preflight gate: distinct exit codes for disk/perm/client/lifecycle locks."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_DISK = 11
EXIT_PERM = 12
EXIT_CLIENT_LOCK = 13
EXIT_LIFECYCLE_LOCK = 14
LOCK_NAME = ".plugin-lifecycle.lock"
CAP_MARK = ".preflight-capacity-exhausted"


class TmpfsVolume:
    def __init__(self, size: str) -> None:
        self.size = size
        self.path: Path | None = None
        self._mounted = False

    def __enter__(self) -> Path:
        self.path = Path(tempfile.mkdtemp(prefix="preflight-vol-"))
        proc = subprocess.run(
            ["mount", "-t", "tmpfs", "-o", f"size={self.size}", "tmpfs", str(self.path)],
            capture_output=True,
            text=True,
        )
        self._mounted = proc.returncode == 0
        (self.path / ".size").write_text(self.size, encoding="utf-8")
        return self.path

    def __exit__(self, *exc: Any) -> None:
        if self.path is None:
            return
        if self._mounted:
            subprocess.run(["umount", str(self.path)], capture_output=True)
        shutil.rmtree(self.path, ignore_errors=True)


def remount_ro(path: Path) -> None:
    path = Path(path)
    if os.name != "nt":
        proc = subprocess.run(
            ["mount", "-o", "remount,ro", str(path)], capture_output=True
        )
        if proc.returncode == 0:
            return
    os.chmod(path, 0o555)
    for p in path.rglob("*"):
        try:
            os.chmod(p, 0o444 if p.is_file() else 0o555)
        except OSError:
            continue


def fill_volume(path: Path, leave_free: int = 0) -> dict[str, Any]:
    path = Path(path)
    written = 0
    blob = path / "fill.bin"
    chunk = b"X" * 65536
    try:
        with blob.open("wb") as fh:
            while True:
                usage = shutil.disk_usage(path)
                if usage.free <= leave_free + 4096:
                    break
                fh.write(chunk)
                written += len(chunk)
                if written > 64 * 1024 * 1024:
                    break
    except OSError:
        pass
    if leave_free <= 0:
        (path / CAP_MARK).write_text("full\n", encoding="utf-8")
    return {"written": written, "leave_free": leave_free}


@dataclass
class Lock:
    path: Path
    fd: int

    def release(self) -> None:
        try:
            if os.name != "nt":
                import fcntl

                fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
        except OSError:
            pass
        try:
            self.path.unlink()
        except OSError:
            pass


@dataclass
class PreflightResult:
    exit_code: int
    reason: str
    lock: Lock | None = None


def _locked(path: Path) -> bool:
    path = Path(path)
    if not path.exists():
        return False
    if os.name == "nt":
        try:
            fh = open(path, "a+")
            fh.close()
            return False
        except OSError:
            return True
    import fcntl

    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    except OSError:
        return True
    finally:
        os.close(fd)


def _acquire(path: Path) -> Lock | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    if os.name != "nt":
        import fcntl

        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return None
    return Lock(path, fd)


def run_preflight(
    target: Path,
    payload_bytes: int = 0,
    backup_bytes: int = 0,
    acquire: bool = False,
    client_retries: int = 1,
    backoff_s: float = 0,
) -> PreflightResult:
    target = Path(target)
    need = int(payload_bytes) + int(backup_bytes)
    if (target / CAP_MARK).is_file():
        return PreflightResult(EXIT_DISK, "disk-full")
    try:
        free = shutil.disk_usage(target).free
    except OSError:
        free = 0
    if free < need:
        return PreflightResult(EXIT_DISK, "disk-full")
    if not os.access(target, os.W_OK):
        return PreflightResult(EXIT_PERM, "target-not-writable")
    plugin_json = target / "plugin.json"
    for _ in range(max(1, client_retries)):
        if plugin_json.exists() and _locked(plugin_json):
            if backoff_s:
                time.sleep(backoff_s)
                continue
            return PreflightResult(EXIT_CLIENT_LOCK, "client-write-lock")
        break
    else:
        return PreflightResult(EXIT_CLIENT_LOCK, "client-write-lock")
    lock_path = target / LOCK_NAME
    if acquire:
        held = _acquire(lock_path)
        if held is None:
            return PreflightResult(EXIT_LIFECYCLE_LOCK, "lifecycle-lock-held")
        return PreflightResult(EXIT_OK, "ok", lock=held)
    if lock_path.exists() and _locked(lock_path):
        return PreflightResult(EXIT_LIFECYCLE_LOCK, "lifecycle-lock-held")
    return PreflightResult(EXIT_OK, "ok")


def spawn_lock_holder(path: Path) -> subprocess.Popen:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "import os,time,sys\n"
        "p=sys.argv[1]\n"
        "fd=os.open(p, os.O_RDWR|os.O_CREAT, 0o644)\n"
        "os.write(fd, b'hold\\n')\n"
    )
    if os.name != "nt":
        script += (
            "import fcntl\n"
            "fcntl.flock(fd, fcntl.LOCK_EX)\n"
        )
    script += "time.sleep(30)\n"
    return subprocess.Popen(
        [os.environ.get("PYTHON", "python3"), "-c", script, str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def stop_holder(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except Exception:
        proc.kill()
