#!/usr/bin/env python3
"""Named probe 1: sandbox beacon install across lifecycle vectors."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lifecycle as L  # noqa: E402

ART = L.REPO / L.OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0060-probe1 {msg}")
    return 1


def main() -> int:
    m = L.measure()
    report = L.probe1_report(m)
    print(report, end="")
    c = m["controls"]
    if not c["detector_ok"]:
        return fail("direct beacon did not fire")
    if not c["implicit_ok"]:
        return fail("implicit install executed or wrote a beacon")
    if not c["naive_ok"]:
        return fail("naive host control did not write a beacon")
    if not c["gated_ok"]:
        return fail("owner-gated sandbox arm did not isolate the beacon")
    if not c["both_states"]:
        return fail("beacon presence is a constant; both-states failed")
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
    if L.PROBE1_NAME not in text:
        return fail("probe1-name-absent")
    raw = ""
    for p in doc.get("named_probes") or []:
        if isinstance(p, dict) and p.get("id") == "probe1":
            raw = str(p.get("raw_output") or "")
    if raw != report:
        return fail("named-probe1-raw-mismatch")
    live_ids = {t["id"]: t["verdict"] for t in L.targets_from(m)}
    art_ids = {}
    for t in doc.get("targets") or []:
        if not isinstance(t, dict):
            continue
        tid = t.get("id") or t.get("target_id")
        v = t.get("verdict")
        if tid in art_ids:
            return fail(f"duplicate-target:{tid}")
        if v not in L.LEGAL:
            return fail(f"illegal-verdict:{tid}={v}")
        art_ids[tid] = v
    if live_ids != art_ids:
        return fail("target-verdict-drift")
    print("SUCCESS:ADV-0060-probe1 beacon-install")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
