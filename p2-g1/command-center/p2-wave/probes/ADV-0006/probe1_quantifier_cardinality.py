#!/usr/bin/env python3
"""Probe 1: mechanical quantifier vs evidence-cardinality arithmetic."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

ART = A.REPO / A.OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0006-probe1 {msg}")
    return 1


def main() -> int:
    meas = A.measure()
    report = A.probe1_payload(meas)
    print(report)
    if not meas["scoped_ok"]:
        return fail("three correctly-scoped controls were not left CONFIRMED")
    if not meas["overclaim_plants_ok"]:
        return fail("planted overclaims were not flagged")
    if not meas["controls_ok"]:
        return fail("calibration controls did not discriminate")
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
    sentinel = A.catalog_sentinel()
    if sentinel not in text:
        return fail("sentinel-absent")
    raw = ""
    for probe in doc.get("named_probes") or []:
        if isinstance(probe, dict) and probe.get("id") == "probe1":
            raw = str(probe.get("raw_output") or "")
    if raw != report:
        return fail("named-probe1-raw-mismatch")
    live = {row["target_id"]: row["verdict"] for row in meas["rows"]}
    art: dict[str, str] = {}
    for target in doc.get("targets") or []:
        if not isinstance(target, dict):
            continue
        tid = str(target.get("target_id") or "")
        verdict = str(target.get("verdict") or "")
        if tid in art:
            return fail(f"duplicate-target:{tid}")
        if verdict not in A.LEGAL:
            return fail(f"illegal-verdict:{tid}={verdict}")
        art[tid] = verdict
    if live != art:
        return fail("target-verdict-drift")
    if str(doc.get("overall_verdict")) != meas["overall_verdict"]:
        return fail("overall-verdict-drift")
    print("SUCCESS:ADV-0006-probe1 quantifier-cardinality")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
