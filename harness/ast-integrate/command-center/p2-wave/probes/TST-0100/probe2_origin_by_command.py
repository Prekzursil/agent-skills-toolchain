#!/usr/bin/env python3
"""Probe 2: origin is resolved by git command, not by the path string.

A directory whose path *looks* like the pinned repo but whose origin is
foreign must be refused. An unrelated path whose origin *is* the pin must
be permitted. The live argv is git -C <worktree> remote get-url origin.

This is the independent reviewer signal vs probe 1's both-states table.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from guard import guarded_write, load_pin, normalize_origin  # noqa: E402
from scratch import FOREIGN_ORIGIN, PINNED_ORIGIN, make_repo  # noqa: E402


def main() -> int:
    pin = load_pin()
    with tempfile.TemporaryDirectory(prefix="tst0100-p2-") as tmp_s:
        tmp = Path(tmp_s)
        decoy = tmp / "https:" / "github.com" / "program" / "ast-integrate"
        unrelated = tmp / "box-unrelated-9f3a"
        make_repo(decoy, FOREIGN_ORIGIN)
        make_repo(unrelated, PINNED_ORIGIN)

        r_decoy = guarded_write(decoy, "planted.txt", b"decoy-must-not-land\n")
        r_ok = guarded_write(unrelated, "ok.txt", b"unrelated-path-pinned-origin\n")

        decoy_file = decoy / "planted.txt"
        ok_file = unrelated / "ok.txt"

        fail = []
        if "ast-integrate" not in decoy.as_posix():
            fail.append("decoy-path-does-not-look-pinned")
        if "ast-integrate" in unrelated.as_posix():
            fail.append("unrelated-path-contains-pin-token")
        if r_decoy.allowed or r_decoy.wrote or decoy_file.exists():
            fail.append("path-decoy-was-allowed")
        if r_decoy.reason != "origin-mismatch":
            fail.append(f"decoy-reason:{r_decoy.reason}")
        if r_decoy.origin != FOREIGN_ORIGIN:
            fail.append(
                "decoy-origin-not-from-git-command:"
                f"{r_decoy.origin!r} (a path-string guard would invent the pin)"
            )
        if not r_ok.allowed or not ok_file.is_file():
            fail.append("unrelated-path-with-pin-origin-refused")
        if ok_file.is_file() and ok_file.read_bytes() != b"unrelated-path-pinned-origin\n":
            fail.append("unrelated-payload-mismatch")
        if normalize_origin(r_ok.origin or "") != normalize_origin(pin):
            fail.append(f"ok-origin:{r_ok.origin!r}")

        for label, row in (("decoy", r_decoy), ("ok", r_ok)):
            cmd = row.command
            if len(cmd) < 6:
                fail.append(f"{label}-short-command:{cmd}")
                continue
            if cmd[0] != "git" or cmd[1] != "-C" or cmd[3:] != ["remote", "get-url", "origin"]:
                fail.append(f"{label}-not-git-remote-get-url:{cmd}")
            if Path(cmd[2]).resolve() != row.worktree.resolve():
                fail.append(f"{label}-C-target-mismatch")

        src = (HERE / "guard.py").read_text(encoding="utf-8")
        if "remote" not in src or "get-url" not in src:
            fail.append("guard-source-missing-get-url")
        if "normalize_origin(resolved.origin)" not in src:
            fail.append("guard-source-missing-origin-compare")

        result = {
            "probe": "probe2-origin-by-command",
            "unit_id": "TST-0100",
            "pass": not fail,
            "fail": fail,
            "reviewer_id": "TST-0100-probe2-origin-by-command",
            "independent": True,
            "re_ran_detector_control": True,
            "decoy_path_contains_pin_token": "ast-integrate" in decoy.as_posix(),
            "unrelated_path_contains_pin_token": "ast-integrate" in unrelated.as_posix(),
            "decoy": {
                "path": str(decoy),
                "origin": r_decoy.origin,
                "allowed": r_decoy.allowed,
                "wrote": r_decoy.wrote,
                "file_exists": decoy_file.exists(),
                "reason": r_decoy.reason,
                "command": r_decoy.command,
            },
            "unrelated_path_pinned_origin": {
                "path": str(unrelated),
                "origin": r_ok.origin,
                "allowed": r_ok.allowed,
                "wrote": r_ok.wrote,
                "file_exists": ok_file.is_file(),
                "reason": r_ok.reason,
                "command": r_ok.command,
            },
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        if fail:
            print(f"FAILED:TST-0100-probe2 {fail}")
            return 1
        print(
            "path_decoy_refused=True unrelated_path_with_pin_permitted=True "
            "origin_resolved_by_git_remote_get_url=True"
        )
        print("SUCCESS:TST-0100-probe2 origin by command, not path string")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
