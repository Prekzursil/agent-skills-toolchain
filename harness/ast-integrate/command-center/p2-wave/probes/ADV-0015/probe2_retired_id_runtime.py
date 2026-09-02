#!/usr/bin/env python3
"""Named probe 2: retired-id runtime behaviour of the CNL-0004 cost router."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

ART = L.REPO / L.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0015-probe2 {msg}")
    return 1


def main() -> int:
    m = L.measure()
    report = L.probe2_report(m)
    print(report, end="")
    rt = m["runtime_controls"]
    if not rt["loud_ok"]:
        return fail("fail-loudly control classified as a defect")
    if not rt["silent_ok"]:
        return fail("silent-substitute of a working model was not a defect")
    if not m["runtime_over"].get("behaviour"):
        return fail("retired-id over-budget call produced no behaviour")
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
    if L.catalog_sentinel() not in text:
        return fail("sentinel-absent")
    if L.PROBE2_NAME not in text:
        return fail("probe2-name-absent")
    raw = ""
    for p in doc.get("named_probes") or []:
        if isinstance(p, dict) and p.get("id") == "probe2":
            raw = str(p.get("raw_output") or "")
    if raw != report:
        return fail("named-probe2-raw-mismatch")
    art_over = (doc.get("runtime") or {}).get("over_budget") or {}
    if art_over.get("behaviour") != m["runtime_over"].get("behaviour"):
        return fail("over-budget-behaviour-drift")
    if art_over.get("defect") != m["runtime_over"].get("defect"):
        return fail("over-budget-defect-drift")
    if bool(rt["silent"]["substitute_would_work"]) is not True:
        return fail("silent-sub control must keep substitute_would_work true")
    print("SUCCESS:ADV-0015-probe2 retired-id-runtime")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
