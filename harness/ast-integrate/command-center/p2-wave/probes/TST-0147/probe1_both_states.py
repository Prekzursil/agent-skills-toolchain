#!/usr/bin/env python3
"""Probe 1 (signal a): live condition 6 both-states on a fixture worktree.

A resolvable file:line must PASS condition 6; the same path off-by-1000
and a missing path must FALSE. Does not invoke git cat-file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import OUT_REL, SENTINEL, UNIT, measure_condition6  # noqa: E402

ART = REPO / OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def check_artifact() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
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

    live = measure_condition6()
    slim = {k: live[k] for k in live if k not in {"good", "off_by_1000", "missing"}}
    print(json.dumps(slim, sort_keys=True))
    print(
        f"good={live['good']['outcome']} off_by_1000={live['off_by_1000']['outcome']} "
        f"missing={live['missing']['outcome']}"
    )
    if not live["silent_on_good"]:
        return fail("resolvable file:line did not PASS condition 6")
    if not live["fired_on_off_by_1000"]:
        return fail("off-by-1000 file:line did not FALSE condition 6")
    if not live["fired_on_missing"]:
        return fail("missing-path file:line did not FALSE condition 6")
    if not live["pass"]:
        return fail("both-states control did not pass")
    if "BEYOND-EOF" not in str(live["off_by_1000"].get("basis") or ""):
        return fail("off-by-1000 basis did not name BEYOND-EOF")
    if "MISSING" not in str(live["missing"].get("basis") or ""):
        return fail("missing-path basis did not name MISSING")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        rec = doc.get("both_states") or {}
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

    print(f"SUCCESS:{UNIT}-probe1 both-states condition-6 off-by-1000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
