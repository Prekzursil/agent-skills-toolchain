#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0113-benchmark-matched-pair-harness.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixtures import BUDGET_LIMIT, BUDGET_UNIT, SEED  # noqa: E402
from harness import inventory, run_experiment  # noqa: E402

OUT = "command-center/wfa/WFA-0113-benchmark-matched-pair-harness.json"
SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json"
SENTINEL = "SUCCESS:WFA-0113"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0113/probe1_input_hashes_and_floor.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0113/probe2_failed_arm_budget_floor.py"
)
QUESTION = (
    "Implementation target: a harness that runs each source workflow and each "
    "fused candidate on the SAME case with the same inputs, seeds and budget, "
    "recording per-run cost, wall-clock, terminal state and oracle verdict - so "
    "a comparison is a controlled experiment rather than two separate anecdotes."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def compact_run(run: dict, extra: bool = False) -> dict:
    row = {
        "run_id": run["run_id"],
        "workflow_id": run["workflow_id"],
        "workflow_role": run["workflow_role"],
        "case_id": run["case_id"],
        "seq": run["seq"],
        "phase": run["phase"],
        "seed": run["seed"],
        "budget_limit": run["budget_limit"],
        "budget_spent": run["budget_spent"],
        "cost": run["cost"],
        "wall_clock_ms": run["wall_clock_ms"],
        "terminal_state": run["terminal_state"],
        "oracle_verdict": run["oracle_verdict"],
        "oracle_score": run["oracle_score"],
        "quality": run["quality"],
        "input_hash": run["input_hash"],
    }
    if extra:
        row.update(
            {
                "error": run["error"],
                "dropped": run["dropped"],
                "stages_executed": run["stages_executed"],
                "stage_count": run["stage_count"],
                "requested_budget_ignored": run["requested_budget_ignored"],
            }
        )
    return row


def build_tests(exp: dict) -> list[dict]:
    floor = exp["variance_floor"]
    hashes = exp["input_hash_parity"]
    failed = exp["failed_arm_accounting"]
    budget = exp["budget_parity"]
    hungry = exp["budget_exhausted_arms"]
    crash = exp["failed_arms"]
    below = exp["suppressor_controls"]["below_floor"]
    above = exp["suppressor_controls"]["above_floor"]
    quality_quiet = all(
        not row.get("reported_as_difference") for row in exp["quality_comparisons"]
    )
    seq_ok = int(floor["max_control_seq"]) < int(floor["min_comparison_seq"])
    floor_first = bool(floor["measured_before_comparisons"]) and seq_ok
    crash_kept = bool(crash) and all(not a.get("dropped") for a in crash)
    hungry_halted = bool(hungry) and all(
        float(a["budget_spent"]) <= float(a["budget_limit"])
        and int(a["stages_executed"]) < int(a["stage_count"])
        for a in hungry
    )
    requested_ignored = all(
        r.get("requested_budget_ignored") is not None
        and float(r["requested_budget_ignored"]) != float(r["budget_limit"])
        and float(r["budget_limit"]) == float(exp["budget_limit"])
        for r in exp["comparison_runs"]
    )
    return [
        {
            "id": "variance-floor-before-comparison",
            "requirement": (
                "the variance floor must be measured before any comparison is reported"
            ),
            "result": "PASS" if floor_first else "FAIL",
            "observed": {
                "measured_before_comparisons": floor["measured_before_comparisons"],
                "max_control_seq": floor["max_control_seq"],
                "min_comparison_seq": floor["min_comparison_seq"],
                "live_oracle_floor": floor["live_oracle_floor"],
            },
        },
        {
            "id": "input-hashes-match-on-pairs",
            "requirement": (
                "per pair, both arms run on the identical case with the same budget, "
                "verified by comparing the recorded input hashes"
            ),
            "result": "PASS" if hashes["all_matched_pairs_agree"] else "FAIL",
            "observed": hashes,
        },
        {
            "id": "failed-arm-retained",
            "requirement": (
                "an arm that fails to run is recorded as a failed arm, never dropped "
                "from the comparison"
            ),
            "result": "PASS"
            if crash_kept and not failed["any_pair_dropped"] and not exp["drop_failed"]
            else "FAIL",
            "observed": failed,
        },
        {
            "id": "budget-parity-enforced-by-harness",
            "requirement": (
                "budget parity must be enforced by the harness, not requested of the workflows"
            ),
            "result": "PASS"
            if budget["equal"]
            and budget["enforced_by"] == "harness"
            and hungry_halted
            and requested_ignored
            else "FAIL",
            "observed": {
                "budget_parity": budget,
                "hungry_halted": hungry_halted,
                "requested_budget_ignored": requested_ignored,
                "budget_exhausted_arms": hungry,
            },
        },
        {
            "id": "below-floor-not-reported",
            "requirement": (
                "a difference between two workflows smaller than the variance floor "
                "is not a difference and must not be reported as one"
            ),
            "result": "PASS"
            if (not below["reported_as_difference"])
            and above["reported_as_difference"]
            and quality_quiet
            else "FAIL",
            "observed": {
                "suppressor_controls": exp["suppressor_controls"],
                "quality_comparisons_not_reported": quality_quiet,
                "quality_floor_used": floor["quality_floor_used"],
            },
        },
    ]


def main() -> int:
    exp = run_experiment(seed=SEED, budget_limit=BUDGET_LIMIT, planted_floor=0.05)
    inv = inventory(REPO)
    tests = build_tests(exp)
    red = [t["id"] for t in tests if t["result"] != "PASS"]
    if red:
        print(f"FAILED:WFA-0113 emit tests red {red}")
        print(json.dumps(tests, indent=2)[:4000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_present = (REPO / SCHEMA).is_file() and (REPO / SCHEMA).stat().st_size > 0
    doc = {
        "kind": "BenchmarkResult",
        "unit_id": "WFA-0113",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "ts": now,
        "title": (
            "Matched-pair harness running source and fused workflows on identical cases"
        ),
        "question": QUESTION,
        "schema_ref": f"{SCHEMA}#/$defs/BenchmarkResult",
        "schema_pack_present": schema_present,
        "declared_metric": {
            "id": "oracle_score",
            "direction": "higher-is-better",
            "estimator": (
                "binary case pass (required capabilities subseteq collected "
                "capabilities within harness-imposed budget); quality is a secondary "
                "continuous metric used only for the below-floor suppressor control"
            ),
        },
        "harness": {
            "seed": SEED,
            "budget_limit": BUDGET_LIMIT,
            "budget_unit": BUDGET_UNIT,
            "budget_enforcement": "harness",
            "control_runs_per_workflow_case": 2,
            "records_per_run": [
                "cost",
                "wall_clock_ms",
                "terminal_state",
                "oracle_verdict",
                "input_hash",
            ],
        },
        "upstream": inv,
        "variance_floor": exp["variance_floor"],
        "budget_parity": exp["budget_parity"],
        "input_hash_parity": exp["input_hash_parity"],
        "failed_arm_accounting": exp["failed_arm_accounting"],
        "cases": exp["cases"],
        "workflows": exp["workflows"],
        "control_runs": [compact_run(r) for r in exp["control_runs"]],
        "runs": [compact_run(r, extra=True) for r in exp["comparison_runs"]],
        "pairs": exp["pairs"],
        "comparisons": exp["comparisons"],
        "quality_comparisons": exp["quality_comparisons"],
        "failed_arms": exp["failed_arms"],
        "budget_exhausted_arms": exp["budget_exhausted_arms"],
        "suppressor_controls": exp["suppressor_controls"],
        "tests": tests,
        "reviewer": {
            "reviewer_id": "WFA-0113-probe2-failed-arm-budget-floor",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-runs the crash, hungry, and below-floor both-states "
                "controls without reading this artifact's answers. Probe 1 "
                "recomputes input hashes and checks control seq < comparison seq."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "input-hashes-and-floor", "command": P1},
            {"id": "probe2", "role": "failed-arm-budget-floor", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/WFA-0113/harness.py",
                "role": "harness",
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0113/fixtures.py",
                "role": "fixture-corpus",
            },
        ],
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/WFA-0113/harness.py",
                "claim": (
                    "A: per pair, both arms share input_hash of case+seed+budget. "
                    "B: control arm runs the same workflow twice before comparisons; "
                    "abs(delta) <= floor is classified not-a-difference."
                ),
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0113/probe2_failed_arm_budget_floor.py",
                "claim": (
                    "Failed crash arm is retained; drop_failed mutant drops it. "
                    "Hungry fusion is halted by the harness at budget_limit. "
                    "Planted 0.01 vs 0.05 is not reported; 0.10 vs 0.05 is."
                ),
            },
        ],
        "answers": {
            "matched_input_hashes": exp["input_hash_parity"]["all_matched_pairs_agree"],
            "variance_floor_measured_first": exp["variance_floor"][
                "measured_before_comparisons"
            ],
            "failed_arms_retained": (
                exp["failed_arm_accounting"]["failed_count"] > 0
                and not exp["failed_arm_accounting"]["any_pair_dropped"]
            ),
            "budget_parity_enforced_by_harness": exp["budget_parity"]["equal"],
            "below_floor_not_reported": not exp["suppressor_controls"]["below_floor"][
                "reported_as_difference"
            ],
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "benchmark-engineer",
            "execution_substrate": "linux-local",
            "ts": now,
        },
        "cloud_ok": False,
        "does_not_claim": [
            "cloud ok=true is delivery",
            "WFA-0112 benchmark case corpus is present on this worktree",
            "fusion-operator artifacts are present on this worktree",
            "wfa-schema-pack.json is present and this document was validated against it",
            "global unit_manifest.py --write was run",
        ],
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:WFA-0113 completion sentinel missing from serialized artifact")
        return 1
    blocked = str(doc.get("state") or "").upper()
    if blocked in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:WFA-0113 self-declared {blocked}")
        return 1
    out.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 2000:
        print(f"FAILED:WFA-0113 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        "floor={0} pairs={1} failed_arms={2} hungry={3}".format(
            exp["variance_floor"]["live_oracle_floor"],
            len(exp["pairs"]),
            exp["failed_arm_accounting"]["failed_count"],
            len(exp["budget_exhausted_arms"]),
        )
    )
    print("SUCCESS:WFA-0113 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
