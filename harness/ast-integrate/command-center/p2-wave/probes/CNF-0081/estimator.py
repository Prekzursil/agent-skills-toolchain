"""Pre-run estimator. Reads only declared stage fields.

Does not see hidden_retries or amplifier. That omission is the bias under
test: a systematically low estimator is a scheduling hazard.
"""
from __future__ import annotations

from ledger import CUMULATIVE_FIELD, cost_usd


def estimate_workflow(wf: dict) -> dict:
    stages = list(wf.get("stages") or [])
    tokens = 0
    wall_s = 0.0
    outputs: list[str] = []
    for stage in stages:
        tokens += int(stage.get("declared_tokens", 80))
        wall_s += float(stage.get("declared_duration_s", 0.01))
        for out in stage.get("outputs") or []:
            outputs.append(str(out))
    return {
        "tokens_cumulative": tokens,
        "wall_clock_s": wall_s,
        "cost_usd": cost_usd(tokens),
        "blast_radius": sorted(set(outputs)),
        "estimator": "command-center/p2-wave/probes/CNF-0081/estimator.py",
        "uses_field": CUMULATIVE_FIELD,
        "sees_hidden_retries": False,
        "sees_amplifier": False,
    }
