#!/usr/bin/env python3
"""Named probe 2: fix-level equivalence. Mechanically different from probe 1."""
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
    print(f"FAILED:ADV-0114-probe2 {msg}")
    return 1


def main() -> int:
    m = C.measure()
    report = C.probe2_report(m)
    print(report, end="")
    ctrl = m["controls"]
    if not ctrl["reword_collapsed"]:
        return fail("planted reworded duplicate did not share the seed fix cluster")
    if not ctrl["neighbour_separated"]:
        return fail("planted near-neighbour collapsed on fix-equivalence")
    if not ctrl["both_ok"]:
        return fail("planted-control-calibration")
    if ctrl["probe2_seed_key"] == ctrl["probe2_neighbour_key"]:
        return fail("fix-keys-not-independent-of-wording")
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
    if C.PROBE2_NAME not in text:
        return fail("probe2-name-absent")
    raw = ""
    for p in doc.get("named_probes") or []:
        if isinstance(p, dict) and p.get("id") == "probe2":
            raw = str(p.get("raw_output") or "")
    if raw != report:
        return fail("named-probe2-raw-mismatch")
    live = {t["target_id"]: t["verdict"] for t in m["targets"]}
    for t in doc.get("targets") or []:
        if not isinstance(t, dict):
            continue
        tid = t.get("target_id")
        if t.get("verdict") not in LEGAL:
            return fail(f"illegal-verdict:{tid}")
        if tid not in live:
            return fail(f"unknown-target:{tid}")
        if t.get("verdict") != live[tid]:
            return fail(f"verdict-drift:{tid}")
    art_p2 = doc.get("probe2") or {}
    if int(art_p2.get("raw") or -1) != int(m["probe2"]["raw"]):
        return fail("artifact-raw-drift")
    if int(art_p2.get("collapsed") or -1) != int(m["probe2"]["collapsed"]):
        return fail("artifact-collapsed-drift")
    if abs(float(art_p2.get("ratio") or -1) - float(m["probe2"]["ratio"])) > 1e-9:
        return fail("artifact-ratio-drift")
    print("SUCCESS:ADV-0114-probe2 fix-equivalence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
