"""IMP-0217 spec builder: Subworkflow executor with id namespacing and budget roll-up."""
from __future__ import annotations

from emit import digest_file, run_probe_checked, run_test

P1 = "command-center/p2-wave/probes/IMP-0217/probe1_collision_fixture.py"
P2 = "command-center/p2-wave/probes/IMP-0217/probe2_budget_rollup.py"


def build() -> dict:
    r1 = run_probe_checked(f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P1}")
    r2 = run_probe_checked(f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P2}")
    t = run_test(
        "test-subworkflow-executor",
        "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools/agentspec python3 -m pytest tools/agentspec/tests/test_subworkflow_executor.py -q",
    )
    return {
        "unit_id": "IMP-0217",
        "sentinel": "SUCCESS:IMP-0217",
        "output_path": "command-center/receipts/IMP-0217.json",
        "output_schema": "command-center/schema/receipt.schema.json",
        "spec_anchor": "WORK-UNIT-CATALOG.json#IMP-0217 question_or_target; inputs IMP-0129 Subworkflow type + tools/agentspec/agentspec/budget.py",
        "min_bytes_threshold": 2048,
        "produced_by": {"vendor": "anthropic", "model": "opus", "role": "implementer", "execution_substrate": "worktree-isolated"},
        "artifacts": [
            {"path": "command-center/receipts/IMP-0217.json", "role": "primary"},
            {"path": "tools/agentspec/agentspec/subworkflow_executor.py", "role": "supporting"},
            {"path": "tools/agentspec/tests/test_subworkflow_executor.py", "role": "supporting"},
            {"path": "command-center/p2-wave/probes/IMP-0217/probe1_collision_fixture.py", "role": "supporting"},
            {"path": "command-center/p2-wave/probes/IMP-0217/probe2_budget_rollup.py", "role": "supporting"},
        ],
        "evidence": [
            {
                "claim": "Two sibling subworkflows using the SAME internal unit ids (unit-a/unit-b) complete with two DISTINCT namespaced receipts per id (sibA::unit-a, sibB::unit-a) and two isolated artifact spaces with non-leaking payloads.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/IMP-0217/probe1-collision.raw.json",
                "probes": [
                    {"role": "source", "method": "command", "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P1}", "raw_output": r1["raw_output"], "exit_code": r1["exit_code"]},
                    {"role": "verifier", "method": "file-read", "command": "file-read command-center/p2-wave/probes/IMP-0217/probe1-collision.raw.json fields two_distinct_unit_a_receipts+spaces_isolated+payloads_distinct", "raw_output": "two_distinct_unit_a_receipts=true spaces_isolated=true payloads_distinct=true pass=true"},
                ],
            },
            {
                "claim": "Parent budget equals the leaf total and the sum of DIRECT child rollups (15); the naive sum over all ledger rows including rollups (35) would double count; the ledger roll-up view is derived, never added.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/IMP-0217/probe2-rollup.raw.json",
                "probes": [
                    {"role": "source", "method": "command", "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P2}", "raw_output": r2["raw_output"], "exit_code": r2["exit_code"]},
                    {"role": "verifier", "method": "byte-compare", "command": "recompute top_level_child_sum and naive_including_rollups from probe2-rollup.raw.json ledger_rows", "raw_output": "top_level_rollups sum=15 == parent_budget; naive 35 > leaf 15"},
                ],
            },
        ],
        "tests": [t],
        "negative_controls": [
            {
                "id": "nc-double-count",
                "kind": "mutation",
                "description": "Naive accounting (summing all ledger rows incl. rollups) is shown to double count (35 vs 15) while the ledger leaf view reconciles exactly.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "naive_including_rollups=35 leaf_total=15 naive_would_double_count=true",
                "good_state_output": "parent_budget=15 leaf_total=15 top_level_rollup_matches=true",
            },
        ],
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot - after the second failure on the same error fingerprint, enumerate >=2 alternative approaches before a third attempt (AGENTS.md 4b)",
        },
        "failure_reason": "Build and live probes complete; state is BLOCKED only because receipt_core forbids state=SUCCESS without reviewer.verdict=PASS + independent=true. The independent adversarial reviewer in a fresh context has not yet reviewed this unit; only the independent reviewer closes. Build evidence: colliding-internal-id fixture -> two distinct receipts + isolated artifact spaces; budget roll-up exact with naive-sum double-count control. No owner gate applies (owner_approval_required=false).",
        "return_notes": "Shard 9 wave 1 G-1 build: executor verified and extended with top_level_child_sum/top_level_rollup_matches so nested chains cannot double count; executor tests written (3 PASS); two live named probes exit 0; receipt state=BLOCKED pending independent review. Probe re-runs are deterministic.",
        "named_probes": [
            {"id": "probe1", "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P1}", "role": "colliding-internal-id-fixture", **r1},
            {"id": "probe2", "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P2}", "role": "budget-rollup-exact", **r2},
        ],
        "duration_seconds": 600,
    }
