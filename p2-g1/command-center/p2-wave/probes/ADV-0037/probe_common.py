#!/usr/bin/env python3
"""Shared ADV-0037 planted-synthetic helpers.

The planted value is computed at runtime so the distinctive body is not a
source literal. Reports record prefix + sha256 + length only.
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import tempfile
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0037"
PREFIX = "syn37_"
PLANTED = PREFIX + hashlib.sha256(b"adv-0037-synthetic-plant-v1").hexdigest()
PLANTED_SHA = hashlib.sha256(PLANTED.encode("utf-8")).hexdigest()
ELIDE = PREFIX + "<elided-body>"
SAFE_SPAWN_KEYS = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "TZ",
    "PYTHONDONTWRITEBYTECODE",
    "PYTHONHASHSEED",
)
CREDENTIAL_KEY_MARKERS = (
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "CREDENTIAL",
    "API_KEY",
    "PRIVATE_KEY",
    "AUTHORIZATION",
    "CURSOR_API",
    "OPENAI",
    "ANTHROPIC",
    "AWS_",
    "GH_TOKEN",
    "GITHUB_TOKEN",
)


def planted_meta() -> dict[str, Any]:
    return {
        "prefix": PREFIX,
        "sha256": PLANTED_SHA,
        "bytes": len(PLANTED.encode("utf-8")),
        "synthetic": True,
        "authenticating": False,
    }


def sanitize(text: str) -> str:
    if not text:
        return text
    return text.replace(PLANTED, ELIDE)


def allowlisted_env(*, home: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    env: dict[str, str] = {"PYTHONDONTWRITEBYTECODE": "1", "HOME": str(home)}
    for key in SAFE_SPAWN_KEYS:
        val = os.environ.get(key)
        if val and key != "HOME":
            env[key] = val
    if extra:
        env.update(extra)
    leaked_parent = [
        k
        for k in env
        if any(m.lower() in k.lower() for m in CREDENTIAL_KEY_MARKERS)
        and k not in (extra or {})
    ]
    if leaked_parent:
        raise RuntimeError(f"refusing parent credential keys {leaked_parent}")
    return env


def parent_secret_keys_unread() -> list[str]:
    """Names present in the parent environment that this unit must not read."""
    names = []
    for k in os.environ:
        if any(m.lower() in k.lower() for m in CREDENTIAL_KEY_MARKERS):
            names.append(k)
    return sorted(names)


def sweep_text(text: str) -> bool:
    return PLANTED in (text or "")


def sweep_tree(root: Path) -> list[str]:
    hits: list[str] = []
    if not root.exists():
        return hits
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if PLANTED.encode("utf-8") in raw:
            hits.append(path.name)
    return hits


def capture_channels(root: Path, stdout: str, stderr: str) -> dict[str, Any]:
    files = sweep_tree(root)
    return {
        "stdout": sweep_text(stdout),
        "stderr": sweep_text(stderr),
        "files": files,
        "hit": sweep_text(stdout) or sweep_text(stderr) or bool(files),
    }


class EgressGuard:
    def __init__(self) -> None:
        self.attempts: list[str] = []
        self._orig: dict[str, Any] = {}

    def _record(self, kind: str, detail: str) -> None:
        self.attempts.append(f"{kind}:{detail}")
        raise RuntimeError(f"network {kind} blocked: {detail}")

    def __enter__(self) -> "EgressGuard":
        self._orig["connect"] = socket.socket.connect
        self._orig["connect_ex"] = socket.socket.connect_ex
        self._orig["create"] = socket.create_connection
        self._orig["getaddrinfo"] = socket.getaddrinfo
        guard = self

        def connect(sock: socket.socket, address: Any) -> Any:
            guard._record("connect", repr(address))

        def connect_ex(sock: socket.socket, address: Any) -> Any:
            guard._record("connect_ex", repr(address))

        def create_connection(address: Any, *a: Any, **k: Any) -> Any:
            guard._record("create_connection", repr(address))

        def getaddrinfo(*a: Any, **k: Any) -> Any:
            guard._record("getaddrinfo", repr(a[:2]))

        socket.socket.connect = connect  # type: ignore[method-assign]
        socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]
        socket.create_connection = create_connection  # type: ignore[assignment]
        socket.getaddrinfo = getaddrinfo  # type: ignore[assignment]
        return self

    def __exit__(self, *exc: Any) -> None:
        socket.socket.connect = self._orig["connect"]  # type: ignore[method-assign]
        socket.socket.connect_ex = self._orig["connect_ex"]  # type: ignore[method-assign]
        socket.create_connection = self._orig["create"]  # type: ignore[assignment]
        socket.getaddrinfo = self._orig["getaddrinfo"]  # type: ignore[assignment]


def dump_json(doc: dict[str, Any]) -> str:
    return json.dumps(doc, indent=1, sort_keys=True, default=str)


def isolated_root() -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory(prefix="adv0037-")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_detector_control(root: Path) -> dict[str, Any]:
    """Deliberate leak vs redacted good state. Never prints the planted body."""
    bad = root / "detector-bad.log"
    good = root / "detector-good.log"
    prefix_only = root / "detector-prefix-only.log"
    write_text(bad, f"scratch print once: {PLANTED}\n")
    write_text(good, f"scratch print once: {PREFIX}***\n")
    write_text(prefix_only, f"prefix-only {PREFIX} with no body\n")
    planted_b = PLANTED.encode("utf-8")
    fired = planted_b in bad.read_bytes()
    silent = planted_b not in good.read_bytes()
    prefix_false_positive = planted_b in prefix_only.read_bytes()
    return {
        "id": "detector-control",
        "fired_on_bad_state": fired,
        "silent_on_good_state": silent,
        "prefix_only_is_not_a_hit": not prefix_false_positive,
        "expect_clean_on_bad_would_exit": 1 if fired else 0,
        "bad_channels": ["detector-bad.log"] if fired else [],
        "good_channels": [],
        "pass": fired and silent and not prefix_false_positive,
    }


def with_isolation(fn: Callable[[Path], dict[str, Any]]) -> dict[str, Any]:
    with isolated_root() as tmp:
        root = Path(tmp)
        with EgressGuard() as guard:
            result = fn(root)
        result["egress_attempts"] = list(guard.attempts)
        leftover = sweep_tree(root)
        result["runtime_tree_hits_before_delete"] = leftover
        return result


# Names used by probe_case / emit (stable aliases).
write_text = write_text
capture_channels = capture_channels
run_detector_control = run_detector_control
planted_meta = planted_meta
parent_secret_keys_unread = parent_secret_keys_unread
with_isolation = with_isolation
dump_json = dump_json
sanitize = sanitize
PLANTED_SHA = PLANTED_SHA
planted_meta = planted_meta
dump_json = dump_json
dump_json = dump_json
