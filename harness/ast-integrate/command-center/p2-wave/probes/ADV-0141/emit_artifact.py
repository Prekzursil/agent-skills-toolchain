#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0141-scanner-coverage-algebra.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

REPO = L.REPO
OUT = REPO / L.OUT_REL


def main() -> int:
    m = L.measure(L.UNIVERSE)
    if m["state"] != "SUCCESS":
        print("FAILED:ADV-0141 emit controls", json.dumps(m["controls"], indent=2, sort_keys=True))
        return 1
    if not m["sets_agree"]:
        print("FAILED:ADV-0141 emit opener/audit COVERED disagreement")
        return 1
    doc = L.build_artifact_doc(m)
    errs = L.schema_errors(doc)
    if errs:
        print("FAILED:ADV-0141 emit schema", errs[:12])
        return 1
    garbage = {"unit_id": "ADV-0141", "state": "SUCCESS"}
    g_errs = L.schema_errors(garbage)
    if not g_errs:
        print("FAILED:ADV-0141 emit schema accepted garbage")
        return 1
    wrong_kind = {
        "schema_version": 1,
        "unit_id": "ADV-0141",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0141",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#ADV-0141",
        "min_bytes_threshold": 1,
        "artifacts": [
            {
                "path": "a",
                "bytes": 1,
                "sha256": "a" * 64,
                "exists": True,
            }
        ],
        "evidence": [
            {
                "claim": "c",
                "verdict": "NOT-CHECKED",
                "anchor": "a",
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": "x",
                        "raw_output": "y",
                        "fingerprint": "z",
                    }
                ],
            }
        ]
        * 2,
        "timestamps": {
            "started_at": "2026-08-25T00:00:00Z",
            "ended_at": "2026-08-25T00:00:00Z",
        },
        "retry": {"count": 0, "policy": "resumable checkpoint per container format"},
        "tests": [{"id": "t", "command": "c", "result": "PASS"}],
        "negative_controls": [
            {
                "id": "n",
                "kind": "mutation",
                "description": "d",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "r",
            "verdict": "PASS",
            "independent": True,
        },
        "manifest_registration": {"registered": True, "manifest_path": "m"},
        "downstream_consumers": [
            {
                "consumer": "c",
                "artifact_path": "p",
                "executed": True,
                "read_ok": True,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": "x",
                    "raw_output": "y",
                    "fingerprint": "q",
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": "c",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "s",
            }
        ],
        "report": {
            "kind": "not-coverage-difference",
            "observations": [
                {"name": "n", "measured": 1, "method": "m", "anchor": "a"}
            ],
            "control_ids": ["c1"],
        },
    }
    if not L.schema_errors(wrong_kind):
        print("FAILED:ADV-0141 emit schema accepted wrong report.kind")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"COVERED={len(m['covered_rows'])} PRODUCED={len(m['produced_rows'])} "
        f"DIFFERENCE={len(m['difference'])} canary={m['canary_id']}"
    )
    print("SUCCESS:ADV-0141 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
