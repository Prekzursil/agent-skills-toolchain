#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0290.json from live three-way measurements."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from measure import REPO, collect  # noqa: E402

OUT = "command-center/receipts/TST-0290.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0290"
QUESTION = (
    "Implementation target: implement and test the :10762 deadlock, escalation, "
    "replacement and owner-intervention policies. Distinguish three states that "
    "look identical from outside - productive disagreement, genuine deadlock, "
    "and a stalled runtime - and require different handling for each. Escalating "
    "a productive disagreement destroys the dissent the council exists to "
    "surface; treating a stalled runtime as disagreement burns the whole budget."
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/council/stopping/tests/test_deadlock.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0290/probe1_three_way_actions.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0290/probe2_owner_packet.py"
)
SUPPORTING = [
    SCHEMA,
    "tools/council/stopping/deadlock.py",
    "tools/council/stopping/__init__.py",
    "tools/council/stopping/schema/deadlock-classification.schema.json",
    "tools/council/stopping/tests/test_deadlock.py",
    "tools/council/owner_ask.py",
    "tools/council/simulate.py",
    "command-center/p2-wave/probes/TST-0290/measure.py",
    "command-center/p2-wave/probes/TST-0290/probe1_three_way_actions.py",
    "command-center/p2-wave/probes/TST-0290/probe2_owner_packet.py",
]


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def main() -> int:
    data = collect()
    if not data.get("ok"):
        print("FAILED:TST-0290 emit live flags not all true")
        print(json.dumps(data["flags"], indent=2, sort_keys=True))
        return 1
    # probe1 re-checks the receipt on disk against the live trace hash. While
    # re-emitting, that receipt is by definition the stale one, so set it aside
    # for the library-only probe pass and restore it if emission fails.
    dest = REPO / OUT
    stale = dest.read_bytes() if dest.is_file() else None
    if stale is not None:
        dest.unlink()
    try:
        c_test, t_test = run_cmd(TEST_CMD)
        c1, t1 = run_cmd(P1)
        c2, t2 = run_cmd(P2)
    finally:
        if stale is not None and not dest.is_file():
            dest.write_bytes(stale)
    if c_test != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0290 emit tests={c_test} p1={c1} p2={c2}")
        print(t_test[-1500:])
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    if "SUCCESS:TST-0290-tests" not in t_test:
        print("FAILED:TST-0290 emit tests sentinel missing")
        return 1
    if "SUCCESS:TST-0290-probe1" not in t1:
        print("FAILED:TST-0290 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:TST-0290-probe2" not in t2:
        print("FAILED:TST-0290 emit probe2 sentinel missing")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_a = data["run_a"]
    policy = data["policy"]
    rows = policy["rows"]
    answer = (
        "Three scripted runs that look stuck from outside take three different "
        f"actions: productive_disagreement -> {rows[0]['action']} (dissent "
        f"preserved, no escalation); genuine_deadlock -> {rows[1]['action']} "
        f"naming {policy['deadlock_proposition_id']}; stalled_runtime -> "
        f"{rows[2]['action']} for seat {rows[2]['seat_id']} (not a deliberation "
        "outcome). A single generic escalation did not fire. Owner packet "
        "Q-CUTOVER is one foundation-level question with a recommendation and "
        "a stated default; two-question, compound, and already-settled packets "
        f"are refused. Same-seed traces hash to {run_a['trace_hash']}; seed 8 "
        "diverges. Frozen clock and fixed pid do not move the production DAG; "
        "leak flags do. SUCCESS:TST-0290"
    )
    arts = [{"path": OUT, "exists": True, "role": "primary"}]
    for rel in SUPPORTING:
        arts.append(
            {
                "path": rel,
                "exists": (REPO / rel).is_file(),
                "role": "supporting",
            }
        )
    doc = {
        "answer": answer,
        "artifacts": arts,
        "claim_under_test": (
            "Productive disagreement, genuine deadlock, and a stalled runtime "
            "must be classified apart and must trigger three distinct actions. "
            "Owner intervention asks one foundation-level question with a "
            "recommendation and a stated default."
        ),
        "completion_sentinel": SENTINEL,
        "evidence": [
            {
                "anchor": "tools/council/stopping/deadlock.py:run_three_way",
                "claim": (
                    "productive="
                    + rows[0]["action"]
                    + " deadlock="
                    + rows[1]["action"]
                    + " stalled="
                    + rows[2]["action"]
                    + " generic_escalation="
                    + str(policy["generic_escalation"])
                    + " proposition="
                    + str(policy["deadlock_proposition_id"])
                ),
                "detail": (
                    "productive="
                    + rows[0]["action"]
                    + " deadlock="
                    + rows[1]["action"]
                    + " stalled="
                    + rows[2]["action"]
                    + " generic_escalation="
                    + str(policy["generic_escalation"])
                    + " proposition="
                    + str(policy["deadlock_proposition_id"])
                ),
                "kind": "three-way-scripted-runs",
                "path": "tools/council/stopping/deadlock.py",
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "tools/council/owner_ask.py:check_packet",
                "claim": (
                    "Q-CUTOVER question_count=1 recommendation and default "
                    "present; two-question, compound, and settled packets refused."
                ),
                "detail": (
                    "Q-CUTOVER question_count=1 recommendation and default "
                    "present; two-question, compound, and settled packets refused."
                ),
                "kind": "owner-intervention-packet",
                "path": "tools/council/owner_ask.py",
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "tools/council/simulate.py:three_cast_bundle",
                "claim": (
                    f"seed={data['seed']} run_a={run_a['trace_hash']} "
                    f"run_b={data['run_b']['trace_hash']} identical=true; "
                    f"seed={data['other_seed']} diverges"
                ),
                "detail": (
                    f"seed={data['seed']} run_a={run_a['trace_hash']} "
                    f"run_b={data['run_b']['trace_hash']} identical=true; "
                    f"seed={data['other_seed']} diverges"
                ),
                "kind": "trace-hash-comparison",
                "path": "tools/council/simulate.py",
                "verdict": "CONFIRMED",
            },
        ],
        "fixed_pid": {
            "applied": True,
            "pid": data["fixed_pid"],
            "trace_unchanged": True,
            "live_hash": data["live_pid_hash"],
        },
        "frozen_clock": {
            "applied": True,
            "clock_ns": data["frozen_ns"],
            "trace_unchanged": True,
            "wall_hash": data["wall_hash"],
            "frozen_hash": run_a["trace_hash"],
        },
        "id": "TST-0290",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "role": "three-way"},
            {"id": "probe2", "command": P2, "exit_code": c2, "role": "owner-reviewer"},
        ],
        "nondeterminism_sources": data["sources"],
        "notes": (
            "G-1 for TST-0290: live named probes exit 0, receipt state=SUCCESS "
            "with SUCCESS:TST-0290, per-unit UNIT-ARTIFACT-MANIFEST row. Did not "
            "run global unit_manifest.py --write. Cloud ok=true is not delivery. "
            "TST-0257/TST-0263/IMP-0310/IMP-0366 are catalog dependencies not "
            "delivered here; this unit ships the three-way policy and a scripted "
            "persona runner, not the full B07 kernel. SUCCESS:TST-0290"
        ),
        "question": QUESTION,
        "registered": True,
        "residual_unknowns": [
            {
                "claim": (
                    "TST-0257 (byte-reproducible CouncilSpec simulator) and "
                    "TST-0263 (information-gain stop) are catalog dependencies "
                    "and are not delivered on this worktree."
                ),
                "settling_experiment": (
                    "After those units land, replay the three casts through the "
                    "kernel simulator and re-run probe1 against that transcript."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "reviewer": {
            "independent": True,
            "method": (
                "Probe 2 re-runs the three scripted casts, requires three "
                "distinct actions, checks the owner packet both-states control "
                "(legal packet vs two-question / compound / settled), and "
                "injects clock and pid leaks. This is a detector control, not a "
                "re-read of probe 1's conclusion."
            ),
            "reviewer_id": "TST-0290-probe2-owner-packet",
            "verdict": "PASS",
        },
        "schema_version": 1,
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "tests": [
            {
                "id": "productive-disagreement-no-escalation",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "genuine-deadlock-named-proposition",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "stalled-runtime-operational-failure",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "owner-intervention-one-question",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
            {
                "id": "unit-tests",
                "command": TEST_CMD,
                "result": "PASS",
                "exit_code": c_test,
            },
        ],
        "three_way": {
            "distinct_actions": policy["distinct_actions"],
            "generic_escalation": policy["generic_escalation"],
            "rows": rows,
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "title": "Deadlock detection, escalation, and the owner-intervention path",
        "trace_hash_comparison": {
            "barrier_resolution": run_a["barrier_resolution"],
            "different_seed": {
                "diverges": True,
                "seed": data["other_seed"],
                "sha256": data["other_seed_hash"],
            },
            "fan_out_cardinalities": data["fan_out_cardinalities"],
            "identical": True,
            "node_order": run_a["node_order"],
            "run_a_sha256": run_a["trace_hash"],
            "run_b_sha256": data["run_b"]["trace_hash"],
            "seed": data["seed"],
        },
        "unit_id": "TST-0290",
    }
    # Catalog output_schema (receipt.schema.json) is absent. test-receipt.schema.json
    # currently encodes TST-0128's pytest-collection contract, not deadlock policy.
    # G-1 does not schema-gate; probes re-run the classifier instead.
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
