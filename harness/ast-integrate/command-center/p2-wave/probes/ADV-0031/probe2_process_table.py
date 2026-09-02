#!/usr/bin/env python3
"""Probe 2: OS process-table argv oracle (mechanically different from canary).

A value that reaches the child unchanged is safe even if stdout looks odd.
A value that alters argv is unsafe even if no canary fired.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402

UNIT = "ADV-0031"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    live = H.run_process_table_campaign()
    sys.stdout.write(H.dump_json(live))
    c = live["controls"]
    if not c["procfs_readable"]:
        return fail("procfs cmdline unreadable")
    if not c["benign_argv_unsplit"]:
        return fail("benign parameter did not reach the child as one argv field")
    if not c["benign_argv_not_altered"]:
        return fail("benign argv-array run altered the process table")
    if not c["semicolon_string_altered"]:
        return fail("process-table oracle silent on planted unquoted string-command")
    if not c["apostrophe_quoted_altered"]:
        return fail("process-table oracle silent on planted apostrophe breakout")
    print(
        f"SUCCESS:{UNIT}-probe2 process-table argv-semicolon-altered="
        f"{not c['semicolon_argv_not_altered']} string-semicolon-altered="
        f"{c['semicolon_string_altered']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
