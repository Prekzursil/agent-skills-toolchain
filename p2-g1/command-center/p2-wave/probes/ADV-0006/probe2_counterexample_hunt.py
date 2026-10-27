#!/usr/bin/env python3
"""Probe 2: hunt one counterexample outside the cited evidence set."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

ART = A.REPO / A.OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0006-probe2 {msg}")
    return 1


def main() -> int:
    meas = A.measure()
    report = A.probe2_payload(meas)
    print(report)
    if meas["probe2_hits"] < 1:
        return fail("no-outside-cited-set-counterexample")
    if not meas["mutant_fires"]:
        return fail("widened-scoped-mutant-silent")
    if not meas["scoped_ok"]:
        return fail("scoped-controls-not-silent")
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
    if A.catalog_sentinel() not in text:
        return fail("sentinel-absent")
    raw = ""
    for probe in doc.get("named_probes") or []:
        if isinstance(probe, dict) and probe.get("id") == "probe2":
            raw = str(probe.get("raw_output") or "")
    if raw != report:
        return fail("named-probe2-raw-mismatch")
    reviewer = doc.get("reviewer") or {}
    if not isinstance(reviewer, dict) or reviewer.get("independent") is not True:
        return fail("reviewer-not-independent")
    live = {row["target_id"]: row["verdict"] for row in meas["rows"]}
    art = {
        str(t.get("target_id")): str(t.get("verdict"))
        for t in (doc.get("targets") or [])
        if isinstance(t, dict)
    }
    if live != art:
        return fail("target-verdict-drift")
    hits = [
        row
        for row in meas["rows"]
        if row.get("counterexample") and row["verdict"] == "REFUTED"
    ]
    print(
        f"probe2_hits={len(hits)} mutant={meas['mutant']['verdict']} "
        f"overall={meas['overall_verdict']}"
    )
    print("SUCCESS:ADV-0006-probe2 counterexample-hunt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
