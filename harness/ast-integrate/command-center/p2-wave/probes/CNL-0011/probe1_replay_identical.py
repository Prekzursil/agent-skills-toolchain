#!/usr/bin/env python3
"""Probe 1: same seeds twice + pause/resume yield byte-identical transcripts.

Oracle: scripted-participant replay (SHA-256 of canonical JSON) plus an
independent line-join hash of the same events. A wall-clock leak fails
pause/resume identity.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import replay_engine as E  # noqa: E402


def main() -> int:
    ident = E.two_run_identity()
    pause = E.pause_resume_match(5)
    pause2 = E.pause_resume_match(11)
    print(json.dumps({"identity": ident, "pause_5": pause, "pause_11": pause2}, sort_keys=True))
    print(
        f"two_run_identical={ident['match']} events={ident['events']} "
        f"sha={ident['sha_a']} line_join_match={ident['line_join_sha_a']==ident['line_join_sha_b']}"
    )
    print(
        f"pause_resume_5 match={pause['match']} "
        f"unint={pause['uninterrupted_sha']} resumed={pause['resumed_sha']}"
    )
    print(
        f"pause_resume_11 match={pause2['match']} "
        f"unint={pause2['uninterrupted_sha']} resumed={pause2['resumed_sha']}"
    )
    if not ident["match"]:
        print("FAILED:CNL-0011-probe1 two same-seed runs diverged")
        return 1
    if ident["line_join_sha_a"] != ident["line_join_sha_b"]:
        print("FAILED:CNL-0011-probe1 line-join hash diverged (second mechanism)")
        return 1
    if ident["sha_a"] != ident["sha_b"]:
        print("FAILED:CNL-0011-probe1 array-sha diverged")
        return 1
    if not pause["match"] or not pause2["match"]:
        print("FAILED:CNL-0011-probe1 pause/resume transcript mismatch")
        return 1
    if pause["uninterrupted_events"] < 8:
        print("FAILED:CNL-0011-probe1 transcript too short to be a real council")
        return 1
    print("SUCCESS:CNL-0011-probe1 same-seed replay and pause/resume identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
