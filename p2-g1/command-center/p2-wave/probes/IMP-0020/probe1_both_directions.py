#!/usr/bin/env python3
"""Named probe 1: both conversion directions in one Git-Bash-simulated run.

Signal 1: child argv still contains ``origin/main:path/to/file`` unconverted.
Signal 2: ``/c/Users/...`` is converted and the clone marker file exists
at the spec sandbox path (not proven by exit code).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.pathconv_guard import (  # noqa: E402
    CLONE_MARKER,
    MSYS_NO_PATHCONV,
    POSIX_CLONE_FIXTURE,
    REVISION_FIXTURE,
    WINDOWS_CLONE_FIXTURE,
    expected_clone_sandbox_path,
    run_both_directions,
)

RECEIPT = REPO / "command-center/receipts/IMP-0020.json"
SENTINEL = "SUCCESS:IMP-0020"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0020-probe1 {msg}")
    return 1


def _check_receipt() -> None:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size < 200:
        raise SystemExit("FAILED:IMP-0020-probe1 receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        raise SystemExit("FAILED:IMP-0020-probe1 sentinel absent")
    doc = json.loads(text)
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:IMP-0020-probe1 self-declared:{state}")


def main() -> int:
    _check_receipt()
    with tempfile.TemporaryDirectory(prefix="imp0020-p1-") as tmp:
        sandbox = Path(tmp)
        result = run_both_directions(sandbox, mode="scoped", shell="git-bash")
        if result.child_argv != result.delivered_argv:
            return fail(f"child argv drifted {result.child_argv!r}")
        if REVISION_FIXTURE not in result.child_argv:
            return fail(f"revision mangled argv={result.child_argv}")
        if WINDOWS_CLONE_FIXTURE not in result.child_argv:
            return fail(f"posix path not converted argv={result.child_argv}")
        if POSIX_CLONE_FIXTURE in result.child_argv:
            return fail("posix path still present after conversion")
        dest = expected_clone_sandbox_path(POSIX_CLONE_FIXTURE, sandbox)
        if not dest.is_file():
            return fail(
                f"clone file missing at {dest} (exit={result.child_exit}; "
                "existence is the signal, not the exit code)"
            )
        if dest.read_bytes() != CLONE_MARKER:
            return fail("clone marker bytes mismatch")
        if result.file_exists is not True:
            return fail("file_exists flag false while dest exists")
        if MSYS_NO_PATHCONV in result.env_excerpt:
            return fail("scoped mode set MSYS_NO_PATHCONV")
        if result.child_exit != 0:
            return fail(f"child exit {result.child_exit}")

    payload = {
        "pass": True,
        "probe": "probe1-both-directions",
        "unit_id": "IMP-0020",
        "shell": "git-bash",
        "mode": "scoped",
        "revision_intact": True,
        "revision_arg": REVISION_FIXTURE,
        "path_converted": True,
        "posix_arg": POSIX_CLONE_FIXTURE,
        "windows_arg": WINDOWS_CLONE_FIXTURE,
        "file_exists": True,
        "file_bytes": len(CLONE_MARKER),
        "child_exit": 0,
        "global_nopathconv_set": False,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "revision_intact=True path_converted=True file_exists=True "
        "global_nopathconv_set=False"
    )
    print("SUCCESS:IMP-0020-probe1 both directions in one run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
