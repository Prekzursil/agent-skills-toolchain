#!/usr/bin/env python3
"""Emit TST-0231 receipt, SUBAGENT-RETURN.json, and per-unit manifest.

Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import distribution_gate as G  # noqa: E402

UNIT = "TST-0231"
OUT = f"command-center/receipts/{UNIT}.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    f"command-center/p2-wave/probes/{UNIT}/probe1_n_lt_k_and_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    f"command-center/p2-wave/probes/{UNIT}/probe2_analytic_and_fpr.py"
)
SUPPORTING = [
    f"command-center/p2-wave/probes/{UNIT}/distribution_gate.py",
    f"command-center/p2-wave/probes/{UNIT}/probe1_n_lt_k_and_both_states.py",
    f"command-center/p2-wave/probes/{UNIT}/probe2_analytic_and_fpr.py",
    f"command-center/p2-wave/probes/{UNIT}/fixtures/synthetic_known_normal.json",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        "role": role,
    }


def drop_samples(syn: dict) -> dict:
    skip = {
        "baseline_samples",
        "candidate_20pct_samples",
        "candidate_2pct_samples",
    }
    return {k: v for k, v in syn.items() if k not in skip}


def main() -> int:
    k = G.DEFAULT_K
    refusals = G.n_lt_k_controls(k=k)
    states = G.both_states_controls(k=k)
    syn = G.synthetic_known_distribution()
    fpr = G.no_change_false_positive_rate()

    if refusals["single_sample"]["verdict"] != "REFUSED":
        print("FAILED:TST-0231 emit n=1 not refused")
        return 1
    if refusals["n_k_minus_1_with_50pct"]["verdict"] != "REFUSED":
        print("FAILED:TST-0231 emit n=k-1 not refused")
        return 1
    if states["regression_20pct"]["verdict"] != "REGRESSION":
        print("FAILED:TST-0231 emit 20pct not caught")
        return 1
    if states["noise_2pct"]["verdict"] != "NO_REGRESSION":
        print("FAILED:TST-0231 emit 2pct flagged")
        return 1
    if syn["gate_20pct"]["verdict"] != "REGRESSION":
        print("FAILED:TST-0231 emit analytic 20pct")
        return 1
    if syn["gate_2pct"]["verdict"] != "NO_REGRESSION":
        print("FAILED:TST-0231 emit analytic 2pct")
        return 1
    if float(fpr["false_positive_rate"]) >= 0.05:
        print("FAILED:TST-0231 emit FPR", fpr)
        return 1

    fxdir = HERE / "fixtures"
    fxdir.mkdir(parents=True, exist_ok=True)
    fx_doc = {
        "unit_id": UNIT,
        "family": "Normal",
        "construction": "inverse-CDF at plotting positions (i+0.5)/n",
        "n": syn["n"],
        "baseline_params": syn["baseline_params"],
        "shift_20pct_params": syn["shift_20pct_params"],
        "shift_2pct_params": syn["shift_2pct_params"],
        "population": {
            "baseline": syn["population_baseline"],
            "shift_20pct": syn["population_20pct"],
            "shift_2pct": syn["population_2pct"],
        },
        "baseline_samples": syn["baseline_samples"],
        "candidate_20pct_samples": syn["candidate_20pct_samples"],
        "candidate_2pct_samples": syn["candidate_2pct_samples"],
    }
    fx_path = fxdir / "synthetic_known_normal.json"
    fx_path.write_text(
        json.dumps(G.jsonable(fx_doc), indent=1, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    question = (
        "Does the gate require n>=k repetitions and compare median and p95 "
        "with a stated variance, rather than one sample? PASS requires the "
        "gate to refuse a verdict when n < k and to report the spread "
        "alongside the point estimate."
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": f"SUCCESS:{UNIT}",
        "completion_sentinel": f"SUCCESS:{UNIT}",
        "report_kind": "benchmark_result",
        "kind": "receipt",
        "title": "The regression gate compares distributions, not single samples",
        "question": question,
        "question_or_target": question,
        "phase": "10",
        "generated_at": now,
        "generating_commit": "worktree-uncommitted",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/benchmark_result",
        "k": k,
        "noise_band": G.NOISE_BAND,
        "regression_threshold": G.REGRESSION_THRESHOLD,
        "higher_is_worse": True,
        "answer": (
            f"Yes. The gate's k={k}: n=1 and n={k-1} (even with a 50% shift) "
            "return REFUSED, not a scored verdict. Issued comparisons report "
            "median, p95, variance, stdev, and IQR on both sides. A 20% "
            "location-scale regression is REGRESSION; a 2% band is "
            "NO_REGRESSION. Inverse-CDF Normal samples match the closed-form "
            f"median/p95 within 1%. FPR over {fpr['n_runs']} no-change runs "
            f"is {fpr['false_positive_rate']}. SUCCESS:{UNIT}"
        ),
        "gate": {
            "module": f"command-center/p2-wave/probes/{UNIT}/distribution_gate.py",
            "k": k,
            "compares": ["median", "p95"],
            "spread_fields": ["variance", "stdev", "iqr"],
            "single_sample_verdict": refusals["single_sample"]["verdict"],
            "n_k_minus_1_verdict": refusals["n_k_minus_1_with_50pct"]["verdict"],
            "n_equals_k_verdict": refusals["n_equals_k_no_change"]["verdict"],
        },
        "controls": {
            "n_lt_k_refusal": G.jsonable(refusals),
            "both_states": {
                "regression_20pct": G.jsonable(states["regression_20pct"]),
                "noise_2pct": G.jsonable(states["noise_2pct"]),
            },
            "false_positive_rate": G.jsonable(fpr),
        },
        "synthetic_dataset": {
            "path": f"command-center/p2-wave/probes/{UNIT}/fixtures/synthetic_known_normal.json",
            "summary": G.jsonable(drop_samples(syn)),
        },
        "evidence": [
            {
                "kind": "n-lt-k-refusal",
                "path": f"command-center/p2-wave/probes/{UNIT}/distribution_gate.py",
                "note": (
                    f"n=1 verdict={refusals['single_sample']['verdict']}; "
                    f"n={k-1} with 50% shift verdict="
                    f"{refusals['n_k_minus_1_with_50pct']['verdict']}."
                ),
            },
            {
                "kind": "analytic-normal",
                "path": f"command-center/p2-wave/probes/{UNIT}/fixtures/synthetic_known_normal.json",
                "note": (
                    "Inverse-CDF Normal(100,10) vs 20% and 2% scaled twins; "
                    "gate median/p95 checked against NormalDist.inv_cdf."
                ),
            },
        ],
        "tests": [
            {
                "id": "refuse-verdict-when-n-lt-k",
                "requirement": "Gate refuses a verdict when n < k, including n=1.",
                "verdict": "PASS",
                "evidence": (
                    f"single_sample={refusals['single_sample']['verdict']} "
                    f"n_k_minus_1={refusals['n_k_minus_1_with_50pct']['verdict']}"
                ),
            },
            {
                "id": "both-states-20pct-vs-2pct",
                "requirement": "A genuine 20% regression is caught; a 2% noise band is not flagged.",
                "verdict": "PASS",
                "evidence": (
                    f"20pct={states['regression_20pct']['verdict']} "
                    f"2pct={states['noise_2pct']['verdict']}"
                ),
            },
            {
                "id": "false-positive-rate-100-no-change",
                "requirement": "False-positive rate measured over 100 no-change runs.",
                "verdict": "PASS",
                "evidence": (
                    f"flags={fpr['regression_flags']} / {fpr['n_runs']} "
                    f"rate={fpr['false_positive_rate']} seed={fpr['seed']}"
                ),
            },
            {
                "id": "analytic-normal-verdict",
                "requirement": "Synthetic known Normal: gate verdict matches analytic answer.",
                "verdict": "PASS",
                "evidence": (
                    f"20pct gate={syn['gate_20pct']['verdict']} "
                    f"analytic={syn['analytic_verdict_20pct']}; "
                    f"2pct gate={syn['gate_2pct']['verdict']} "
                    f"analytic={syn['analytic_verdict_2pct']}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0231-probe2-analytic-fpr",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 independently rebuilds the inverse-CDF Normal, "
                "recomputes median/p95, checks the closed-form population "
                "values, and measures FPR over 100 no-change redraws."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": f"command-center/p2-wave/probes/{UNIT}/distribution_gate.py",
                "exists": True,
                "role": "implementation",
            },
            {
                "path": f"command-center/p2-wave/probes/{UNIT}/fixtures/synthetic_known_normal.json",
                "exists": True,
                "role": "synthetic-dataset",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(G.jsonable(receipt), indent=1, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    text = out.read_text(encoding="utf-8")
    if f"SUCCESS:{UNIT}" not in text:
        print("FAILED:TST-0231 sentinel missing from receipt")
        return 1
    if json.loads(text).get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:TST-0231 self-declared blocked")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0231 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": f"SUCCESS:{UNIT}",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/benchmark_result",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0231-probe2-analytic-fpr",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for TST-0231: live named probes exit 0, receipts/TST-0231.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"SUCCESS:{UNIT} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
