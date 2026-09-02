#!/usr/bin/env python3
"""Probe 1: planted one-tree vs both-tree detector + paths: load semantics.

Must classify a skill present in only one tree and a skill present in both
correctly BEFORE live totals are trusted. Absence of a paths: key is
ALWAYS-ON, not never-loaded.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = S.OUT


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0017-probe1 {msg}")
    return 1


def main() -> int:
    control = S.detector_control()
    load = S.load_controls()
    print(json.dumps({"detector_control": control, "load_semantics": load}, indent=2))
    if not control["passed"]:
        return fail(f"planted detector mismatches={control['mismatches']}")
    if not load["inversion_holds"]:
        return fail("load-semantics inversion failed")
    if not load["absence_means_always_on"]:
        return fail("missing paths: key was not ALWAYS-ON")
    if not load["paths_key_means_lazy"]:
        return fail("paths: key was not LAZY")
    if not load["never_loaded_rejected"]:
        return fail("parser invented a never-loaded state")
    if not load["instrument_agrees"]:
        return fail("YAML resolver and line-scan instrument disagree")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact absent")
    text = ART.read_text(encoding="utf-8")
    if S.SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    rec_ctrl = doc.get("detector_control") or {}
    if rec_ctrl.get("passed") is not True:
        return fail("artifact detector_control.passed is not true")
    rec_load = doc.get("load_semantics") or {}
    if rec_load.get("inversion_holds") is not True:
        return fail("artifact load inversion_holds is not true")
    if rec_load.get("absence_means_always_on") is not True:
        return fail("artifact did not record absence_means_always_on")
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in (
        "one-tree-vs-both-tree-detector",
        "paths-key-load-semantics",
        "registry-96-counting-rule",
    ):
        if (tests.get(tid) or {}).get("result") != "PASS":
            return fail(f"artifact test {tid} not PASS")
    print(
        "only-agents=agents_only only-claude=claude_only "
        "shared-identical=both+hash-equal shared-divergent=both+hash-divergent "
        "no-paths=ALWAYS-ON with-paths=LAZY"
    )
    print("SUCCESS:WFA-0017-probe1 detector-control and load-semantics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
