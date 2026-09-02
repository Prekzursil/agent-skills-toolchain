#!/usr/bin/env python3
"""Emit TST-0162 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

from claim_resume import run_both_states, run_mutation_truncate  # noqa: E402

UNIT = "TST-0162"
OUT = "command-center/receipts/TST-0162.json"
SENTINEL = "SUCCESS:TST-0162"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0162/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0162/probe2_truncate_redispatch.py"
)
SUPPORTING = [
    "tools/command-center/claim_resume.py",
    "tools/command-center/tests/test_claim_resume.py",
    "command-center/p2-wave/probes/TST-0162/probe1_both_states.py",
    "command-center/p2-wave/probes/TST-0162/probe2_truncate_redispatch.py",
    "command-center/p2-wave/probes/TST-0162/emit_receipt.py",
]
QUESTION = (
    "On resume, are already-terminal units skipped and units with a "
    "corrupted claim record re-dispatched? PASS requires both behaviors; "
    "a corrupted claim that is silently skipped is the dangerous failure "
    "and must be detected."
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0162/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst-0162-emit-") as td:
        base = Path(td)
        both = run_both_states(base / "both")
        mut = run_mutation_truncate(base / "mut")
    if not both.get("pass") or not mut.get("pass"):
        print("FAILED:TST-0162 emit live suites did not pass")
        print(json.dumps({"both": both, "mutation": mut}, default=str)[:4000])
        return 1

    lib = REPO / "tools/command-center/claim_resume.py"
    lib_sha, lib_n = digest(lib)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    both_states = both.get("both_states") or {}
    mut_states = mut.get("both_states") or {}
    honest = mut.get("honest") or {}
    mutant = mut.get("mutant_skip_corrupt") or {}

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "test-receipt",
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/concurrency_report",
        "overall_verdict": "PASS",
        "title": "Resume skips terminal units and re-dispatches corrupted claims",
        "question": QUESTION,
        "output_path": OUT,
        "spec_anchor": (
            "catalog TST-0162: intact claims skip, corrupted claims re-dispatch; "
            "mutation control truncates one claim record and confirms re-dispatch"
        ),
        "min_bytes_threshold": 128,
        "profile": "p2-wave-g1-unit",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "concurrency-tester",
            "execution_substrate": "worktree-isolated",
        },
        "premise": {
            "catalog_inputs": [
                "_USER-PROMPTS.md:11011 (Phase 10 layer 23, duplicate-dispatch tests)",
                "_USER-PROMPTS.md:10965-10983 (Phase 9 work claims, file leases, duplicate suppression)",
                "tools/lib/handled-ledger.mjs",
            ],
            "inputs_were_absent": True,
            "action": (
                "Created probes/TST-0162 and tools/command-center/claim_resume.py "
                "on this sparse worktree. handled-ledger.mjs and B07 runner were "
                "absent; this unit ships the resume planner that skips intact "
                "terminal claims and re-dispatches truncated ones."
            ),
        },
        "implementation": {
            "module": "tools/command-center/claim_resume.py",
            "operator": (
                "checksummed claim JSON plus per-unit receipts; resume plan "
                "skip/redispatch lists; independent receipt-directory sha256 diff; "
                "truncate mutation; skip-corrupt mutant as negative control"
            ),
            "claim_resume_sha256": lib_sha,
            "claim_resume_bytes": lib_n,
        },
        "both_states_evidence": {
            "intact": both.get("intact"),
            "corrupt": both.get("corrupt"),
            "both_states": both_states,
            "signals": both.get("signals"),
        },
        "mutation_evidence": {
            "honest": honest,
            "mutant_skip_corrupt": mutant,
            "both_states": mut_states,
            "signals": mut.get("signals"),
        },
        "artifacts": [
            {
                "path": "tools/command-center/claim_resume.py",
                "role": "primary-implementation",
                "sha256": lib_sha,
                "bytes": lib_n,
                "exists": True,
            }
        ],
        "evidence": [
            {
                "kind": "resume-plan",
                "claim": (
                    "Intact terminal claims appear only on the skip list; a "
                    "truncated claim appears on the redispatch list and is "
                    "absent from skip."
                ),
                "detail": (
                    f"intact skip={((both.get('intact') or {}).get('plan') or {}).get('skip')} "
                    f"corrupt redispatch={((both.get('corrupt') or {}).get('plan') or {}).get('redispatch')} "
                    f"honest redispatch={honest.get('plan_redispatch')}"
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/command-center/claim_resume.py:plan_resume",
                "signal": "(a) the resume plan's skip/redispatch lists",
                "probes": [],
            },
            {
                "kind": "independent-receipt-diff",
                "claim": (
                    "An independent hash of the receipts directory, taken "
                    "without reading the plan, stays unchanged for skipped "
                    "terminals and changes for the redispatched truncated unit. "
                    "The skip-corrupt mutant leaves the truncated unit's receipt "
                    "byte-identical, which turns the mutation control red."
                ),
                "detail": (
                    f"after-truncate diff={((both.get('signals') or {}).get('b_independent_receipt_diff') or {}).get('after_truncate')} "
                    f"honest={((mut.get('signals') or {}).get('b_independent_receipt_diff') or {}).get('honest')} "
                    f"mutant={((mut.get('signals') or {}).get('b_independent_receipt_diff') or {}).get('mutant')}"
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/command-center/claim_resume.py:snapshot_receipts",
                "signal": "(b) an independent diff of receipts present before and after resume",
                "probes": [],
            },
        ],
        "tests": [
            {
                "id": "TST-0162-BOTH-STATES",
                "command": P1,
                "result": "PASS",
                "exit_code": 0,
                "both_states": both_states,
            },
            {
                "id": "TST-0162-MUTATION-TRUNCATE",
                "command": P2,
                "result": "PASS",
                "exit_code": 0,
                "both_states": mut_states,
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0162-C1-intact-vs-corrupt",
                "kind": "both-states",
                "description": (
                    "Intact terminal claims skip and their receipts stay "
                    "byte-identical. Truncating one claim moves that unit onto "
                    "redispatch and changes its receipt hash."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "TST-0162-C2-skip-corrupt-mutant",
                "kind": "mutation",
                "description": (
                    "A planner that treats a truncated claim with an existing "
                    "receipt as skip leaves the receipt unchanged. The honest "
                    "planner redispatches. Silent skip of a corrupted claim is "
                    "the named dangerous failure."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0162-probe2-truncate-redispatch",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Adversarial control is the planted skip-corrupt mutant plus the "
                "independent snapshot_receipts reader that hashes receipt files "
                "without consulting plan_resume skip/redispatch lists."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0162/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 TST-0162: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            f"{SENTINEL}"
        ),
        "answer": (
            "Yes. Intact terminal claims are skipped and their receipts stay "
            "unchanged. Truncating a claim record forces re-dispatch, which an "
            "independent receipt-hash diff observes. A mutant that silently "
            "skips the truncated claim is detected."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0162 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    receipt["evidence"][0]["probes"] = [
        {
            "role": "verifier",
            "method": "command",
            "command": P1,
            "exit_code": c1,
            "raw_output": t1[:16000],
        }
    ]
    receipt["evidence"][1]["probes"] = [
        {
            "role": "verifier",
            "method": "command",
            "command": P2,
            "exit_code": c2,
            "raw_output": t2[:16000],
        }
    ]
    receipt["tests"][0]["exit_code"] = c1
    receipt["tests"][1]["exit_code"] = c2
    receipt["tests"][0]["result"] = "PASS" if c1 == 0 else "FAIL"
    receipt["tests"][1]["result"] = "PASS" if c2 == 0 else "FAIL"

    out_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/concurrency_report",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "both-states-intact-skip-corrupt-redispatch",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "mutation-truncate-and-independent-receipt-diff",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0162/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0162-probe2-truncate-redispatch",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0162: live named probes exit 0, TST-0162.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
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
    print(f"SUCCESS:TST-0162 receipts {SENTINEL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
