#!/usr/bin/env python3
"""Probe 1: foreign write refused; pinned write permitted; missing origin refused.

Evidence for TST-0100: a scratch clone of a DIFFERENT repository cannot
receive a guarded write; a scratch clone whose origin is the pin can.
A worktree with no origin is refused (never default-allow).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from guard import guarded_write, normalize_origin  # noqa: E402
from scratch import (  # noqa: E402
    ALT_PINNED_ORIGIN,
    FOREIGN_ORIGIN,
    PINNED_ORIGIN,
    make_repo,
)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0100-p1-") as tmp_s:
        tmp = Path(tmp_s)
        pinned = make_repo(tmp / "pinned", PINNED_ORIGIN)
        foreign = make_repo(tmp / "foreign", FOREIGN_ORIGIN)
        bare = make_repo(tmp / "no-origin", None)
        alt = make_repo(tmp / "alt-url-form", ALT_PINNED_ORIGIN)

        r_foreign = guarded_write(foreign, "must-not-land.txt", b"foreign-payload\n")
        r_pinned = guarded_write(pinned, "ok.txt", b"pinned-payload\n")
        r_bare = guarded_write(bare, "must-not-land.txt", b"bare-payload\n")
        r_alt = guarded_write(alt, "ok-alt.txt", b"alt-pin-payload\n")

        foreign_file = foreign / "must-not-land.txt"
        pinned_file = pinned / "ok.txt"
        bare_file = bare / "must-not-land.txt"
        alt_file = alt / "ok-alt.txt"

        fail = []
        if r_foreign.allowed or r_foreign.wrote or foreign_file.exists():
            fail.append("foreign-write-not-refused")
        if r_foreign.reason != "origin-mismatch":
            fail.append(f"foreign-reason:{r_foreign.reason}")
        if r_foreign.origin != FOREIGN_ORIGIN:
            fail.append(f"foreign-origin-not-from-git:{r_foreign.origin!r}")
        if not r_pinned.allowed or not r_pinned.wrote or not pinned_file.is_file():
            fail.append("pinned-write-not-permitted")
        if pinned_file.read_bytes() != b"pinned-payload\n":
            fail.append("pinned-payload-mismatch")
        if r_bare.allowed or r_bare.wrote or bare_file.exists():
            fail.append("missing-origin-default-allow")
        if r_bare.reason != "missing-origin":
            fail.append(f"bare-reason:{r_bare.reason}")
        if not r_alt.allowed or alt_file.read_bytes() != b"alt-pin-payload\n":
            fail.append("alt-url-form-not-normalized")
        if normalize_origin(r_alt.origin or "") != normalize_origin(PINNED_ORIGIN):
            fail.append("alt-url-normalize")
        cmd = r_foreign.command
        if cmd[:2] != ["git", "-C"] or cmd[3:] != ["remote", "get-url", "origin"]:
            fail.append(f"resolve-command:{cmd}")

        result = {
            "probe": "probe1-foreign-and-pinned",
            "unit_id": "TST-0100",
            "pass": not fail,
            "fail": fail,
            "pinned_origin": PINNED_ORIGIN,
            "foreign_origin": FOREIGN_ORIGIN,
            "rows": [
                {
                    "id": "foreign",
                    "path": str(foreign),
                    "origin": r_foreign.origin,
                    "allowed": r_foreign.allowed,
                    "wrote": r_foreign.wrote,
                    "file_exists": foreign_file.exists(),
                    "reason": r_foreign.reason,
                    "command": r_foreign.command,
                },
                {
                    "id": "pinned",
                    "path": str(pinned),
                    "origin": r_pinned.origin,
                    "allowed": r_pinned.allowed,
                    "wrote": r_pinned.wrote,
                    "file_exists": pinned_file.is_file(),
                    "reason": r_pinned.reason,
                    "command": r_pinned.command,
                },
                {
                    "id": "missing-origin",
                    "path": str(bare),
                    "origin": r_bare.origin,
                    "allowed": r_bare.allowed,
                    "wrote": r_bare.wrote,
                    "file_exists": bare_file.exists(),
                    "reason": r_bare.reason,
                    "command": r_bare.command,
                    "git_exit": r_bare.git_exit,
                },
                {
                    "id": "alt-url-form",
                    "path": str(alt),
                    "origin": r_alt.origin,
                    "allowed": r_alt.allowed,
                    "wrote": r_alt.wrote,
                    "reason": r_alt.reason,
                },
            ],
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        if fail:
            print(f"FAILED:TST-0100-probe1 {fail}")
            return 1
        print(
            "foreign_refused=True pinned_permitted=True missing_origin_refused=True "
            "alt_url_form_permitted=True"
        )
        print("SUCCESS:TST-0100-probe1 foreign refused, pinned permitted")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
