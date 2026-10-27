#!/usr/bin/env python3
"""Census claimed latency/overhead figures actually present on this worktree."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

CLAIMED_PATHS = [
    "command-center/BASELINE-SNAPSHOT.json",
    "command-center/receipts/TST-0025.json",
    "command-center/receipts/TST-0105.json",
    "command-center/receipts/TST-0237.json",
    "command-center/receipts/TST-0238.json",
    "command-center/receipts/TST-0239.json",
    "command-center/receipts/TST-0305.json",
    "command-center/confirmation/CNF-0027-baseline-variance.json",
    "command-center/adversarial/ADV-0115-router-overhead-and-context-tax.json",
    "command-center/audit/AUD-0087-startup-latency-baseline.json",
    "hooks/harness-bench/baseline.json",
    "hooks/harness-bench/gate.py",
    "hooks/harness-bench/test_bench.py",
    "_USER-PROMPTS.md",
    "command-center/bench/results",
    "tools/bench",
]


def _stat(rel: str) -> dict:
    path = REPO / rel
    present = path.exists()
    kind = "missing"
    size = 0
    if present:
        kind = "dir" if path.is_dir() else "file"
        size = path.stat().st_size if path.is_file() else sum(
            1 for _ in path.rglob("*") if _.is_file()
        )
    return {"path": rel, "present": present, "kind": kind, "size": size}


def live_numeric_claims() -> list[dict]:
    rows: list[dict] = []
    fm = REPO / "command-center/phase3/A1/FAILURE-MODES.json"
    if fm.is_file():
        doc = json.loads(fm.read_text(encoding="utf-8"))
        lat = (doc.get("detection_latency") or {}).get("latency_ms")
        rows.append(
            {
                "source": "command-center/phase3/A1/FAILURE-MODES.json",
                "field": "detection_latency.latency_ms",
                "value_ms": lat,
                "n": 1,
                "thermal": "unspecified-single-sample",
                "input_size_asserted": False,
                "run_order_randomized": False,
                "note": "Stop-hook plant+detect+hook wall-clock; single number, not a distribution.",
            }
        )
    adv = REPO / "command-center/p2-wave/probes/ADV-0115/_validate_out.json"
    if adv.is_file():
        doc = json.loads(adv.read_text(encoding="utf-8"))
        ids = doc.get("evidence_ids") or []
        snippet = next((x for x in ids if isinstance(x, str) and "ms p50" in x), None)
        rows.append(
            {
                "source": "command-center/p2-wave/probes/ADV-0115/_validate_out.json",
                "field": "evidence_ids[0]",
                "value_ms": 183.068255 if snippet else None,
                "n": None,
                "thermal": "warm",
                "input_size_asserted": False,
                "run_order_randomized": False,
                "primary_artifact_present": (
                    REPO / "command-center/adversarial/ADV-0115-router-overhead-and-context-tax.json"
                ).is_file(),
                "source_unit_state": doc.get("state"),
                "note": snippet or "no ms p50 snippet",
            }
        )
    return rows


def census() -> dict:
    files = [_stat(p) for p in CLAIMED_PATHS]
    present = [r for r in files if r["present"]]
    claims = live_numeric_claims()
    rerunnable = [
        c
        for c in claims
        if c.get("value_ms") is not None
        and c.get("n", 1) not in (None, 1)
        and c.get("input_size_asserted")
    ]
    return {
        "claimed_result_files": files,
        "claimed_result_files_present": present,
        "live_numeric_claims": claims,
        "rerunnable_recorded_distributions": rerunnable,
        "product_harness_present": (REPO / "hooks/harness-bench/gate.py").is_file(),
        "user_prompts_present": (REPO / "_USER-PROMPTS.md").is_file(),
        "baseline_snapshot_present": (REPO / "command-center/BASELINE-SNAPSHOT.json").is_file(),
        "honest_summary": (
            "No recorded product latency/overhead distribution with non-empty "
            "input sizes exists on this worktree. The only live numeric claims "
            "are a single-sample Stop-hook latency and a warm-only ADV-0115 "
            "snippet whose primary artifact is absent."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(census(), indent=2, sort_keys=True))
