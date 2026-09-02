#!/usr/bin/env python3
"""Named probe 1: overlapping agents + git diff --cached oracle."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import race as R  # noqa: E402

ART = R.REPO / R.OUTPUT_REL
LEGAL = R.LEGAL


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0123-probe1 {msg}")
    return 1


def main() -> int:
    m = R.measure()
    report = R.probe1_report(m)
    print(report, end="")
    ctrl = m["controls"]
    if not ctrl["disjoint_ok"]:
        return fail("disjoint scoped-add control leaked sibling files")
    if not ctrl["planted_ok"]:
        return fail("planted sibling not visible after git add -A")
    if not ctrl["scratch_ok"]:
        return fail("scratch-tree invariant failed")
    if not m["probe1"]["overlap"]["swept_sibling"]:
        return fail("broad add did not sweep sibling; oracle is not live")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return fail("artifact-unparseable")
    if not isinstance(doc, dict):
        return fail("artifact-not-object")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    sentinel = R.catalog_sentinel()
    if sentinel not in text:
        return fail("sentinel-absent")
    if R.PROBE1_NAME not in text:
        return fail("probe1-name-absent")
    errs = R.schema_errors(doc)
    if errs:
        return fail(f"schema:{errs[0]}")
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    if not R.schema_errors(garbage):
        return fail("schema-vacuous-garbage")
    raw = ""
    for p in doc.get("named_probes") or []:
        if isinstance(p, dict) and p.get("id") == "probe1":
            raw = str(p.get("raw_output") or "")
    if raw != report:
        return fail("named-probe1-raw-mismatch")
    live = {t["target_id"]: t["verdict"] for t in m["targets"]}
    art_ids = {}
    for t in doc.get("targets") or []:
        if not isinstance(t, dict):
            continue
        tid = t.get("target_id")
        v = t.get("verdict")
        if tid in art_ids:
            return fail(f"duplicate-target:{tid}")
        if v not in LEGAL:
            return fail(f"illegal-verdict:{tid}={v}")
        art_ids[tid] = v
    if live != art_ids:
        return fail("target-verdict-drift")
    if live.get("TARGET-BROAD-STAGE-SWEEPS-SIBLING") != "CONFIRMED":
        return fail("sweep-target-not-confirmed")
    if live.get("TARGET-DISJOINT-SCOPED-ADD-ISOLATION") != "CONFIRMED":
        return fail("isolation-target-not-confirmed")
    art_cached = ((doc.get("probe1") or {}).get("overlap") or {}).get("cached")
    if art_cached != m["probe1"]["overlap"]["cached"]:
        return fail("artifact-cached-drift")
    print("SUCCESS:ADV-0123-probe1 index-overlap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
