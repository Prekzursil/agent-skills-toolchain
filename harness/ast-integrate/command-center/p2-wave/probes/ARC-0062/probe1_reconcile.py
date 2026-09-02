#!/usr/bin/env python3
"""Probe 1: cross-artifact reconciliation, computed, with a both-states control.

paths listed in the source dossiers minus paths listed in the hybrid must be
empty. Dropping a known-present source id from the hybrid must surface it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from hybrid import hybrid_paths  # noqa: E402
from proof import run_proof  # noqa: E402
from sources import EPOCHS, source_dossier_paths  # noqa: E402


def main() -> int:
    proof = run_proof()
    print(json.dumps(
        {
            "ok": proof["ok"],
            "evaluator_node": proof["evaluator_node"],
            "source_count": proof["clean"]["reconciliation"]["source_count"],
            "hybrid_count": proof["clean"]["reconciliation"]["hybrid_count"],
            "missing": proof["clean"]["reconciliation"]["missing"],
            "clean_bypass_count": proof["clean"]["bypass_count"],
            "epochs": proof["clean"]["epochs"]["counts"],
            "both_states": proof["reconciliation_both_states"],
        },
        sort_keys=True,
    ))
    src = source_dossier_paths()
    hyb = hybrid_paths()
    src_ids = [r["id"] for r in src]
    hyb_ids = [r["id"] for r in hyb]
    print(
        f"source={len(src_ids)} hybrid={len(hyb_ids)} "
        f"missing={proof['clean']['reconciliation']['missing']}"
    )
    print(
        f"both_states clean_empty={proof['reconciliation_both_states']['clean_empty']} "
        f"mutant_reports_victim={proof['reconciliation_both_states']['mutant_reports_victim']} "
        f"victim={proof['reconciliation_both_states']['victim']}"
    )
    print(f"epochs={proof['clean']['epochs']['counts']}")
    if not proof["reconciliation_both_states"]["discriminates"]:
        print("FAILED:ARC-0062-probe1 reconciliation both-states did not discriminate")
        return 1
    if proof["clean"]["reconciliation"]["missing"]:
        print("FAILED:ARC-0062-probe1 source-minus-hybrid not empty")
        return 1
    if not proof["clean"]["epochs"]["complete"]:
        print(f"FAILED:ARC-0062-probe1 epoch gap {proof['clean']['epochs']['missing']}")
        return 1
    for epoch in EPOCHS:
        if proof["clean"]["epochs"]["counts"].get(epoch, 0) < 1:
            print(f"FAILED:ARC-0062-probe1 no path in epoch {epoch}")
            return 1
    if not proof["ok"]:
        print("FAILED:ARC-0062-probe1 proof.ok is false")
        return 1
    print("SUCCESS:ARC-0062-probe1 source-minus-hybrid empty and both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
