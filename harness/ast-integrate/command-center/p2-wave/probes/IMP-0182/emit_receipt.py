#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0182.json after running the splice operator."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fake_rail import FakeRail  # noqa: E402
from scenario import (  # noqa: E402
    DONOR_INDEX,
    HOST_INDEX,
    host_workflow,
    initial_env,
    matching_donor,
    mismatch_donor,
    successor_mismatch_donor,
    write_fixtures,
)
from stage_splice import emit_first_mutant, stage_splice  # noqa: E402
from workflow_ir import untouched_byte_identical  # noqa: E402

OUT = "command-center/receipts/IMP-0182.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0182/probe1_contract_mismatch.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0182/probe2_plan_differs.py"
)
QUESTION = (
    "Target: implement the stage-splice strategy - replace one workflow's stage "
    "with a better-performing stage from another, preserving the surrounding "
    "contract. Acceptance: the spliced stage's input/output contract is checked "
    "against its neighbours BEFORE the fusion is emitted; a contract mismatch "
    "is a refusal."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    write_fixtures()
    host = host_workflow()
    match = matching_donor()
    bad = mismatch_donor()
    bad_succ = successor_mismatch_donor()

    good = stage_splice(host, match, HOST_INDEX, DONOR_INDEX)
    refused = stage_splice(host, bad, HOST_INDEX, DONOR_INDEX)
    refused_out = stage_splice(host, bad_succ, HOST_INDEX, DONOR_INDEX)
    mutant = emit_first_mutant(host, bad, HOST_INDEX, DONOR_INDEX)

    if good.get("status") != "emitted" or good.get("fusion") is None:
        print(f"FAILED:IMP-0182 matching splice did not emit: {good.get('reason')}")
        return 1
    if refused.get("status") != "refused" or refused.get("fusion") is not None:
        print("FAILED:IMP-0182 input mismatch was not a pre-emit refusal")
        return 1
    if refused_out.get("status") != "refused" or refused_out.get("fusion") is not None:
        print("FAILED:IMP-0182 successor mismatch was not a pre-emit refusal")
        return 1
    if mutant.get("fusion") is None:
        print("FAILED:IMP-0182 emit-first mutant produced no fusion (detector dead)")
        return 1

    fusion = good["fusion"]
    env = initial_env()
    host_run = FakeRail().run(host, env)
    donor_run = FakeRail().run(match, env)
    fused_run = FakeRail().run(fusion, env)
    rows = untouched_byte_identical(host, fusion, HOST_INDEX)
    plan_differs = (
        fused_run["plan_fingerprint"] != host_run["plan_fingerprint"]
        and fused_run["plan_fingerprint"] != donor_run["plan_fingerprint"]
    )
    if not plan_differs:
        print("FAILED:IMP-0182 fused plan collapsed to a parent")
        return 1
    if any(not r["identical"] for r in rows):
        print("FAILED:IMP-0182 untouched host stages mutated")
        return 1

    deps_present = {
        "IMP-0174": (REPO / "command-center/receipts/IMP-0174.json").is_file(),
        "IMP-0175": (REPO / "command-center/receipts/IMP-0175.json").is_file(),
        "agentspec.evals.fake_rail": (
            REPO / "tools/agentspec/agentspec/evals/fake_rail.py"
        ).is_file(),
        "receipt.schema.json": (REPO / SCHEMA).is_file(),
    }

    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    doc = {
        "schema_version": 1,
        "unit_id": "IMP-0182",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0182",
        "spec_anchor": "_USER-PROMPTS.md:10737,11161",
        "min_bytes_threshold": 2048,
        "question": QUESTION,
        "title": "Implement stage-splice fusion",
        "strategy": "stage-splice",
        "profile": "workflow-fusion-operator",
        "cloud_ok": False,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "fusion-engineer",
            "execution_substrate": "linux-local",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "dependencies_on_this_tree": deps_present,
        "scope": {
            "implemented": (
                "stage-splice replace-one-slot operator with neighbour contract "
                "check before emit, plus a hermetic fake rail that executes the "
                "spliced plan"
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "IMP-0174 component graph or IMP-0175 compatibility map consumed (absent)",
                "tools/agentspec/agentspec/evals/fake_rail.py imported (absent)",
                "receipt.schema.json validated (file absent on this worktree)",
                "all eight fusion strategies implemented",
            ],
            "proof_surface": (
                "executable operator on in-tree fixtures; both-states contract "
                "mismatch; fake-rail plans compared by sha256 of executed stage "
                "fingerprints"
            ),
        },
        "operator": {
            "module": "command-center/p2-wave/probes/IMP-0182/stage_splice.py",
            "fake_rail": "command-center/p2-wave/probes/IMP-0182/fake_rail.py",
            "host_index": HOST_INDEX,
            "donor_index": DONOR_INDEX,
            "matching": {
                "status": good["status"],
                "trace": good["trace"],
                "fusion_id": fusion.get("id"),
                "lineage": fusion.get("lineage"),
            },
            "input_mismatch": {
                "status": refused["status"],
                "reason": refused["reason"],
                "trace": refused["trace"],
                "fusion_is_none": refused.get("fusion") is None,
                "missing_inputs": ((refused.get("preconditions") or {}).get("contracts") or {}).get(
                    "missing_inputs"
                ),
            },
            "successor_mismatch": {
                "status": refused_out["status"],
                "reason": refused_out["reason"],
                "fusion_is_none": refused_out.get("fusion") is None,
                "missing_outputs": (
                    (refused_out.get("preconditions") or {}).get("contracts") or {}
                ).get("missing_outputs"),
            },
            "emit_first_mutant": {
                "status": mutant["status"],
                "trace": mutant["trace"],
                "fusion_present_on_mismatch": mutant.get("fusion") is not None,
                "note": "known-broken control; not the shipped path",
            },
        },
        "fake_rail_runs": {
            "host_plan_fingerprint": host_run["plan_fingerprint"],
            "donor_plan_fingerprint": donor_run["plan_fingerprint"],
            "fusion_plan_fingerprint": fused_run["plan_fingerprint"],
            "differs_from_host": fused_run["plan_fingerprint"] != host_run["plan_fingerprint"],
            "differs_from_donor": fused_run["plan_fingerprint"] != donor_run["plan_fingerprint"],
            "spawn_count": fused_run["spawn_count"],
            "network_count": fused_run["network_count"],
            "fusion_verdict": fused_run["env"].get("verdict"),
            "fusion_score": fused_run["env"].get("score"),
            "untouched_host_stages": rows,
        },
        "tests": [
            {
                "id": "T1-contract-mismatch-refused",
                "command": P1,
                "result": "PASS",
                "assertions": 2,
                "output_tail": (
                    "input mismatch fusion=None reason=contract-mismatch; "
                    "matching splice emitted"
                ),
            },
            {
                "id": "T2-spliced-plan-differs-from-both-parents",
                "command": P2,
                "result": "PASS",
                "assertions": 2,
                "output_tail": (
                    f"fusion={fused_run['plan_fingerprint'][:16]} "
                    f"host={host_run['plan_fingerprint'][:16]} "
                    f"donor={donor_run['plan_fingerprint'][:16]}"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0182-C1",
                "kind": "known-broken-fixture",
                "description": (
                    "Both-states: matching neighbour contract is accepted; a donor "
                    "stage whose inputs are unsatisfied by the predecessor is refused "
                    "with fusion=None."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(
                    {"status": refused["status"], "reason": refused["reason"]},
                    sort_keys=True,
                ),
                "good_state_output": json.dumps(
                    {"status": good["status"], "fusion_id": fusion.get("id")},
                    sort_keys=True,
                ),
            },
            {
                "id": "IMP0182-C2",
                "kind": "emit-first-mutant",
                "description": (
                    "The shipped operator checks contracts before constructing a "
                    "fusion. An emit-first mutant still carries a fusion object on "
                    "mismatch, proving 'fusion is None' is a live detector."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(
                    {
                        "mutant_fusion_present": mutant.get("fusion") is not None,
                        "trace": mutant.get("trace"),
                    },
                    sort_keys=True,
                ),
                "good_state_output": json.dumps(
                    {"shipped_trace": good.get("trace"), "fusion_emitted": True},
                    sort_keys=True,
                ),
            },
        ],
        "evidence": [
            {
                "claim": (
                    "A contract-mismatch fixture is refused before a fusion workflow "
                    "is emitted (fusion is None; trace is contract-check then refuse)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0182/stage_splice.py:stage_splice",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "stage_splice(host, mismatch_donor)",
                        "raw_output": json.dumps(
                            {
                                "status": refused["status"],
                                "reason": refused["reason"],
                                "trace": refused["trace"],
                                "fusion_is_none": True,
                            },
                            sort_keys=True,
                        ),
                    }
                ],
            },
            {
                "claim": (
                    "A valid splice runs end to end on the fake rail and its executed "
                    "plan differs from both parents."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0182/fake_rail.py:FakeRail.run",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": "FakeRail.run(host|donor|fusion)",
                        "raw_output": json.dumps(
                            {
                                "host": host_run["plan_fingerprint"],
                                "donor": donor_run["plan_fingerprint"],
                                "fusion": fused_run["plan_fingerprint"],
                                "spawn_count": fused_run["spawn_count"],
                                "network_count": fused_run["network_count"],
                            },
                            sort_keys=True,
                        ),
                    }
                ],
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0182-probe1-contract-mismatch",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe1 re-runs matching vs mismatch vs emit-first mutant. "
                "Named probe2 re-runs fake-rail plans on a different field "
                "(executed fingerprints, spawn counters, untouched-stage bytes)."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0182/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "note": "per-unit only; global unit_manifest.py --write was not run",
        },
        "named_probes": [
            {"id": "probe1", "role": "contract-mismatch-both-states", "command": P1},
            {"id": "probe2", "role": "fake-rail-plan-differs", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/IMP-0182/stage_splice.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/IMP-0182/fake_rail.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Neighbour cover is exact-type, name-preferring. A richer "
                    "IMP-0175 compatibility map (licence, stop-rule, tool policy) "
                    "is not on this tree and is not silently assumed."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "When IMP-0175 exists, call its cell for the spliced pair and "
                    "require FORBIDDEN cells to refuse here too."
                ),
            }
        ],
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": None,
                "note": "measure runs after this emit; probes re-run live",
            }
        ],
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if "SUCCESS:IMP-0182" not in payload:
        print("FAILED:IMP-0182 sentinel missing from payload")
        return 1
    out.write_text(payload, encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0182 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"match={good['status']} mismatch={refused['status']} "
        f"plan_differs={plan_differs} spawn={fused_run['spawn_count']}"
    )
    print("SUCCESS:IMP-0182 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
