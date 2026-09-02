"""Probe 1: both-states internal anchors via git cat-file (signal a).

A resolvable fixture anchor must pass; the same path off-by-1000 lines
must be reported. A shape-only checker is shown to miss the off-by-1000.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import both_states_internal  # noqa: E402

ART = REPO / "command-center/receipts/TST-0255.json"
UNIT = "TST-0255"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0255-probe1 {msg}")
    return 1


def check_artifact() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0255" not in text:
        return "artifact sentinel absent"
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"artifact self-declared {st}"
    return None


def main() -> int:
    err = check_artifact()
    if err:
        return fail(err)

    live = both_states_internal()
    print(json.dumps({k: live[k] for k in live if k not in {"good", "off_by_1000", "missing"}}, sort_keys=True))
    print(
        f"good={live['good']['classification']} off_by_1000={live['off_by_1000']['classification']} "
        f"missing={live['missing']['classification']} "
        f"shape_only_accepts_off_by_1000={live['shape_only_accepts_off_by_1000']}"
    )
    if not live["silent_on_good"]:
        return fail("good fixture anchor was not OK via git cat-file")
    if not live["fired_on_off_by_1000"]:
        return fail("off-by-1000 anchor was not reported BEYOND-EOF")
    if not live["fired_on_missing"]:
        return fail("missing-path anchor was not reported MISSING")
    if not live["blob_text_ok"]:
        return fail("blob line text mismatch")
    if live["shape_only_accepts_off_by_1000"] is not True:
        return fail("shape-only negative control did not accept the bad shape")
    if not live["shape_only_misses_off_by_1000"]:
        return fail("shape-only control did not miss off-by-1000")
    if not live["pass"]:
        return fail("both-states control did not pass")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        rec = (doc.get("both_states") or {})
        if rec.get("fired_on_off_by_1000") is not True:
            return fail("artifact both_states.fired_on_off_by_1000 drift")
        if rec.get("silent_on_good") is not True:
            return fail("artifact both_states.silent_on_good drift")
        if rec.get("pass") is not True:
            return fail("artifact both_states.pass drift")
        tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
        row = tests.get("both-states-off-by-1000")
        if not row or row.get("result") != "PASS":
            return fail("artifact test both-states-off-by-1000 not PASS")

    print("SUCCESS:TST-0255-probe1 both-states git cat-file off-by-1000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
