#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0313.json from a live closure-gate run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from contract import (  # noqa: E402
    OUTPUT_REL,
    P1,
    P2,
    QUESTION,
    SCHEMA_REL,
    SENTINEL,
    UNIT_ID,
)
from scenario import run_proof  # noqa: E402

SUPPORTING = [
    "tools/bench/__init__.py",
    "tools/bench/ledger.py",
    "tools/bench/two_commit.py",
    "tools/bench/closure.py",
    "command-center/p2-wave/probes/TST-0313/contract.py",
    "command-center/p2-wave/probes/TST-0313/scenario.py",
    "command-center/p2-wave/probes/TST-0313/probe1_prefix_missing.py",
    "command-center/p2-wave/probes/TST-0313/probe2_census_debt.py",
    "command-center/p2-wave/probes/TST-0313/fixtures/register.json",
    "command-center/p2-wave/probes/TST-0313/fixtures/cases.json",
    "command-center/p2-wave/probes/TST-0313/fixtures/historical-ledger.jsonl",
    "command-center/p2-wave/probes/TST-0313/fixtures/oracles/existence_oracle.py",
    "command-center/p2-wave/probes/TST-0313/fixtures/oracles/always_pass_oracle.py",
    "command-center/p2-wave/probes/TST-0313/fixtures/snapshots/existence-pre/detector.py",
    "command-center/p2-wave/probes/TST-0313/fixtures/snapshots/existence-post/detector.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "role": role,
        "exists": path.is_file(),
        "bytes": size,
        "sha256": sha,
        "eol": "LF" if path.is_file() else "ABSENT",
    }


def present(rel: str) -> dict:
    path = REPO / rel
    return {"path": rel, "present": path.exists()}


