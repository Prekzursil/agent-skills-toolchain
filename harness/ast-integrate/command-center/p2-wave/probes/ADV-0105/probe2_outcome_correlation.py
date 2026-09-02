#!/usr/bin/env python3
"""Named probe 2: outcome-error correlation. Mechanically different from probe 1."""
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
    print(f"FAILED:ADV-0105-probe2 {msg}")
    return 1


def main() -> int:
    m = I.measure()
    report = I.probe2_report(m)
    print(report, end="")
    ctrl = m["controls"]
    if not ctrl["distinct_ok"]:
        return fail("distinct-input control did not calibrate correlation")
    if not ctrl["mutant_ok"]:
        return fail("shared-mutant correlation gate did not go red")
    if abs(float(ctrl["distinct_correlation"] or 0)) > I.CORR_DISTINCT_MAX:
        return fail("distinct-correlation-too-high")
    if abs(float(ctrl["mutant_correlation"] or 0)) < I.CORR_COLLAPSE:
        return fail("mutant-correlation-too-low")
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
    if I.catalog_sentinel() not in text:
        return fail("sentinel-absent")
    if I.PROBE2_NAME not in text:
        return fail("probe2-name-absent")
    raw = ""
    for p in doc.get("named_probes") or []:
        if isinstance(p, dict) and p.get("id") == "probe2":
            raw = str(p.get("raw_output") or "")
    if raw != report:
        return fail("named-probe2-raw-mismatch")
    live = {
        e["event_id"]: (e.get("correlation") or {}).get("correlation")
        for e in m["events"]
    }
    for t in doc.get("targets") or []:
        if not isinstance(t, dict):
            continue
        tid = t.get("target_id")
        if t.get("verdict") not in LEGAL:
            return fail(f"illegal-verdict:{tid}")
        if tid not in live:
            return fail(f"unknown-target:{tid}")
        art_c = t.get("correlation")
        live_c = live[tid]
        if art_c is None and live_c is None:
            continue
        if art_c is None or live_c is None:
            return fail(f"correlation-presence-drift:{tid}")
        if abs(float(art_c) - float(live_c)) > 1e-9:
            return fail(f"correlation-drift:{tid}")
    print("SUCCESS:ADV-0105-probe2 outcome-correlation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
