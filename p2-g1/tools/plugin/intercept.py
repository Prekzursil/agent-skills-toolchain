"""Userspace exec/write/network intercept installed into policy-run children."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

DENY_EXIT = 78
POLICY_ENV = "IMP0064_POLICY_JSON"


def _policy() -> dict:
    raw = os.environ.get(POLICY_ENV) or "{}"
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError:
        doc = {}
    return doc if isinstance(doc, dict) else {}


def _allowed_exec(policy: dict, argv0: str) -> bool:
    allowed = [str(x) for x in (policy.get("allowed_executables") or [])]
    if not allowed:
        return True
    name = Path(argv0).name
    resolved = argv0
    for item in allowed:
        if argv0 == item or name == Path(item).name or resolved == item:
            return True
        try:
            if Path(argv0).resolve() == Path(item).resolve():
                return True
        except OSError:
            continue
    python_ok = Path(sys.executable).name
    if name in {python_ok, "python", "python3", "python.exe"}:
        return True
    return False


def _write_allowed(policy: dict, dest: Path) -> bool:
    roots = [Path(x) for x in (policy.get("allowed_write_roots") or [])]
    if not roots:
        return True
    try:
        real = dest.resolve()
    except OSError:
        real = dest
    for root in roots:
        try:
            real.relative_to(root.resolve())
            return True
        except (ValueError, OSError):
            continue
    return False


def _net_allowed(policy: dict, host: str, port: int) -> bool:
    mode = str(policy.get("network_mode") or "deny")
    if mode in {"allow", "off"}:
        return True
    endpoints = policy.get("endpoints") or []
    for ep in endpoints:
        if isinstance(ep, (list, tuple)) and len(ep) >= 2:
            if str(ep[0]) == str(host) and int(ep[1]) == int(port):
                return True
        if isinstance(ep, dict):
            if str(ep.get("host")) == str(host) and int(ep.get("port") or 0) == int(port):
                return True
        if isinstance(ep, str) and ep == f"{host}:{port}":
            return True
    return False


def _die(code: str) -> None:
    sys.stderr.write(code + "\n")
    sys.stderr.flush()
    raise SystemExit(DENY_EXIT)


def install() -> None:
    policy = _policy()
    orig_popen = subprocess.Popen
    orig_run = subprocess.run
    orig_connection = socket.create_connection
    orig_write_text = Path.write_text
    orig_write_bytes = Path.write_bytes
    orig_open = Path.open

    def popen(argv, *args, **kwargs):  # noqa: ANN001
        argv0 = argv[0] if isinstance(argv, (list, tuple)) else str(argv)
        if not _allowed_exec(policy, str(argv0)):
            _die("FORBIDDEN_SPAWN")
        return orig_popen(argv, *args, **kwargs)

    def run(argv, *args, **kwargs):  # noqa: ANN001
        argv0 = argv[0] if isinstance(argv, (list, tuple)) else str(argv)
        if not _allowed_exec(policy, str(argv0)):
            _die("FORBIDDEN_SPAWN")
        return orig_run(argv, *args, **kwargs)

    def create_connection(address, *args, **kwargs):  # noqa: ANN001
        host, port = address[0], int(address[1])
        if not _net_allowed(policy, str(host), port):
            _die("FORBIDDEN_NETWORK")
        return orig_connection(address, *args, **kwargs)

    def write_text(self, data, *args, **kwargs):  # noqa: ANN001
        if not _write_allowed(policy, self):
            _die("FORBIDDEN_WRITE")
        return orig_write_text(self, data, *args, **kwargs)

    def write_bytes(self, data, *args, **kwargs):  # noqa: ANN001
        if not _write_allowed(policy, self):
            _die("FORBIDDEN_WRITE")
        return orig_write_bytes(self, data, *args, **kwargs)

    def path_open(self, mode="r", *args, **kwargs):  # noqa: ANN001
        if any(ch in str(mode) for ch in "wax+"):
            if not _write_allowed(policy, self):
                _die("FORBIDDEN_WRITE")
        return orig_open(self, mode, *args, **kwargs)

    subprocess.Popen = popen  # type: ignore[assignment]
    subprocess.run = run  # type: ignore[assignment]
    socket.create_connection = create_connection  # type: ignore[assignment]
    Path.write_text = write_text  # type: ignore[assignment]
    Path.write_bytes = write_bytes  # type: ignore[assignment]
    Path.open = path_open  # type: ignore[assignment]
