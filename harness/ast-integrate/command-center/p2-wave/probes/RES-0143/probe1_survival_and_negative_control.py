#!/usr/bin/env python3
"""Probe 1: 30-anecdote survival is computed live; 5 vague controls refuse.

A protocol that transforms 100% of the sample, or that emits a claim for a
vague negative control, is fabricating.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from measure import measure  # noqa: E402

UNIT = "RES-0143"
ART = REPO / "command-center/research/sources-frontier/RES-0143-anecdote-to-falsifiable-claim-protocol.json"
SENTINEL = "SUCCESS:RES-0143"


def main() -> int:
    m = measure()
    neg = m["negative_controls"]
    payload = {
        "probe": "probe1-survival-and-negative-control",
        "unit_id": UNIT,
        "n_sample": m["n_sample"],
        "n_survived": m["n_survived"],
        "n_refused": m["n_refused"],
        "survival_fraction": m["survival_fraction"],
        "survival_not_100_percent": m["survival_not_100_percent"],
        "negative_n": neg["n"],
        "negative_all_not_transformable": neg["all_not_transformable"],
        "negative_dispositions": neg["dispositions"],
        "pin_ok": m["pin_ok"],
        "audit_ok": m["audit_ok"],
        "mismatches": m["mismatches"],
        "audit_fail": m["audit_fail"],
        "survived_ids": m["survived_ids"],
        "refused_ids": m["refused_ids"],
        "pass": False,
    }
    artifact_ok = True
    artifact_notes = []
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        text = ART.read_text(encoding="utf-8")
        if SENTINEL not in text:
            artifact_ok = False
            artifact_notes.append("sentinel-absent")
        measured = (doc.get("sample_measurement") or {}).get("survival_fraction")
        if measured is not None and abs(float(measured) - float(m["survival_fraction"])) > 1e-9:
            artifact_ok = False
            artifact_notes.append("artifact-fraction-mismatch")
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            artifact_ok = False
            artifact_notes.append("artifact-self-declared-not-delivering")
    payload["artifact_ok"] = artifact_ok
    payload["artifact_notes"] = artifact_notes
    payload["pass"] = bool(
        m["n_sample"] == 30
        and m["n_survived"] >= 1
        and m["survival_not_100_percent"]
        and neg["n"] == 5
        and neg["all_not_transformable"]
        and m["pin_ok"]
        and m["audit_ok"]
        and artifact_ok
        and m["n_survived"] == m["expected_transformable"]
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:RES-0143-probe1 survival/negative-control")
        return 1
    print(
        f"SUCCESS:RES-0143-probe1 survived={m['n_survived']}/30 "
        f"fraction={m['survival_fraction']:.3f}; 5/5 vague controls NOT-TRANSFORMABLE"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
