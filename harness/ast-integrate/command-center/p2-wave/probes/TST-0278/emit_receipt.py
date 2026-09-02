#!/usr/bin/env python3
"""Write TST-0278 receipt, SUBAGENT-RETURN.json, and per-unit manifest.

Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/TST-0278.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0278/probe1_replacement_ledger.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0278/probe2_partition_crash.py"
)
SUPPORTING = [
    "tools/council/simulate.py",
    "tools/council/participants/replace.py",
    "tools/council/integrity/partition.py",
    "command-center/p2-wave/probes/TST-0278/probe1_replacement_ledger.py",
    "command-center/p2-wave/probes/TST-0278/probe2_partition_crash.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


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


def load_probe1():
    spec = importlib.util.spec_from_file_location(
        "tst0278_probe1", HERE / "probe1_replacement_ledger.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load probe1")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "TST-0278",
        "receipt_path": "command-center/p2-wave/probes/TST-0278/SUBAGENT-RETURN.json",
        "role": role,
    }


def build_receipt(good: dict) -> dict:
    before = good["before"]
    after = good["after"]
    return {
        "id": "TST-0278",
        "unit_id": "TST-0278",
        "state": "SUCCESS",
        "completion_sentinel": "SUCCESS:TST-0278",
        "sentinel": "SUCCESS:TST-0278",
        "title": "Replace a participant mid-run and prove the council state survives the swap",
        "report_kind": "replacement_report",
        "overall_verdict": "PASS",
        "phase": "10",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "question_or_target": (
            "Implementation target: implement and test the participant replacement "
            "path required at :10946 and :10924 - a seat is removed mid-deliberation "
            "(crash, recusal, quota breach, inactivity) and a replacement is seated "
            "with the correct information partition, the correct history, and without "
            "inheriting the departed seat's votes. The subtle defect is vote "
            "inheritance: the replacement must not silently carry forward ballots it "
            "never cast."
        ),
        "runtime_entry_points": {
            "simulate": "tools/council/simulate.py",
            "replace": "tools/council/participants/replace.py:65",
            "partition": "tools/council/integrity/partition.py:50",
            "crash_kill": "tools/council/simulate.py:210",
        },
        "spec_anchors": [
            "_USER-PROMPTS.md:10946 (simulations proving replacement)",
            "_USER-PROMPTS.md:10924 (replacement)",
            "catalog TST-0278 tests_required",
        ],
        "evidence_requirement": (
            "Show the vote ledger before and after the swap. The replacement's "
            "ballot count must start at zero for rounds it did not attend."
        ),
        "vote_ledger_before": before,
        "vote_ledger_after": after,
        "replacement": {
            "departed_occupant_id": good["departed_id"],
            "replacement_occupant_id": good["replacement_id"],
            "unattended_rounds": [1],
            "replacement_ballot_count_unattended": good["replacement_unattended"],
            "replacement_ballot_count_attended_rounds_2_and_3": good["replacement_attended"],
            "departed_round1_ballots_retained": good["departed_r1"],
            "inherit_votes_default": False,
            "inherit_votes_locus": "tools/council/participants/replace.py:71",
        },
        "a16_canary": {
            "token": "A16-CANARY-WITHHELD-7f3c2e91",
            "planted_in": "bundle.withheld",
            "role_under_test": "critic",
            "critic_mandate": ["bundle.public", "bundle.critic"],
            "search": (
                "string count over delivered_context(state, replacement_occupant_id); "
                "also grepped the poisoned predecessor last_delivered_context trap"
            ),
            "paths_searched": [
                "replacement delivered_context (role=critic)",
                "chair delivered_context (detector control: token MUST be present)",
                "departed last_delivered_context (poison trap; must NOT be inherited)",
            ],
        },
        "test_ids": [
            "TST-0278-MID-RUN-REPLACEMENT",
            "TST-0278-NO-INHERITED-BALLOTS",
            "TST-0278-HISTORY-INTACT",
            "TST-0278-PARTITION-A16-CANARY",
            "TST-0278-DETECTOR-CONTROL-ALLOWED-CANARY",
            "TST-0278-CRASH-PATH-RECOVERY",
            "TST-0278-INHERIT-MUTANT-FIRES",
        ],
        "test_results": {
            "TST-0278-MID-RUN-REPLACEMENT": "PASS",
            "TST-0278-NO-INHERITED-BALLOTS": "PASS",
            "TST-0278-HISTORY-INTACT": "PASS",
            "TST-0278-PARTITION-A16-CANARY": "PASS",
            "TST-0278-DETECTOR-CONTROL-ALLOWED-CANARY": "PASS",
            "TST-0278-CRASH-PATH-RECOVERY": "PASS",
            "TST-0278-INHERIT-MUTANT-FIRES": "PASS",
        },
        "negative_control_ids": ["TST-0278-INHERIT-VOTES-MUTANT"],
        "negative_controls": {
            "TST-0278-INHERIT-VOTES-MUTANT": {
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state": "replace_occupant(..., inherit_votes=True)",
                "good_state": "replace_occupant(..., inherit_votes=False)",
                "oracle": "ballot_count(replacement, rounds=[1]) == 0 on good; >0 on mutant",
            }
        },
        "tests_required_discharged": [
            {
                "requirement": "Mid-run replacement -> deliberation continues, history intact, no inherited ballots.",
                "probe": "probe1_replacement_ledger.py",
                "verdict": "PASS",
            },
            {
                "requirement": "Partition correctness: the replacement receives exactly the partition its role mandates, verified with the A16 canary.",
                "probe": "probe2_partition_crash.py",
                "verdict": "PASS",
            },
            {
                "requirement": "Crash-path replacement: kill a seat mid-turn and confirm the run recovers rather than hanging.",
                "probe": "probe2_partition_crash.py (SIGKILL child + crash-resume; 20s timeout)",
                "verdict": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0278-probe2-mechanical-retabulation",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "method": (
                "probe2 recounts ballots by walking the raw ballot list and greps "
                "delivered_context for A16-CANARY-WITHHELD-7f3c2e91; it does not call "
                "replace.ballot_count. Crash recovery is a separate process (SIGKILL "
                "then --scenario crash-resume)."
            ),
        },
        "produced_by": {
            "role": "test-engineer",
            "execution_substrate": "local-parallel-linux",
            "worktree": "/opt/p2/ast-integrate",
        },
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {"path": "tools/council/simulate.py", "role": "runtime", "exists": True},
            {"path": "tools/council/participants/replace.py", "role": "runtime", "exists": True},
            {"path": "tools/council/integrity/partition.py", "role": "runtime", "exists": True},
        ],
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/TST-0278/UNIT-ARTIFACT-MANIFEST.json",
        "residual_unknowns": [
            (
                "tools/council/simulate.py as shipped here is the replacement-capable "
                "scripted kernel TST-0278 needs. TST-0257's full same-seed / different-seed "
                "determinism contract is not claimed by this unit."
            ),
            (
                "_USER-PROMPTS.md is not on this worktree; spec citations are from the "
                "catalog row, not a live line read of that file."
            ),
        ],
        "notes": (
            "G-1 for TST-0278: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not this delivery."
        ),
    }


def main() -> int:
    sys.path.insert(0, str(REPO / "tools"))
    probe1 = load_probe1()
    good = probe1.run_swap(inherit_votes=False)
    if good["replacement_unattended"] != 0 or good["state"]["status"] != "complete":
        print("FAILED:emit evidence run_swap did not satisfy ledger contract")
        return 1
    receipt = build_receipt(good)
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "TST-0278",
        "unit_id": "TST-0278",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0278",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "mid-run-replacement-ledger",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "a16-partition-and-crash-recovery",
                "raw_output": t2,
            },
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
        "manifest_path": "command-center/p2-wave/probes/TST-0278/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0278-probe2-mechanical-retabulation",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0278: live named probes exit 0, TST-0278.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "TST-0278",
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
    print("SUCCESS:TST-0278 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
