#!/usr/bin/env python3
"""TST-0230 probe 2: production known-work timing separation above 1ms.

Times the production scorer (foundry.bench.score_case) over the same case
with an EMPTY document versus a known-work document (~1MiB of real stage
structure). PASS requires known-work p05 minus empty p95 above 1ms, so a
green cannot be produced by timing nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "platform" / "lib"))

from foundry.bench import DEFAULT_CASES, measure_known_work_separation  # noqa: E402


def known_work_doc() -> dict:
    """A document with real stage structure (~1MiB) the scorer must walk.

    iter_stages walks doc['stages'] as a LIST (depth-first into body and
    diagnose/repair/verify sub-mappings).
    """
    stages = []
    for i in range(2400):
        stages.append(
            {
                "kind": "task",
                "gate": {
                    "blocking": True,
                    "evidence_required": True,
                    "conditions_required": ["evidence"],
                    "on_fail": "block",
                },
                "work_unit": {
                    "evidence_requirement": f"evidence requirement for stage {i}",
                    "output_schema": "command-center/schema/artifact.schema.json",
                },
                "produces": [
                    {
                        "schema_ref": "command-center/schema/artifact.schema.json",
                        "min_bytes": 128,
                        "consumers": ["downstream"],
                    }
                ],
            }
        )
    return {
        "id": "tst-0230-known-work",
        "stages": stages,
        "gates": {"g0": {"blocking": True, "evidence_required": True, "conditions_required": ["x"], "on_fail": "block"}},
        "stopping_rules": {"max_turns": 10},
    }


def main() -> int:
    doc_empty: dict = {}
    doc_known = known_work_doc()
    payload_bytes = len(json.dumps(doc_known).encode("utf-8"))
    case = DEFAULT_CASES[0]

    report = measure_known_work_separation(doc_empty, doc_known, case, runs=21, required_ns=1_000_000)

    checks = {
        "known_work_input_material": payload_bytes > 500_000,
        "separation_above_1ms": report["separation_pass"] is True,
        "runs_material": report["runs"] == 21,
        "known_beats_empty": report["known_p05_ns"] > report["empty_p95_ns"],
    }
    out = {
        "probe": "probe2_timing_control",
        "unit": "TST-0230",
        "known_work_input_bytes": payload_bytes,
        "known_work_input_items": 2,
        "timing": report,
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe_timing_separation.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