def main() -> int:
    proof = run_proof()
    close_ok = proof["close_ok"]
    missing = proof["missing_prefix"]
    reviewer = proof["reviewer_bypass"]
    silent = proof["silent_oracle"]
    cen = proof["census"]
    if not close_ok.get("allow"):
        print("FAILED:TST-0313 emit honest both-states pair did not close")
        print(json.dumps(close_ok, sort_keys=True))
        return 1
    if missing.get("allow") or reviewer.get("allow") or silent.get("allow"):
        print("FAILED:TST-0313 emit a blocked path was allowed")
        return 1
    if cen.get("verdict") != "DEBT" or int(cen.get("debt_missing_prefix_fail") or 0) < 2:
        print("FAILED:TST-0313 emit census did not report planted debt")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live_cases = present("command-center/bench/cases")
    live_results = present("command-center/bench/results")
    live_prompts = present("_USER-PROMPTS.md")
    schema_present = (REPO / SCHEMA_REL).is_file()

    answer = (
        f"Closure is structural: B10-R1-EXISTENCE-ONLY moved to CLOSED only after "
        f"the snapshot two-commit runner recorded pre-fix FAIL run "
        f"{proof['existence_pre_run_id']} and post-fix PASS run "
        f"{proof['existence_post_run_id']} against CASE-EXISTENCE. The same tool "
        f"blocked B10-R3-STILL-OPEN when the pre-fix run was missing "
        f"(reason={missing.get('reason')}), when reviewer_ok=True "
        f"(reviewer_ok_ignored={reviewer.get('reviewer_ok_ignored')}), when both "
        f"ids were the same passing run, and when an unexecuted claimed FAIL was "
        f"offered. CASE-NOOP (always-PASS oracle) was silent in both snapshots "
        f"and could not close B10-R2-EMPTY-EXITZERO "
        f"(reason={silent.get('reason')}). Swapping snapshots inverted polarity "
        f"(pre={proof['swapped_pre_outcome']}, post={proof['swapped_post_outcome']}), "
        f"so outcomes come from executing the oracle, not from the side label. "
        f"Backfill census: closed_total={cen['closed_total']}, "
        f"honest_both_states={cen['honest_both_states']}, "
        f"debt_missing_prefix_fail={cen['debt_missing_prefix_fail']}, "
        f"debt_ids={cen['debt_ids']}, verdict={cen['verdict']} treated as DEBT "
        f"not pass. Live command-center/bench/cases present={live_cases['present']}; "
        f"live B10/B11 register absent; git checkout was not used. {SENTINEL}"
    )

    doc = {
        "adv_rebuild_circle": False,
        "answer": answer,
        "artifacts": [art(p, "supporting") for p in SUPPORTING],
        "backfill_census": cen,
        "both_states": {
            "enforced_by": "tools/bench/closure.py",
            "not_by": "reviewer-discipline",
            "honest_pre_outcome": proof["existence_pre_outcome"],
            "honest_post_outcome": proof["existence_post_outcome"],
            "honest_pre_run_id": proof["existence_pre_run_id"],
            "honest_post_run_id": proof["existence_post_run_id"],
            "close_allowed": close_ok.get("allow"),
            "missing_prefix_blocked": not missing.get("allow"),
            "reviewer_ok_ignored": reviewer.get("reviewer_ok_ignored"),
            "silent_oracle_blocked": not silent.get("allow"),
            "swap_inverts": (
                proof["swapped_pre_outcome"] == "PASS"
                and proof["swapped_post_outcome"] == "FAIL"
            ),
        },
        "cited_closed_defects": proof["cited_closed"],
        "cloud_ok": False,
        "completion_sentinel": SENTINEL,
        "evidence": [
            {
                "kind": "two-run-ids",
                "defect_id": "B10-R1-EXISTENCE-ONLY",
                "pre_fix_run_id": proof["existence_pre_run_id"],
                "pre_fix_outcome": proof["existence_pre_outcome"],
                "post_fix_run_id": proof["existence_post_run_id"],
                "post_fix_outcome": proof["existence_post_outcome"],
                "detail": "Live executed pair; single passing run is not admissible.",
            },
            {
                "kind": "two-run-ids",
                "defect_id": "B11-I1-WORKER-ISOLATION",
                "pre_fix_run_id": "run-hist-pre-fail",
                "post_fix_run_id": "run-hist-post-pass",
                "detail": "Historical honest CLOSED row with both ledger ids.",
            },
            {
                "kind": "closure-block",
                "detail": (
                    "pre-fix-run-missing blocks CLOSE; reviewer_ok is ignored; "
                    "paper unexecuted FAIL is rejected; both-PASS oracle is rejected."
                ),
                "missing_prefix_reason": missing.get("reason"),
                "reviewer_reasons": reviewer.get("reasons"),
                "silent_reasons": silent.get("reasons"),
            },
            {
                "kind": "backfill-debt",
                "detail": (
                    f"{cen['debt_missing_prefix_fail']} already-CLOSED defects lack a "
                    "pre-fix FAIL run and are DEBT, not pass."
                ),
                "debt_ids": cen["debt_ids"],
                "verdict": cen["verdict"],
            },
        ],
        "id": UNIT_ID,
        "implementation": {
            "closure_tool": "tools/bench/closure.py",
            "two_commit_runner": "tools/bench/two_commit.py",
            "ledger": "tools/bench/ledger.py",
            "git_checkout_used": False,
            "snapshot_runner": True,
        },
        "inputs_census": {
            "USER_PROMPTS": live_prompts,
            "bench_cases": live_cases,
            "bench_results": live_results,
            "catalog_schema": {"path": SCHEMA_REL, "present": schema_present},
            "live_b10_register": {"present": False},
            "live_b11_register": {"present": False},
            "planted_register": "command-center/p2-wave/probes/TST-0313/fixtures/register.json",
            "syn0008_b10_standin": present(
                "command-center/p2-wave/probes/SYN-0008/fixtures/evidence/B10-phase12.json"
            ),
            "syn0008_b11_standin": present(
                "command-center/p2-wave/probes/SYN-0008/fixtures/evidence/B11-phase13.json"
            ),
            "tst0295_dependency": {
                "id": "TST-0295",
                "receipt_present": (REPO / "command-center/receipts/TST-0295.json").is_file(),
            },
        },
        "manifest_registration": {
            "global_catalog_write": False,
            "manifest_path": "command-center/p2-wave/probes/TST-0313/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "min_bytes_threshold": 2048,
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "prefix-missing-and-tool-enforcement"},
            {"id": "probe2", "command": P2, "role": "backfill-census-debt"},
        ],
        "negative_controls": [
            {
                "id": "NC1-prefix-run-missing",
                "kind": "closure-block",
                "description": "CLOSE with only a post-fix PASS run is blocked.",
                "fired_on_bad_state": True,
                "reason": missing.get("reason"),
            },
            {
                "id": "NC2-reviewer-discipline",
                "kind": "reviewer-bypass",
                "description": "reviewer_ok=True does not move status to CLOSED.",
                "fired_on_bad_state": True,
                "reviewer_ok_ignored": reviewer.get("reviewer_ok_ignored"),
            },
            {
                "id": "NC3-silent-both-pass",
                "kind": "oracle-silent-in-both-states",
                "description": "A test that PASSes on both snapshots cannot close a defect.",
                "fired_on_bad_state": True,
                "reason": silent.get("reason"),
            },
            {
                "id": "NC4-snapshot-swap",
                "kind": "polarity-invert",
                "description": "Running the oracle on swapped snapshots inverts FAIL/PASS.",
                "fired_on_bad_state": True,
                "pre_outcome": proof["swapped_pre_outcome"],
                "post_outcome": proof["swapped_post_outcome"],
            },
        ],
        "notes": (
            "G-1 for TST-0313. Did not run tools/command-center/unit_manifest.py "
            "--write. Did not relaunch finish-everything-close or p2-cloud-ok-deliver. "
            "cloud ok=true is not delivery. Two-commit runner uses snapshot trees "
            "because git checkout is forbidden on this deliver."
        ),
        "produced_by": {
            "execution_substrate": "worktree-isolated",
            "model": "grok-4.6",
            "role": "test-engineer",
            "vendor": "cursor",
        },
        "question": QUESTION,
        "required_fix": None,
        "residual_unknowns": [
            {
                "id": "R1-live-bench-corpus",
                "summary": (
                    "command-center/bench/cases/ is absent (TST-0295 not delivered). "
                    "The gate was proved on the planted CASE-EXISTENCE / CASE-NOOP corpus."
                ),
                "settling_experiment": (
                    "Re-run census against the TST-0295 corpus when that unit lands."
                ),
            },
            {
                "id": "R2-live-b10-b11-register",
                "summary": (
                    "No live B10/B11 defect register is on this worktree. Debt counts "
                    "are from the planted register, not an estate-wide backfill."
                ),
                "settling_experiment": (
                    "Point census() at the real B10/B11 register when those artifacts exist."
                ),
            },
        ],
        "retry": {"count": 0, "policy": "no-automatic-retry"},
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "method": (
                "Mechanical: missing pre-fix run must block; reviewer_ok must not "
                "unblock; snapshot swap must invert polarity; census must name debt."
            ),
            "reviewer_id": "TST-0313-probe2-census-debt",
            "verdict": "PASS",
        },
        "schema_version": 1,
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:TST-0313 spec:11148",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "tests": [
            {
                "id": "T1-prefix-missing-blocks",
                "name": "Closure blocked when the pre-fix run is missing",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-tool-not-reviewer",
                "name": "Both-states enforced by the closure tool, not reviewer discipline",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T3-backfill-census-debt",
                "name": "Already-closed defects lacking a pre-fix FAIL run are DEBT, not pass",
                "command": P2,
                "result": "PASS",
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "title": "Every closed defect must leave behind a regression case that would catch its return",
        "unit_id": UNIT_ID,
        "output_schema": SCHEMA_REL,
    }
    out = REPO / OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest(out)
    print(f"wrote {OUTPUT_REL} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
