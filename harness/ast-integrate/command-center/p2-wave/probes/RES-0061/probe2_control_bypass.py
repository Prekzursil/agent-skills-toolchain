#!/usr/bin/env python3
"""Probe 2: reviewer re-runs clean-tree control and mitigation bypasses.

Does not treat probe 1's conclusion as evidence. Re-executes the experiment
and requires: clean tree silent, decoy isolated, at least one mitigation
held, at least one bypassed, program hook detector fires only on planted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import surface as S  # noqa: E402

ART = REPO / "command-center/research/RES-0061.json"


def main() -> int:
    exp = S.run_experiment()
    by_id = {m["id"]: m for m in exp["mitigations"]}
    checks = [
        ("clean silent", exp["no_client_ingested_on_clean"] is True),
        ("planted ingest", exp["all_clients_ingested_on_planted"] is True),
        ("decoy isolated planted", exp["decoy_in_instruction_buffer_planted"] is False),
        ("decoy isolated clean", exp["decoy_in_instruction_buffer_clean"] is False),
        ("signals agree", exp["signals_agree"] is True),
        ("detector fires planted", exp["program_detector_planted"]["fired"] is True),
        ("detector silent clean", exp["program_detector_clean"]["fired"] is False),
        ("one mitigation held", exp["one_mitigation_held"] is True),
        ("one mitigation bypassed", exp["one_mitigation_bypassed"] is True),
        ("M4 held", by_id["M4-hash-pinned-allowlist"]["survived"] is True),
        ("M1 bypassed", by_id["M1-declared-permission-manifest"]["survived"] is False),
        ("M2 bypassed", by_id["M2-strip-dot-client-dirs-only"]["survived"] is False),
        ("M3 bypassed", by_id["M3-data-not-instructions-preamble"]["survived"] is False),
    ]
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:RES-0061-probe2 {name}")
            return 1
    if not ART.is_file():
        print("FAILED:RES-0061-probe2 research artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS":
        print("FAILED:RES-0061-probe2 reviewer verdict not PASS")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:RES-0061-probe2 self-declared {doc.get('state')}")
        return 1
    print("SUCCESS:RES-0061-probe2 clean-tree control and mitigation bypasses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
