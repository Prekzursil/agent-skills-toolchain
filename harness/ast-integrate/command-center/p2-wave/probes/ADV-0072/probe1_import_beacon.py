#!/usr/bin/env python3
"""Probe 1: import (do not run) hostile vs benign definitions; beacon oracle.

A behaviour change is a beacon file written during import. The hostile
definition is never executed. The naive splice mutant is the red control so a
silent oracle cannot be mistaken for a safe importer.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fixtures import TOKENS, benign_definition, hostile_definition  # noqa: E402
from importer import LIVE_FIELDS, import_definition, run_workflow  # noqa: E402

OUT = HERE / "probe1-import-beacon.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0072-probe1 {msg}")
    return 1


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="adv0072-probe1-"))
    try:
        benign_box = root / "benign"
        hostile_q = root / "hostile-quarantined"
        hostile_n = root / "hostile-naive"
        benign = import_definition(
            benign_definition(), sandbox=benign_box, mode="quarantined"
        )
        hostile = import_definition(
            hostile_definition(), sandbox=hostile_q, mode="quarantined"
        )
        naive = import_definition(
            hostile_definition(), sandbox=hostile_n, mode="naive"
        )

        executed_raised = False
        try:
            run_workflow(hostile_definition())
        except RuntimeError as exc:
            executed_raised = "forbids executing" in str(exc)

        expected = sorted(TOKENS.values())
        live_seen = list(hostile.live_fields_in_prompt)
        report = {
            "probe": "probe1-import-beacon",
            "unit_id": "ADV-0072",
            "pass": False,
            "benign": benign.as_dict(),
            "hostile_quarantined": hostile.as_dict(),
            "hostile_naive": naive.as_dict(),
            "expected_tokens": expected,
            "run_workflow_refused": executed_raised,
            "hostile_executed": bool(
                hostile.executed or naive.executed or benign.executed
            ),
            "live_fields_seen": live_seen,
        }
        ok = (
            benign.imported
            and hostile.imported
            and naive.imported
            and not benign.executed
            and not hostile.executed
            and not naive.executed
            and executed_raised
            and benign.fired_tokens == []
            and hostile.fired_tokens == []
            and sorted(naive.fired_tokens) == expected
            and not list(benign_box.glob("*.beacon"))
            and not list(hostile_q.glob("*.beacon"))
            and sorted(p.name for p in hostile_n.glob("*.beacon"))
            == sorted(f"{t}.beacon" for t in expected)
            and set(live_seen) >= set(LIVE_FIELDS)
        )
        report["pass"] = bool(ok)
        OUT.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        if not ok:
            return fail(
                "beacon/control mismatch "
                f"benign_fired={benign.fired_tokens} "
                f"hostile_fired={hostile.fired_tokens} "
                f"naive_fired={naive.fired_tokens} "
                f"executed={report['hostile_executed']} "
                f"run_refused={executed_raised} "
                f"live={live_seen}"
            )
        print(
            "SUCCESS:ADV-0072-probe1 benign import clean; quarantined hostile "
            "wrote no beacon; naive splice wrote every field beacon; "
            "workflow not executed"
        )
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
