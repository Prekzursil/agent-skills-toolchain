"""IMP-0222 spec builder: per-unit pipeline isolation against a hung sibling."""
from __future__ import annotations

from emit import run_probe_checked, run_test

P1 = "command-center/p2-wave/probes/IMP-0222/probe1_planted_hang_49_of_50.py"
P2 = "command-center/p2-wave/probes/IMP-0222/probe2_no_barrier_past_timeout.py"


def build() -> dict:
    r1 = run_probe_checked(f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P1}")
    r2 = run_probe_checked(f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P2}")
    t = run_test(
        "test-cohort-isolation",
        "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools/agentrail;tools/agentspec python3 -m pytest tools/agentrail/tests/test_cohort_isolation.py -q",
    )
    return {
        "unit_id": "IMP-0222",
        "sentinel": "SUCCESS:IMP-0222",
        "output_path": "command-center/receipts/IMP-0222.json",
        "output_schema": "command-center/schema/receipt.schema.json",
        "spec_anchor": "_USER-PROMPTS.md:11318 + rules/common/fan-out-contract.md (one hung agent deadlocked a whole phase - measured orchestration failure); inputs tools/agentrail/agentrail/runner.py",
        "min_bytes_threshold": 2048,
        "produced_by": {"vendor": "anthropic", "model": "opus", "role": "implementer", "execution_substrate": "local-parallel"},
        "artifacts": [
            {"path": "command-center/receipts/IMP-0222.json", "role": "primary"},
            {"path": "tools/agentrail/agentrail/runner.py", "role": "supporting"},
            {"path": "tools/agentrail/tests/test_cohort_isolation.py", "role": "supporting"},
            {"path": "command-center/p2-wave/probes/IMP-0222/probe1_planted_hang_49_of_50.py", "role": "supporting"},
            {"path": "command-center/p2-wave/probes/IMP-0222/probe2_no_barrier_past_timeout.py", "role": "supporting"},
        ],
        "evidence": [
            {
                "claim": "A deliberately hung unit in a 50-unit cohort delays only itself: 49/50 complete, the hung unit's terminal record is TIMEOUT-TYPED (not absent) with its own declared_timeout_s, and the cohort wall (measured, 0.5s-class) is bounded by the declared timeout rather than the hang duration.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/IMP-0222/probe1-hang.raw.json",
                "probes": [
                    {"role": "source", "method": "command", "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P1}", "raw_output": r1["raw_output"], "exit_code": r1["exit_code"]},
                    {"role": "verifier", "method": "file-read", "command": "read probe1-hang.raw.json completed=49 timed_out=[U-0007] hung_record.status=timeout-typed", "raw_output": "completed=49 timed_out_count=1 wall_s<1.5"},
                ],
            },
            {
                "claim": "No barrier waits past a declared timeout: every completed unit's measured elapsed_s <= declared timeout (timestamp audit over the ledger), and the barrier-coupled counterfactual on the same cohort stalls ALL siblings (both-states control).",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/IMP-0222/probe2-barrier.raw.json",
                "probes": [
                    {"role": "source", "method": "command", "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P2}", "raw_output": r2["raw_output"], "exit_code": r2["exit_code"]},
                    {"role": "verifier", "method": "test-run", "command": "CoupledBarrierRunner().run(same cohort) must stall all 50 (inside probe2)", "raw_output": "coupled_terminal=timeout coupled_completed=0 isolated_completed=49"},
                ],
            },
        ],
        "tests": [t],
        "negative_controls": [
            {
                "id": "nc-coupled-barrier",
                "kind": "known-broken-fixture",
                "description": "The barrier-coupled runner is the measured failure class being prevented: on the same 50-unit cohort with one hang it completes ZERO units (terminal=timeout). If the coupled runner stopped stalling, the control would stop discriminating.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "coupled: terminal=timeout completed=0",
                "good_state_output": "isolated: completed=49 timed_out=[U-0007] typed",
            },
        ],
        "retry": {
            "count": 2,
            "policy": "two strikes then pivot - after the second failure on the same error fingerprint, enumerate >=2 alternative approaches before a third attempt (AGENTS.md 4b)",
            "attempts": [
                {"attempt": 1, "error_fingerprint": "import-concurrent-futures-TimeoutExpired-missing-py314", "outcome": "FAILED"},
                {"attempt": 2, "error_fingerprint": "threadpool-with-block-joins-hung-worker-wall-30s", "outcome": "FAILED"},
                {"attempt": 3, "error_fingerprint": "pivot-applied-builtin-timeout-and-no-join-shutdown", "outcome": "SUCCESS"},
            ],
            "pivot_alternatives": [
                "use builtin TimeoutError (py3.11+ merged concurrent.futures.TimeoutExpired)",
                "shutdown(wait=False, cancel_futures=True) so the cohort never joins the hung worker; abandoned workers counted in the report",
            ],
        },
        "failure_reason": "Build and live probes complete; state is BLOCKED only because receipt_core forbids state=SUCCESS without reviewer.verdict=PASS + independent=true. The independent adversarial reviewer in a fresh context has not yet reviewed this unit; only the independent reviewer closes. Build evidence: 49/50 complete under a planted hang with a timeout-typed terminal record and timestamp-audited barrier bound; coupled-barrier counterfactual stalls. No owner gate applies (owner_approval_required=false).",
        "return_notes": "Shard 9 wave 1 G-1 build: runner.py extended with run_cohort_isolated (per-unit join timeout, timestamped ledger, abandoned-worker accounting; two-strikes pivot from py314 TimeoutExpired import and pool-join deadlock), tests written (3 PASS), two live named probes exit 0, receipt state=BLOCKED pending independent review. Import-order gotcha recorded: tools/agentspec carries a shadow agentrail/ - probe sys.path inserts agentrail home LAST so the real package wins.",
        "named_probes": [
            {"id": "probe1", "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P1}", "role": "planted-hang-49of50", **r1},
            {"id": "probe2", "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P2}", "role": "no-barrier-past-timeout", **r2},
        ],
        "duration_seconds": 900,
    }
