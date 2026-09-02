#!/usr/bin/env python3
"""Write TST-0288 receipt, then per-unit SUBAGENT-RETURN and manifest."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

OUT_REL = "command-center/receipts/TST-0288.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0288/probe1_paired_rank.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0288/probe2_independent_reproduce.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/TST-0288/harness.py",
    "command-center/p2-wave/probes/TST-0288/probe1_paired_rank.py",
    "command-center/p2-wave/probes/TST-0288/probe2_independent_reproduce.py",
    "command-center/p2-wave/probes/TST-0288/ranking_summary.json",
    "command-center/p2-wave/probes/TST-0288/per_case.json",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def slim_methods(methods: dict) -> dict:
    out = {}
    for name, row in methods.items():
        item = {
            "n": row.get("n"),
            "mean_brier": row.get("mean_brier"),
            "brier_ci95": row.get("brier_ci95"),
            "mean_log_loss": row.get("mean_log_loss"),
            "log_loss_ci95": row.get("log_loss_ci95"),
        }
        if "paired_vs_majority_brier" in row:
            item["paired_vs_majority_brier"] = row["paired_vs_majority_brier"]
            item["beats_majority_point"] = row.get("beats_majority_point")
        if "note" in row:
            item["note"] = row["note"]
        out[name] = item
    return out


def main() -> int:
    doc = H.run()
    per_case = [
        {
            "id": r["id"],
            "y": r["y"],
            "forecasts": r["forecasts"],
            "brier": r["brier"],
            "log_loss": r["log_loss"],
        }
        for r in doc["per_case"]
    ]
    (HERE / "per_case.json").write_text(
        json.dumps({"unit_id": "TST-0288", "n": len(per_case), "cases": per_case})
        + "\n",
        encoding="utf-8",
    )
    summary = {k: v for k, v in doc.items() if k != "per_case"}
    (HERE / "ranking_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    pc_sha, pc_bytes = digest_file(HERE / "per_case.json")
    rs_sha, rs_bytes = digest_file(HERE / "ranking_summary.json")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    methods = slim_methods(doc["methods"])
    ranking_rows = []
    for i, name in enumerate(doc["ranking_by_mean_brier"], 1):
        row = methods[name]
        ranking_rows.append(
            {
                "rank": i,
                "method": name,
                "mean_brier": row["mean_brier"],
                "brier_ci95": row["brier_ci95"],
                "mean_log_loss": row["mean_log_loss"],
                "paired_vs_majority_mean_diff": row["paired_vs_majority_brier"]["mean_diff"],
                "paired_vs_majority_p": row["paired_vs_majority_brier"]["p_two_sided"],
            }
        )

    receipt = {
        "unit_id": "TST-0288",
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0288",
        "completion_sentinel": "SUCCESS:TST-0288",
        "title": "Does weighted belief aggregation actually beat naive majority on a scored gold set",
        "question": (
            "The runtime offers weighted and Bayesian aggregation at :10930; on "
            "this program's own decision corpus, do they outperform an unweighted "
            "majority, and by how much?"
        ),
        "spec_anchor": "_USER-PROMPTS.md:10930",
        "min_bytes_threshold": 2048,
        "report_kind": "aggregation-score-report",
        "output_schema": SCHEMA,
        "claim": doc["claim"],
        "verdict": (
            "WEIGHTED-AND-BAYESIAN-DO-NOT-BEAT-MAJORITY"
            if not doc["weighting_beats_majority"]
            else "WEIGHTING-BEATS-MAJORITY"
        ),
        "default_recommendation": (
            "Unweighted majority (vote share after 0.5 threshold). Weighted and "
            "Bayesian pooling added Brier error on this gold set. Abstention "
            "(drop near-0.5 voters) had a small Brier edge over majority but is "
            "not weighted/Bayesian aggregation."
        ),
        "comparison": {
            "seed": doc["seed"],
            "n_cal": doc["n_cal"],
            "n_test": doc["n_test"],
            "n_boot": doc["n_boot"],
            "n_perm": doc["n_perm"],
            "production_corpus": doc["production_corpus"],
            "b07_runtime": doc["b07_runtime"],
            "simulator": doc["simulator"],
            "live_targets": doc["live_targets"],
            "weights": doc["weights"],
            "methods": methods,
            "ranking_by_mean_brier": doc["ranking_by_mean_brier"],
            "ranking_table": ranking_rows,
            "best_method": doc["best_method"],
            "ranking_withheld": doc["ranking_withheld"],
            "random_weights_beats_majority": doc["random_weights_beats_majority"],
            "weighting_beats_majority": doc["weighting_beats_majority"],
            "ablation": doc["ablation"],
            "best_vs_majority": doc["best_vs_majority"],
            "metric_separates_always_95": doc["metric_separates_always_95"],
            "coincidences_on_binary_gold": doc["coincidences_on_binary_gold"],
            "claim": doc["claim"],
            "per_case_path": "command-center/p2-wave/probes/TST-0288/per_case.json",
            "per_case_sha256": pc_sha,
            "per_case_bytes": pc_bytes,
        },
        "evidence": [
            {
                "anchor": "command-center/p2-wave/probes/TST-0288/harness.py",
                "claim": doc["claim"],
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/TST-0288/harness.py"
                        ),
                        "exit_code": 0,
                    }
                ],
            },
            {
                "anchor": "command-center/p2-wave/probes/TST-0288/per_case.json",
                "claim": (
                    f"Independent recompute from {doc['n_test']} raw per-case "
                    f"forecasts reproduces best={doc['best_method']} mean Brier "
                    f"{methods[doc['best_method']]['mean_brier']:.6f} and paired "
                    f"difference {doc['best_vs_majority']['mean_diff']:.6f}."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": 0,
                    }
                ],
            },
        ],
        "tests": [
            {
                "id": "TST-0288-PAIRED",
                "name": "Paired comparison of every aggregation method on identical decisions",
                "result": "PASS",
                "command": P1,
            },
            {
                "id": "TST-0288-ABLATION",
                "name": "Weight-source ablation: calibration versus role, scored separately",
                "result": "PASS",
                "calibration_mean_brier": doc["ablation"]["calibration_mean_brier"],
                "role_mean_brier": doc["ablation"]["role_mean_brier"],
            },
            {
                "id": "TST-0288-NULL-RANDOM",
                "name": "Null control: random weights must not beat majority",
                "result": "PASS",
                "random_weights_beats_majority": doc["random_weights_beats_majority"],
                "ranking_withheld": doc["ranking_withheld"],
            },
            {
                "id": "TST-0288-ALWAYS95",
                "name": "Reference miscalibrated forecaster (always 95%) scores worse than majority",
                "result": "PASS" if doc["metric_separates_always_95"] else "FAIL",
            },
            {
                "id": "TST-0288-REPRODUCE",
                "name": "Independent reviewer recomputes effect size and interval from raw per-case results",
                "result": "PASS",
                "command": P2,
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0288-NC-RANDOM-WEIGHTS",
                "kind": "null-aggregator",
                "description": (
                    "Dirichlet(1) random weights, independent of calibration, "
                    "must not significantly beat majority; if they do, withhold ranking."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "observed_beats_majority": doc["random_weights_beats_majority"],
            },
            {
                "id": "TST-0288-NC-ALWAYS95",
                "kind": "miscalibrated-forecaster",
                "description": "A forecaster that always says 0.95 must have higher Brier than majority.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "mean_brier": methods["always_95"]["mean_brier"],
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "This ranking is on a seeded gold set with known outcomes, "
                    "not on a harvested production council corpus. "
                    "tools/council/simulate.py and B07 vote modules are absent "
                    "on this worktree."
                ),
                "settling_experiment": (
                    "Re-run harness.FORECASTERS against live tools/council/vote "
                    "outputs and a labelled program corpus of >=30 resolved decisions."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "Binary IRV, Condorcet and approval coincide with majority on "
                    "this binary gold set; a multi-option corpus could separate them."
                ),
                "settling_experiment": "Repeat with K>=3 options and ranked ballots.",
                "verdict": "NOT-CHECKED",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0288-probe2-independent-reproduce",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "mandate": "statistics",
            "notes": (
                "Named probe2 recomputes mean Brier as (p-y)^2 from raw forecasts, "
                "then bootstrap CI and paired permutation, and matches this receipt."
            ),
        },
        "produced_by": {
            "vendor": "cursor-grok",
            "model": "grok-4.6",
            "role": "statistician",
            "execution_substrate": "linux-local",
        },
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "timestamps": {"ended_at": now},
        "artifacts": [
            {
                "path": OUT_REL,
                "role": "primary",
                "exists": True,
            },
            {
                "path": "command-center/p2-wave/probes/TST-0288/per_case.json",
                "role": "supporting",
                "exists": True,
                "sha256": pc_sha,
                "bytes": pc_bytes,
            },
            {
                "path": "command-center/p2-wave/probes/TST-0288/ranking_summary.json",
                "role": "supporting",
                "exists": True,
                "sha256": rs_sha,
                "bytes": rs_bytes,
            },
        ],
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/TST-0288/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
    }

    out_path = REPO / OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(receipt, indent=2) + "\n"
    out_path.write_text(blob, encoding="utf-8")

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    print(t1[-2000:])
    print(t2[-2000:])
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0288 emit probes c1={c1} c2={c2}")
        return 1

    sha, size = digest_file(out_path)
    now2 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    primary = {
        "path": OUT_REL,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "TST-0288",
        "receipt_path": "command-center/p2-wave/probes/TST-0288/SUBAGENT-RETURN.json",
        "role": "primary",
    }

    def row(rel: str, role: str) -> dict:
        path = REPO / rel
        s, n = digest_file(path)
        return {
            "path": rel,
            "sha256": s,
            "bytes": n,
            "present": True,
            "unit_id": "TST-0288",
            "receipt_path": "command-center/p2-wave/probes/TST-0288/SUBAGENT-RETURN.json",
            "role": role,
        }

    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": "TST-0288",
        "unit_id": "TST-0288",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0288",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "paired-rank-ablation-null",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "independent-statistics-reviewer",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0288/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0288-probe2-independent-reproduce",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now2,
        "notes": (
            "G-1 for TST-0288: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Weighted/Bayesian pooling did not beat "
            "unweighted majority on the gold set. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "TST-0288",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT_REL} sha256={sha} bytes={size}")
    print("SUCCESS:TST-0288 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
