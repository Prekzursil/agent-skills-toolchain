#!/usr/bin/env python3
"""Probe 2: the matrix can show a red cell (known-failing transport control).

Both-states in one process: Write tool stays silent on a dollar/backtick
payload; expanding heredoc and double-quoted -c fire; bash here-string adds a
newline. A harness that is green on every cell measures nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from matrix import red_cell_control, run_matrix  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0060.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0060-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"receipt unparseable {exc}")
    if not isinstance(doc, dict):
        return fail("receipt not an object")
    if doc.get("unit_id") != "TST-0060":
        return fail(f"unit_id {doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    if "SUCCESS:TST-0060" not in text:
        return fail("sentinel absent")

    ctrl = red_cell_control()
    print(json.dumps(ctrl, sort_keys=True))
    if not ctrl["silent_on_write_tool"]:
        return fail("write_tool was not silent on the dollar payload (oracle broken)")
    if not ctrl["fired_on_double_quoted_c"]:
        return fail("double-quoted -c did not go red on $HOME expansion")
    if not ctrl["fired_on_expanding_heredoc"]:
        return fail("expanding heredoc did not go red on $HOME expansion")
    if not ctrl["fired_on_here_string_extra_nl"]:
        return fail("here-string did not go red (expected extra trailing newline)")
    if not ctrl["pass"]:
        return fail("red-cell control did not hold")

    full = run_matrix()
    by = full["by_transport"]
    write = by.get("write_tool") or {}
    here = by.get("here_string") or {}
    naive = by.get("c_inline_double_quoted") or {}
    if write.get("n", 0) < 40:
        return fail(f"write_tool n={write.get('n')} < 40")
    if here.get("n", 0) < 59:
        return fail(f"here_string n={here.get('n')} < 59")
    if write.get("n_unequal", 1) != 0:
        return fail(f"write_tool had unexpected failures {write}")
    if here.get("n_unequal", 0) < 1:
        return fail("here_string produced no red cells")
    if naive.get("n_unequal", 0) < 1:
        return fail("known-failing double-quoted -c produced no red cells")
    if full["red_count"] < 1:
        return fail("full matrix has zero red cells; harness cannot show a failure")

    recorded = (doc.get("matrix") or {}).get("by_transport") or {}
    rec_here = recorded.get("here_string") or {}
    if rec_here.get("n_unequal", 0) < 1:
        return fail("receipt here_string has no red cells")
    rec_naive = recorded.get("c_inline_double_quoted") or {}
    if rec_naive.get("n_unequal", 0) < 1:
        return fail("receipt missing known-failing transport red cells")

    tests = doc.get("tests") or []
    t2 = next((t for t in tests if t.get("id") == "test_the_matrix_records_a_known_failing_transport"), None)
    if not t2 or t2.get("verdict") != "PASS":
        return fail("receipt did not record the red-cell test as PASS")

    print(
        f"write_tool {write['n_equal']}/{write['n']} equal; "
        f"here_string fail {here['n_unequal']}/{here['n']} "
        f"({here['failure_rate_pct']}%); "
        f"naive_c red {naive['n_unequal']}/{naive['n']}; "
        f"matrix_red={full['red_count']}"
    )
    print("SUCCESS:TST-0060-probe2 matrix records a known failing transport")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
