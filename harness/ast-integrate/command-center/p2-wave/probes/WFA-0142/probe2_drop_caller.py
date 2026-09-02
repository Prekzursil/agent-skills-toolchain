#!/usr/bin/env python3
"""Named probe 2: both-states refusal of a rollback that would drop a caller.

Good state: after a clean supersession, rollback succeeds and serving bytes match.
Bad state: a caller registered only on the replacement is named and the rollback
is refused; a mutant that sets allow_drop_callers=True would drop that caller.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    NEW_CALLER_ID,
    rehearse_drop_caller_refusal,
)

ART = REPO / "command-center/foundry/WFA-0142-supersession-engine-with-migration-and-rollback-to-s.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0142-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0142" not in text:
        return fail("sentinel-absent")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact unparseable:{exc}")

    report = rehearse_drop_caller_refusal()
    if not report.pass_:
        print(json.dumps(report.as_dict(), sort_keys=True))
        return fail(f"refusal {report.reason}")
    if not report.good_rollback_ok or not report.good_byte_equal:
        return fail("good-state rollback did not restore bytes")
    if report.bad_rollback_ok:
        return fail("bad-state rollback was allowed")
    if NEW_CALLER_ID not in report.dropped_named:
        return fail(f"refused without naming {NEW_CALLER_ID}")
    if not report.mutant_dropped:
        return fail("mutant allow_drop_callers did not drop the new caller")
    if not report.both_states:
        return fail("both-states collapsed")
    if report.good_rollback_ok == report.bad_rollback_ok:
        return fail("good and bad rollback verdicts are not distinct")

    rec = (doc.get("rehearsal") or {}).get("drop_caller_refusal") or {}
    if rec.get("dropped_named") != report.dropped_named:
        return fail("artifact dropped_named stale vs live")
    if rec.get("bad_reason") != report.bad_reason:
        return fail("artifact bad_reason stale vs live")

    summary = {
        "probe": "probe2-drop-caller-refusal-both-states",
        "unit_id": "WFA-0142",
        "pass": True,
        "good": {
            "rollback_ok": report.good_rollback_ok,
            "byte_equal": report.good_byte_equal,
        },
        "bad": {
            "rollback_ok": report.bad_rollback_ok,
            "reason": report.bad_reason,
            "dropped_named": report.dropped_named,
        },
        "mutant_dropped": report.mutant_dropped,
        "both_states": True,
        "anchors": report.anchors,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"good_ok={report.good_rollback_ok} bad_ok={report.bad_rollback_ok} "
        f"dropped={report.dropped_named} mutant_dropped={report.mutant_dropped}"
    )
    print("SUCCESS:WFA-0142-probe2 drop-caller rollback REFUSED (both-states)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
