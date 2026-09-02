#!/usr/bin/env python3
"""Named probe 1: input-set overlap. Recomputes Jaccard live; checks the artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import independence as I  # noqa: E402

ART = I.REPO / I.OUTPUT_REL
LEGAL = I.LEGAL


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0105-probe1 {msg}")
    return 1


def main() -> int:
    m = I.measure()
    report = I.probe1_report(m)
    print(report, end="")
    if not m["controls"]["distinct_ok"]:
        return fail("distinct-input control did not calibrate overlap")
    if not m["controls"]["mutant_ok"]:
        return fail("shared-mutant did not collapse overlap")
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
    sentinel = I.catalog_sentinel()
    if sentinel not in text:
        return fail("sentinel-absent")
    if I.PROBE1_NAME not in text:
        return fail("probe1-name-absent")
    raw = ""
    for p in doc.get("named_probes") or []:
        if isinstance(p, dict) and p.get("id") == "probe1":
            raw = str(p.get("raw_output") or "")
    if raw != report:
        return fail("named-probe1-raw-mismatch")
    live_ids = {e["event_id"]: e["verdict"] for e in m["events"]}
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
    if live_ids != art_ids:
        return fail("target-verdict-drift")
    dj = (doc.get("controls") or {}).get("distinct_jaccard")
    if abs(float(dj) - float(m["controls"]["distinct_jaccard"])) > 1e-9:
        return fail("artifact-distinct-jaccard-drift")
    print("SUCCESS:ADV-0105-probe1 input-overlap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
