#!/usr/bin/env python3
"""Named probe 1: canonical-mechanism clustering. Recomputes live; checks the artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit_common as C  # noqa: E402

ART = C.REPO / C.OUTPUT_REL
LEGAL = C.LEGAL


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0114-probe1 {msg}")
    return 1


def main() -> int:
    m = C.measure()
    report = C.probe1_report(m)
    print(report, end="")
    ctrl = m["controls"]
    if not ctrl["reword_collapsed"]:
        return fail("planted reworded duplicate did not collapse")
    if not ctrl["neighbour_separated"]:
        return fail("planted near-neighbour was not kept distinct")
    if not ctrl["both_ok"]:
        return fail("planted-control-calibration")
    if m["probe1"]["raw"] != m["counts"]["live"]:
        return fail("raw-count-mismatch")
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
    if C.catalog_sentinel() not in text:
        return fail("sentinel-absent")
    if C.PROBE1_NAME not in text:
        return fail("probe1-name-absent")
    raw = ""
    for p in doc.get("named_probes") or []:
        if isinstance(p, dict) and p.get("id") == "probe1":
            raw = str(p.get("raw_output") or "")
    if raw != report:
        return fail("named-probe1-raw-mismatch")
    live_ids = {t["target_id"]: t["verdict"] for t in m["targets"]}
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
    art_p1 = doc.get("probe1") or {}
    if int(art_p1.get("raw") or -1) != int(m["probe1"]["raw"]):
        return fail("artifact-raw-drift")
    if int(art_p1.get("collapsed") or -1) != int(m["probe1"]["collapsed"]):
        return fail("artifact-collapsed-drift")
    if abs(float(art_p1.get("ratio") or -1) - float(m["probe1"]["ratio"])) > 1e-9:
        return fail("artifact-ratio-drift")
    print("SUCCESS:ADV-0114-probe1 canonical-clusters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
