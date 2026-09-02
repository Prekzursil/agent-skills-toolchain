#!/usr/bin/env python3
"""Probe 2: empty-log control + independent-field hand-edit + unqueried refusal.

A different reviewer than probe 1: tamper `receipts_total`, not `event_records`.
Zero events => NOT-STARTED, never GREEN, even if receipts claim SUCCESS.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scenario import TOOLS, populate_ledger  # noqa: E402

sys.path.insert(0, str(TOOLS))
import status_ledger as sl  # noqa: E402


def program_token(text: str) -> str:
    marker = "## Program status"
    if marker not in text:
        return ""
    block = text.split(marker, 1)[1].split("## ", 1)[0]
    for line in block.splitlines():
        line = line.strip()
        if line.startswith("`") and line.endswith("`") and len(line) > 2:
            return line.strip("`")
    return ""


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cc-0013-p2-") as tmp:
        empty = Path(tmp) / "empty"
        # Missing events file, but a SUCCESS receipt exists.
        (empty / "receipts").mkdir(parents=True)
        (empty / "receipts" / "claimed.json").write_text(
            json.dumps({"unit_id": "R-CLAIM", "state": "SUCCESS"}) + "\n",
            encoding="utf-8",
        )
        text_missing = sl.render_markdown(empty)
        if program_token(text_missing) != "NOT-STARTED":
            print(
                "FAILED:CC-0013-probe2 missing events did not yield NOT-STARTED; "
                f"got {program_token(text_missing)!r}"
            )
            return 1
        if program_token(text_missing) in sl.FORBIDDEN_PROGRAM_STATUS:
            print("FAILED:CC-0013-probe2 empty log produced a green program status")
            return 1

        blank = Path(tmp) / "blank"
        populate_ledger(
            blank,
            events=[],
            receipts={"claimed.json": {"unit_id": "R-CLAIM", "state": "SUCCESS"}},
        )
        text_blank = sl.render_markdown(blank)
        if program_token(text_blank) != "NOT-STARTED":
            print(
                "FAILED:CC-0013-probe2 empty events file did not yield NOT-STARTED; "
                f"got {program_token(text_blank)!r}"
            )
            return 1
        if text_blank != sl.render_markdown(blank):
            print("FAILED:CC-0013-probe2 empty render was not deterministic")
            return 1

        # Independent reviewer: edit receipts_total, a different field than probe 1.
        live = Path(tmp) / "live"
        populate_ledger(
            live,
            events=[{"id": "R-Z", "ts": "2026-08-24T09:00:00Z", "verb": "open"}],
            receipts={
                "A.json": {"unit_id": "A", "state": "SUCCESS"},
                "B.json": {"unit_id": "B", "state": "BLOCKED"},
            },
        )
        path = sl.status_path(live)
        original = path.read_text(encoding="utf-8")
        tampered = original.replace("| `receipts_total` | 2 |", "| `receipts_total` | 7 |")
        if tampered == original:
            print("FAILED:CC-0013-probe2 could not locate receipts_total to edit")
            return 1
        path.write_text(tampered, encoding="utf-8", newline="\n")
        ok, msgs = sl.check_status(live)
        if ok:
            print("FAILED:CC-0013-probe2 gate silent after independent-field hand-edit")
            return 1
        named = "\n".join(msgs)
        if "receipts_total" not in named or "7" not in named:
            print("FAILED:CC-0013-probe2 gate did not name receipts_total")
            print(named)
            return 1

        refused = False
        try:
            sl.add_metric([], "invented_count", 12, "   ")
        except sl.UnqueriedNumber:
            refused = True
        if not refused:
            print("FAILED:CC-0013-probe2 generator accepted an unqueried number")
            return 1

    print(
        json.dumps(
            {
                "probe": "probe2-empty-and-reviewer",
                "unit_id": "CC-0013",
                "pass": True,
                "empty_log_status": "NOT-STARTED",
                "green_on_empty": False,
                "independent_field_edited": "receipts_total",
                "gate_named_independent_field": True,
                "unqueried_number_refused": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CC-0013-probe2 empty-log NOT-STARTED; independent field named; unqueried refused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
