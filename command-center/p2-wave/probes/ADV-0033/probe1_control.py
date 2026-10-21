#!/usr/bin/env python3
"""Named probe 1: identical payload matrix + unisolated control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

ART = L.REPO / L.OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0033-probe1 {msg}")
    return 1


def main() -> int:
    m = L.measure()
    report = L.probe1_report(m)
    print(report, end="")
    if not m["control_unisolated_all_four"]:
        return fail("unisolated local case did not succeed at all four actions")
    iso = m["matrix"]["cells"]["linux-user-namespace-isolator"]
    if iso["executed"] and not m["isolator_detects_block"]:
        return fail("isolator ran but did not block any action")
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
    sentinel = L.catalog_sentinel()
    if sentinel not in text:
        return fail("sentinel-absent")
    if L.PROBE1_NAME not in text:
        return fail("probe1-name-absent")
    raw = ""
    for item in doc.get("named_probes") or []:
        if isinstance(item, dict) and item.get("id") == "probe1":
            raw = str(item.get("raw_output") or "")
    if raw != report:
        return fail("named-probe1-raw-mismatch")
    live = {t["target_id"]: t["verdict"] for t in m["targets"]}
    art = {}
    for t in doc.get("targets") or []:
        if not isinstance(t, dict):
            continue
        tid = t.get("target_id")
        v = t.get("verdict")
        if tid in art:
            return fail(f"duplicate-target:{tid}")
        if v not in L.LEGAL:
            return fail(f"illegal-verdict:{tid}={v}")
        art[tid] = v
    if live != art:
        return fail("target-verdict-drift")
    local = m["matrix"]["cells"]["local-process"]
    if local["verdict"] != "REFUTED":
        return fail("local-process-isolation-not-refuted")
    tests = doc.get("tests") or []
    needed = {"T-CONTROL-UNISOLATED", "T-PROBE-1-MATRIX"}
    have = {t.get("id") for t in tests if isinstance(t, dict)}
    if not needed <= have:
        return fail("control-test-missing")
    for t in tests:
        if isinstance(t, dict) and t.get("id") == "T-CONTROL-UNISOLATED":
            if t.get("result") != "PASS":
                return fail("control-test-not-pass")
    print("SUCCESS:ADV-0033-probe1 identical-payload-matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
