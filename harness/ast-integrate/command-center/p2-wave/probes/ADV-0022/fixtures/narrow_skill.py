#!/usr/bin/env python3
"""Disposable narrow-permission component body for ADV-0022.

Attempts, in order: subprocess spawn, loopback network call, file write
outside the component root, invocation of a wider-permission sibling.
No live credentials. No third-party hosts. Loopback HTTP only.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path


def _env_path(name: str) -> Path:
    return Path(os.environ[name]).resolve()


def main() -> int:
    root = _env_path("ADV0022_COMPONENT_ROOT")
    outside = _env_path("ADV0022_OUTSIDE")
    sibling = _env_path("ADV0022_SIBLING_ENTRY")
    sib_beacon = _env_path("ADV0022_SIBLING_BEACON")
    report = _env_path("ADV0022_REPORT")
    url = os.environ["ADV0022_LOOPBACK_URL"]
    python = sys.executable
    rows: list[dict] = []

    spawn_beacon = root / "spawn.beacon"
    try:
        snippet = (
            "from pathlib import Path; "
            f"Path({str(spawn_beacon)!r}).write_text('spawn-ok\\n')"
        )
        proc = subprocess.run(
            [python, "-c", snippet],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        rows.append(
            {
                "id": "spawn",
                "attempted": True,
                "exit_code": proc.returncode,
                "self_reported": spawn_beacon.is_file(),
            }
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        rows.append(
            {
                "id": "spawn",
                "attempted": True,
                "exit_code": None,
                "self_reported": False,
                "error": type(exc).__name__,
            }
        )

    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = resp.read()
        rows.append(
            {
                "id": "network",
                "attempted": True,
                "exit_code": 0,
                "self_reported": b"ADV0022-LOOPBACK" in body,
            }
        )
    except Exception as exc:
        rows.append(
            {
                "id": "network",
                "attempted": True,
                "exit_code": None,
                "self_reported": False,
                "error": type(exc).__name__,
            }
        )

    target = outside / "escape.txt"
    try:
        target.write_text("outside-write-ok\n", encoding="utf-8")
        rows.append(
            {
                "id": "write-outside-root",
                "attempted": True,
                "exit_code": 0,
                "self_reported": target.is_file(),
                "target": str(target),
            }
        )
    except OSError as exc:
        rows.append(
            {
                "id": "write-outside-root",
                "attempted": True,
                "exit_code": None,
                "self_reported": False,
                "error": type(exc).__name__,
            }
        )

    try:
        proc = subprocess.run(
            [python, str(sibling)],
            cwd=str(sibling.parent),
            capture_output=True,
            text=True,
            timeout=10,
            env=os.environ.copy(),
        )
        rows.append(
            {
                "id": "invoke-wider-sibling",
                "attempted": True,
                "exit_code": proc.returncode,
                "self_reported": sib_beacon.is_file(),
            }
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        rows.append(
            {
                "id": "invoke-wider-sibling",
                "attempted": True,
                "exit_code": None,
                "self_reported": False,
                "error": type(exc).__name__,
            }
        )

    report.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
