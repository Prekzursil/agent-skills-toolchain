#!/usr/bin/env python3
"""TST-0233 probe 2: the worse-than-every-source regression seed.

fusion.degraded fails every matched case; the gate REJECTS with FC-11333.
Mutation control: a stage-count comparator (more stages -> accept) ACCEPTS the
padded fusion, proving the real gate's behaviour contract is load-bearing and
that the degraded rejection is not a stage-count artifact. The named
complementarity case is EXECUTED: case.beta-only - wf.alpha fails it,
fusion.complement succeeds it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from gate import evaluate_corpus  # noqa: E402


def stage_count_mutant(report: dict) -> dict:
    """Mutation: decide purely on stage count (more stages -> accept)."""
    decisions = {}
    for v in report["verdicts"]:
        decisions[v["fusion_id"]] = "ACCEPT" if v["n_stages"] > 1 else "REJECT"
    return decisions


def main() -> int:
    report = evaluate_corpus()
    by_id = {v["fusion_id"]: v for v in report["verdicts"]}
    degraded_v = by_id["fusion.degraded"]
    padded_v = by_id["fusion.padded"]
    complement_v = by_id["fusion.complement"]

    per_source = complement_v.get("per_source") or []
    comp_cases = {
        p["complementarity_case"]["case_id"]
        for p in per_source
        if p.get("complementarity_case")
    }

    checks = {
        "regression_seed_worse_than_every_source": degraded_v["decision"] == "REJECT"
        and degraded_v["failure_class"] == "FC-11333",
        "mutation_stage_count_comparator_accepts_padded": stage_count_mutant(report)["fusion.padded"] == "ACCEPT",
        "real_gate_rejects_padded": padded_v["decision"] == "REJECT",
        "named_case_executed_alpha_fails_fusion_succeeds": "case.beta-only" in comp_cases,
        "complement_accepted": complement_v["decision"] == "ACCEPT",
        "padded_not_classified_as_degraded": padded_v["failure_class"] != "FC-11333",
    }
    out = {
        "probe": "probe2_worse_than_sources",
        "unit": "TST-0233",
        "complement_per_source": per_source,
        "verdicts": report["verdicts"],
        "mutation_decisions": stage_count_mutant(report),
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe2_worse_than_sources.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
