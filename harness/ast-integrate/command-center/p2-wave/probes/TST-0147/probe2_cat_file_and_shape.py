#!/usr/bin/env python3
"""Probe 2 (signal b): git cat-file plus shape-only negative control.

Independent of probe 1: does not call evaluate() / _c6_evidence.
A checker that only regex-validates path:digits must accept off-by-1000
and therefore fail this unit's test.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import OUT_REL, SENTINEL, UNIT, measure_git_and_shape  # noqa: E402

ART = REPO / OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
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

    live = measure_git_and_shape()
    slim = {
        k: live[k]
        for k in live
        if k not in {"good", "off_by_1000", "missing"}
    }
    print(json.dumps(slim, sort_keys=True))
    print(
        f"git_good={live['good']['classification']} "
        f"git_off_by_1000={live['off_by_1000']['classification']} "
        f"git_missing={live['missing']['classification']} "
        f"shape_only_accepts_off_by_1000={live['shape_only_accepts_off_by_1000']}"
    )
    if live["good"]["classification"] != "OK":
        return fail("git cat-file good line was not OK")
    if live["off_by_1000"]["classification"] != "BEYOND-EOF":
        return fail("git cat-file off-by-1000 was not BEYOND-EOF")
    if live["missing"]["classification"] != "MISSING":
        return fail("git cat-file missing path was not MISSING")
    if not live["blob_text_ok"]:
        return fail("git cat-file blob line text mismatch")
    if live["shape_only_accepts_off_by_1000"] is not True:
        return fail("shape-only checker did not accept off-by-1000")
    if live["shape_only_accepts_missing"] is not True:
        return fail("shape-only checker did not accept missing path")
    if not live["shape_only_fails_this_test"]:
        return fail("shape-only negative control did not fail this test")
    if not live["pass"]:
        return fail("git/shape control did not pass")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        rec = doc.get("git_cat_file") or {}
        if rec.get("off_by_1000_classification") != "BEYOND-EOF":
            return fail("artifact git_cat_file.off_by_1000_classification drift")
        if rec.get("shape_only_accepts_off_by_1000") is not True:
            return fail("artifact shape_only_accepts_off_by_1000 drift")
        tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
        row = tests.get("negative-shape-only-anchor")
        if not row or row.get("result") != "PASS":
            return fail("artifact test negative-shape-only-anchor not PASS")

    print(f"SUCCESS:{UNIT}-probe2 git-cat-file and shape-only negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
