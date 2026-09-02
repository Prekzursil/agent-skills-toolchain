#!/usr/bin/env python3
"""Named probe 2: global-suppression negative control + pwsh7 contrast.

NEGATIVE CONTROL: ``MSYS_NO_PATHCONV=1`` globally must leave ``/c/Users/...``
unconverted so the clone file does NOT appear — proving the test sees the
inversion. Exit code stays 0 (silent no-op); existence is the discriminator.

Reviewer requirement: both directions from Git Bash, not only pwsh7 (where
the MSYS trap does not exist). pwsh7 is run here as the contrast: revision
survives but the POSIX path is also unconverted, so a pwsh7-only run cannot
certify the guard.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.pathconv_guard import (  # noqa: E402
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
    print(f"FAILED:IMP-0020-probe2 {msg}")
    return 1


def _check_receipt() -> None:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size < 200:
        raise SystemExit("FAILED:IMP-0020-probe2 receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        raise SystemExit("FAILED:IMP-0020-probe2 sentinel absent")
    doc = json.loads(text)
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:IMP-0020-probe2 self-declared:{state}")


def main() -> int:
    _check_receipt()
    with tempfile.TemporaryDirectory(prefix="imp0020-p2-") as tmp:
        root = Path(tmp)
        global_run = run_both_directions(
            root / "global", mode="global", shell="git-bash"
        )
        if global_run.env_excerpt.get(MSYS_NO_PATHCONV) != "1":
            return fail("global mode did not set MSYS_NO_PATHCONV")
        if REVISION_FIXTURE not in global_run.child_argv:
            return fail("global control lost the revision (need both-states)")
        if POSIX_CLONE_FIXTURE not in global_run.child_argv:
            return fail("global control still converted the posix path")
        if WINDOWS_CLONE_FIXTURE in global_run.child_argv:
            return fail("global control delivered a windows path")
        dest_g = expected_clone_sandbox_path(POSIX_CLONE_FIXTURE, root / "global")
        if dest_g.is_file():
            return fail("global suppression still wrote the clone file")
        if global_run.file_exists:
            return fail("file_exists true under global suppression")
        if global_run.child_exit != 0:
            return fail("global silent-noop must still exit 0")

        pwsh = run_both_directions(root / "pwsh", mode="scoped", shell="pwsh7")
        if REVISION_FIXTURE not in pwsh.child_argv:
            return fail("pwsh7 mangled revision")
        if POSIX_CLONE_FIXTURE not in pwsh.child_argv:
            return fail("pwsh7 unexpectedly converted posix path")
        dest_p = expected_clone_sandbox_path(POSIX_CLONE_FIXTURE, root / "pwsh")
        if dest_p.is_file() or pwsh.file_exists:
            return fail("pwsh7 wrote a clone file; trap does not exist there")

        scoped = run_both_directions(
            root / "scoped", mode="scoped", shell="git-bash"
        )
        dest_s = expected_clone_sandbox_path(POSIX_CLONE_FIXTURE, root / "scoped")
        if not dest_s.is_file() or not scoped.file_exists:
            return fail("scoped git-bash did not write clone file")
        if REVISION_FIXTURE not in scoped.child_argv:
            return fail("scoped git-bash mangled revision")
        if MSYS_NO_PATHCONV in scoped.env_excerpt:
            return fail("scoped git-bash set MSYS_NO_PATHCONV")

    payload = {
        "pass": True,
        "probe": "probe2-global-control",
        "unit_id": "IMP-0020",
        "negative_control_fired": True,
        "global_revision_intact": True,
        "global_path_converted": False,
        "global_file_exists": False,
        "global_exit_0_silent_noop": True,
        "pwsh7_trap_absent": True,
        "git_bash_scoped_both_directions": True,
        "reviewer": "git-bash-not-only-pwsh7",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "negative_control_fired=True global_file_exists=False "
        "pwsh7_trap_absent=True git_bash_scoped_both_directions=True"
    )
    print("SUCCESS:IMP-0020-probe2 global suppression breaks path-arg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
