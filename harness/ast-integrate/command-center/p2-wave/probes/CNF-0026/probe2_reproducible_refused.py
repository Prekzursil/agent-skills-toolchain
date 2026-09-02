#!/usr/bin/env python3
"""Probe 2: a reproducible failure must not be accepted into the file."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ingest as I  # noqa: E402

REPO = I.REPO
ART = REPO / "command-center/confirmation/CNF-0026-impossibility-records.json"


def planted_record() -> dict:
    obs = I.control_detector_observation(REPO)
    return {
        "failure_id": "IMP-PLANTED-CRLF-CONTROL",
        "title": "Planted CRLF fixture that is live-reproducible on this worktree",
        "source_units": ["CNF-0026"],
        "reproduction_status": "PREREQUISITE-MISSING",
        "missing_prerequisite": "none — control is reproducible",
        "substrates_attempted": ["linux-worktree"],
        "attempts": [
            {
                "substrate": "linux-worktree",
                "action": "byte-scan planted fixture",
                "result": obs,
            }
        ],
        "signals": [
            {
                "id": "S1",
                "channel": "byte-scan",
                "method": "read_bytes count of CRLF pairs",
                "observation": obs,
            },
            {
                "id": "S2",
                "channel": "path-stat",
                "method": "Path.is_file on planted fixture",
                "observation": f"{I.CONTROL_REL} is_file=True",
            },
        ],
        "settling_experiment": {
            "name": "control-must-be-refused",
            "command": (
                "python3 -B command-center/p2-wave/probes/CNF-0026/"
                "probe2_reproducible_refused.py"
            ),
            "expected_observation": "ingest raises Refuse reproducible-control",
            "discriminating_outcome": "acceptance means the gate is dead",
        },
        "blocks_phase15_gate": False,
        "failure_class": "crlf-artefact",
        "subject_path": I.CONTROL_REL,
        "phase15_gate_notes": "control record must never enter the live file",
    }


def main() -> int:
    path = REPO / I.CONTROL_REL
    if not I.crlf_present(path):
        print("FAILED:CNF-0026-probe2 control fixture did not fire")
        print(I.control_detector_observation(REPO))
        return 1
    print("control_detector_fired=True", I.control_detector_observation(REPO))

    rec = planted_record()
    try:
        I.accept_record(rec, REPO)
    except I.Refuse as exc:
        print(f"ingest_refused code={exc.code}")
        if exc.code != "reproducible-control":
            print("FAILED:CNF-0026-probe2 refused for the wrong reason")
            return 1
    else:
        print("FAILED:CNF-0026-probe2 reproducible control was accepted")
        return 1

    reproduced = dict(rec)
    reproduced["failure_id"] = "IMP-SHOULD-STILL-FAIL"
    reproduced["reproduction_status"] = "REPRODUCED"
    try:
        I.accept_record(reproduced, REPO)
        print("FAILED:CNF-0026-probe2 REPRODUCED status was accepted")
        return 1
    except (I.Refuse, Exception) as exc:
        print(f"reproduced_status_refused type={type(exc).__name__}")

    if not ART.is_file():
        print("FAILED:CNF-0026-probe2 live artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    I.accept_artifact(doc, REPO)
    ids = [r["failure_id"] for r in doc["records"]]
    banned = {I.CONTROL_ID, "IMP-PLANTED-CRLF-CONTROL"}
    leaked = banned.intersection(ids)
    if leaked:
        print("FAILED:CNF-0026-probe2 control leaked into live records", leaked)
        return 1
    ctrl = doc.get("reproducible_control") or {}
    if ctrl.get("refused") is not True:
        print("FAILED:CNF-0026-probe2 artifact did not record refusal")
        return 1
    print(
        f"live_excluded={not leaked} "
        f"artifact_refused={ctrl.get('refused')} "
        f"reason={ctrl.get('reason')}"
    )
    print("SUCCESS:CNF-0026-probe2 reproducible control refused entry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
