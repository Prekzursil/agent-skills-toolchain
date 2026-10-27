"""Runtime permission enforcement independent of the renderer (IMP-0059)."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import socket
import subprocess
from typing import Any, Callable

from marketplace.permission_catalog import extract_records


class Codes:
    FS_WRITE_UNDECLARED = "FS_WRITE_UNDECLARED"
    SPAWN_UNDECLARED = "SPAWN_UNDECLARED"
    NETWORK_UNDECLARED = "NETWORK_UNDECLARED"
    FS_SYMLINK_ESCAPE = "FS_SYMLINK_ESCAPE"
    FS_TRAVERSAL = "FS_TRAVERSAL"
    FS_TOCTOU = "FS_TOCTOU"


class PermissionDenied(Exception):
    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


@dataclass
class PermissionManifest:
    fs_write_roots: tuple = ()
    allow_spawn: bool = False
    allow_network: bool = False
    component: str = ""


def _as_path(path) -> Path:
    return Path(path)


def _under_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        try:
            return os.path.commonpath([str(path.resolve()), str(root.resolve())]) == str(
                root.resolve()
            )
        except (OSError, ValueError):
            return False


class PermissionEnforcer:
    def __init__(self, manifest: PermissionManifest):
        self.manifest = manifest
        self._after_authorize_hook: Callable[[], None] | None = None

    def _roots(self) -> list[Path]:
        return [_as_path(r) for r in self.manifest.fs_write_roots]

    def _path_has_dotdot(self, path: Path) -> bool:
        return any(part == ".." for part in Path(path).parts)

    def _symlink_escapes(self, path: Path, roots: list[Path]) -> bool:
        cur = path
        seen = 0
        while True:
            if cur.is_symlink():
                try:
                    resolved = cur.resolve()
                except OSError:
                    return True
                if roots and not any(_under_root(resolved, root) for root in roots):
                    return True
            if cur == cur.parent or seen > 64:
                break
            cur = cur.parent
            seen += 1
        try:
            resolved = path.parent.resolve() if path.parent.exists() else path.parent
        except OSError:
            return True
        if roots and not any(_under_root(resolved, root) for root in roots):
            # Followed a hop out of the declared root.
            return True
        return False

    def write_file(self, path, data: bytes) -> None:
        roots = self._roots()
        target = _as_path(path)
        if not roots:
            raise PermissionDenied(Codes.FS_WRITE_UNDECLARED)
        if self._path_has_dotdot(target):
            raise PermissionDenied(Codes.FS_TRAVERSAL)
        if self._symlink_escapes(target, roots):
            raise PermissionDenied(Codes.FS_SYMLINK_ESCAPE)
        if self._after_authorize_hook is not None:
            self._after_authorize_hook()
            if self._symlink_escapes(target, roots) or (
                target.parent.is_symlink()
                and not any(_under_root(target.parent.resolve(), root) for root in roots)
            ):
                raise PermissionDenied(Codes.FS_TOCTOU)
        try:
            resolved_parent = target.parent.resolve()
        except OSError as exc:
            raise PermissionDenied(Codes.FS_WRITE_UNDECLARED) from exc
        if not any(_under_root(resolved_parent, root) for root in roots):
            raise PermissionDenied(Codes.FS_WRITE_UNDECLARED)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def spawn(self, argv):
        if not self.manifest.allow_spawn:
            raise PermissionDenied(Codes.SPAWN_UNDECLARED)
        return subprocess.Popen(list(argv))

    def connect(self, host: str, port: int, timeout: float = 2.0):
        if not self.manifest.allow_network:
            raise PermissionDenied(Codes.NETWORK_UNDECLARED)
        return socket.create_connection((host, int(port)), timeout=timeout)


def listener():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(0.2)
    port = srv.getsockname()[1]
    return srv, port


def listener_accepted(srv) -> bool:
    try:
        conn, _ = srv.accept()
        conn.close()
        return True
    except OSError:
        return False


def oob_path_exists(path) -> bool:
    return Path(path).exists()


def oob_pid_alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def oob_proc_cmdline_matches(marker: str) -> list:
    hits: list[int] = []
    proc = Path("/proc")
    if not proc.is_dir():
        return hits
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmd = (entry / "cmdline").read_bytes().replace(b"\x00", b" ")
            text = cmd.decode("utf-8", "replace")
        except OSError:
            continue
        if marker in text:
            hits.append(int(entry.name))
    return hits


def query_enforced_set(pkg: dict[str, Any]) -> list[str]:
    return [
        r["id"]
        for r in extract_records(pkg)
        if str(r.get("enforcement") or "gated").lower() in {"gated", "enforced", "hook"}
    ]


def query_decorative(pkg: dict[str, Any]) -> list[str]:
    return [
        r["id"]
        for r in extract_records(pkg)
        if str(r.get("enforcement") or "").lower() in {"decorative", "declared-only", "ui"}
    ]


def query_effective(pkg: dict[str, Any]) -> dict[str, Any]:
    declared = [r["id"] for r in extract_records(pkg)]
    enforced = query_enforced_set(pkg)
    decorative = query_decorative(pkg)
    return {
        "declared": declared,
        "enforced": enforced,
        "decorative": decorative,
        "declared_equals_enforced": set(declared) == set(enforced) and not decorative,
    }
