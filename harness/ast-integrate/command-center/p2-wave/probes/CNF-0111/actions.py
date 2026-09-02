"""Action prober: filesystem, network, process spawn, credential presence.

Credential trials check PRESENCE only. The marker bytes are never read or printed.
"""
from __future__ import annotations

import socket
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from enforcement import Gate, PermissionDenied

MARKER_NAME = "credential.marker"
WRITE_NAME = "cnf0111-write.flag"
OUTSIDE_NAME = "cnf0111-outside.flag"
CRED_ENV = "CNF0111_CRED_PRESENT"


def _env_present(name: str) -> bool:
    return name in os_environ_keys()


def os_environ_keys() -> set[str]:
    import os

    return set(os.environ.keys())


def prepare_credential_marker(root: Path) -> Path:
    path = root / MARKER_NAME
    path.write_bytes(b"\x00presence-only")
    return path


def fs_write(gate: Gate, dest: Path) -> dict[str, Any]:
    try:
        gate.check("filesystem", "write")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("cnf-0111-write", encoding="utf-8")
        return {"observed": "succeeded", "code": None, "error": None}
    except PermissionDenied as exc:
        return {"observed": "blocked", "code": exc.code, "error": str(exc)}


def fs_write_outside(gate: Gate, dest: Path) -> dict[str, Any]:
    try:
        gate.check("filesystem", "write")
        gate.deny_outside_root()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("cnf-0111-outside", encoding="utf-8")
        return {"observed": "succeeded", "code": None, "error": None}
    except PermissionDenied as exc:
        return {"observed": "blocked", "code": exc.code, "error": str(exc)}


def network_connect(gate: Gate) -> dict[str, Any]:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(2.0)
    host, port = srv.getsockname()

    def _accept() -> None:
        try:
            conn, _ = srv.accept()
            conn.close()
        except OSError:
            pass

    threading.Thread(target=_accept, daemon=True).start()
    try:
        gate.check("network", "connect")
        sock = socket.create_connection((host, port), timeout=2)
        sock.close()
        return {
            "observed": "succeeded",
            "code": None,
            "error": None,
            "endpoint": f"{host}:{port}",
        }
    except PermissionDenied as exc:
        return {"observed": "blocked", "code": exc.code, "error": str(exc)}
    finally:
        srv.close()


def process_spawn(gate: Gate) -> dict[str, Any]:
    try:
        gate.check("process-spawn", "subprocess")
        proc = subprocess.run(
            [sys.executable, "-c", "raise SystemExit(0)"],
            check=True,
            timeout=10,
            capture_output=True,
        )
        return {
            "observed": "succeeded",
            "code": None,
            "error": None,
            "exit_code": proc.returncode,
        }
    except PermissionDenied as exc:
        return {"observed": "blocked", "code": exc.code, "error": str(exc)}


def credential_presence(gate: Gate, marker: Path) -> dict[str, Any]:
    """Presence only: Path.is_file and env-name membership. No read, no print."""
    try:
        gate.check("credential-read", "presence")
        present = marker.is_file()
        env_set = _env_present(CRED_ENV)
        return {
            "observed": "succeeded",
            "code": None,
            "error": None,
            "marker_present": present,
            "env_name_present": env_set,
            "value_read": False,
            "value_printed": False,
        }
    except PermissionDenied as exc:
        return {
            "observed": "blocked",
            "code": exc.code,
            "error": str(exc),
            "value_read": False,
            "value_printed": False,
        }


def side_effect_occurred(path: Path | None, observed: str) -> bool:
    if path is None:
        return observed == "succeeded"
    return path.is_file()
