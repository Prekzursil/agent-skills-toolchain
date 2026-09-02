#!/usr/bin/env python3
"""Probe 1: hand-edit a STATUS.md counter; the gate names the drifted line.

Also: two renders over an unchanged log are byte-identical, and regenerate
silences the gate.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scenario import REPO, TOOLS, populate_ledger, sample_events, sample_receipts  # noqa: E402

sys.path.insert(0, str(TOOLS))
import status_ledger as sl  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cc-0013-p1-") as tmp:
        root = Path(tmp) / "command-center"
        populate_ledger(root, events=sample_events(), receipts=sample_receipts())
        a = sl.render_markdown(root)
        b = sl.render_markdown(root)
        if a != b:
            print("FAILED:CC-0013-probe1 two renders over unchanged inputs differed")
            return 1
        ok, msgs = sl.check_status(root)
        if not ok:
            print("FAILED:CC-0013-probe1 regenerate was not silent")
            print("\n".join(msgs))
            return 1

        path = sl.status_path(root)
        original = path.read_text(encoding="utf-8")
        tampered = original.replace("| `event_records` | 3 |", "| `event_records` | 99 |")
        if tampered == original:
            print("FAILED:CC-0013-probe1 could not locate event_records counter to edit")
            return 1
        path.write_text(tampered, encoding="utf-8", newline="\n")
        ok, msgs = sl.check_status(root)
        if ok:
            print("FAILED:CC-0013-probe1 gate silent after hand-edit")
            return 1
        named = "\n".join(msgs)
        if "event_records" not in named or "99" not in named:
            print("FAILED:CC-0013-probe1 gate did not name the drifted counter")
            print(named)
            return 1
        if "line " not in named:
            print("FAILED:CC-0013-probe1 gate did not name a line number")
            print(named)
            return 1

        sl.write_status(root)
        ok, msgs = sl.check_status(root)
        if not ok:
            print("FAILED:CC-0013-probe1 gate still firing after regenerate")
            print("\n".join(msgs))
            return 1

    print(json_summary(named))
    print("SUCCESS:CC-0013-probe1 hand-edit named, regenerate silent, determinism holds")
    return 0


def json_summary(drift_msg: str) -> str:
    import json

    return json.dumps(
        {
            "probe": "probe1-handedit-determinism",
            "unit_id": "CC-0013",
            "pass": True,
            "gate_named_drifted_line": True,
            "drift_excerpt": drift_msg.splitlines()[0],
            "regenerate_silent": True,
            "two_renders_identical": True,
        },
        sort_keys=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
