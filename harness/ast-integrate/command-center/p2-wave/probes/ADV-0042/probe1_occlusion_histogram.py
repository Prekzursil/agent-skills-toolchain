#!/usr/bin/env python3
"""Probe 1: occluding window + window-scoped flag + colour-histogram identity."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

ART = L.REPO / L.OUT_REL


def fail(msg: str, payload: dict | None = None) -> int:
    if payload is not None:
        print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"FAILED:ADV-0042-probe1 {msg}")
    return 1


def main() -> int:
    m = L.live_measurement()
    report = L.probe1_report(m)
    print(report, end="")
    cap = m["capture"]
    if not cap["no_occlusion_passes"]:
        return fail("no-occlusion control did not pass; histogram uncalibrated")
    if not cap["screen_scoped_leaks_under_occlusion"]:
        return fail("screen-scoped capture did not leak occluder under occlusion")
    if not cap["window_scoped_holds_under_occlusion"]:
        return fail("window-scoped capture did not keep the target under occlusion")
    if not cap["window_handle_holds_under_occlusion"]:
        return fail("take_screenshot(window_handle=) leaked the occluder")
    if not cap["mutant_fires"]:
        return fail("claimed-window-scoped copy-from-screen mutant was silent")
    if cap["personal_application_captured"]:
        return fail("a personal application was captured")
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
    if L.SENTINEL not in text:
        return fail("sentinel-absent")
    raw = ""
    for p in doc.get("named_probes") or []:
        if isinstance(p, dict) and p.get("id") == "probe1":
            raw = str(p.get("raw_output") or "")
    if raw != report:
        return fail("named-probe1-raw-mismatch")
    errs = L.validate_doc(doc)
    if errs:
        return fail("schema-invalid", {"errs": errs[:8]})
    garbage = {"unit_id": "ADV-0042", "state": "SUCCESS"}
    if not L.validate_doc(garbage):
        return fail("schema-vacuous-garbage")
    live_ids = {t["id"]: t["verdict"] for t in m["targets"]}
    art_ids = {}
    for t in doc.get("targets") or []:
        if not isinstance(t, dict):
            continue
        tid = t.get("id")
        v = t.get("verdict")
        if tid in art_ids:
            return fail(f"duplicate-target:{tid}")
        if v not in L.LEGAL:
            return fail(f"illegal-verdict:{tid}={v}")
        art_ids[tid] = v
    if live_ids != art_ids:
        return fail("target-verdict-drift", {"live": live_ids, "art": art_ids})
    hist = (doc.get("report") or {}).get("histogram") or {}
    if hist.get("no_occlusion_passes") is not True:
        return fail("artifact-no-occlusion-control-missing")
    if hist.get("calibrated") is not True:
        return fail("artifact-histogram-not-calibrated")
    print("SUCCESS:ADV-0042-probe1 occlusion-histogram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
