#!/usr/bin/env python3
"""Emit IMP-0354 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""
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
UNIT = "IMP-0354"
OUT = "command-center/receipts/IMP-0354.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0354/probe1_every_rule.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0354/probe2_seed_removed.py"
)
LIB = "tools/council/vote/tiebreak.py"
SUPPORTING = [
    LIB,
    "tools/council/__init__.py",
    "tools/council/vote/__init__.py",
    "command-center/p2-wave/probes/IMP-0354/scenario.py",
    "command-center/p2-wave/probes/IMP-0354/probe1_every_rule.py",
    "command-center/p2-wave/probes/IMP-0354/probe2_seed_removed.py",
]


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
        "receipt_path": "command-center/p2-wave/probes/IMP-0354/SUBAGENT-RETURN.json",
        "role": role,
    }


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": True,
        "role": role,
        "eol": "LF",
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0354 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(REPO / "tools"))
    from scenario import census_policies, exact_tie_fixture
    from council.vote.tiebreak import (
        DECLARED_RULES,
        policy_census,
        resolve,
    )

    case = exact_tie_fixture()
    policies = census_policies()
    census = policy_census(case, policies)
    coin = resolve(case, policies["recorded-seed-coin-flip"])
    coin2 = resolve(case, policies["recorded-seed-coin-flip"])
    lib_sha, lib_n = digest(REPO / LIB)
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    artifacts = [art(p, "supporting" if p != LIB else "primary") for p in SUPPORTING]
    artifact_paths = [a["path"] for a in artifacts]
    test_ids = [
        "IMP-0354-T1-every-declared-rule",
        "IMP-0354-T2-recorded-seed-replay",
    ]
    negative_control_ids = [
        "IMP-0354-C1-strip-seed-record",
        "IMP-0354-C2-implicit-list-order-mutant",
    ]
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0354",
        "completion_sentinel": "SUCCESS:IMP-0354",
        "title": "Tie-break policy engine",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "profile": "council-runtime-module",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json IMP-0354: tools/council/vote/"
            "tiebreak.py declared rules (chair-casting-vote, seniority, "
            "recorded-seed-coin-flip, escalation, no-decision); exact-tie "
            "outcome reproducible from recorded rule and seed; no-decision "
            "reachable. Catalog also names 11-COUNCIL-SPECIFICATION.md, which "
            "is not on this Linux worktree."
        ),
        "min_bytes_threshold": 128,
        "question_or_target": (
            "Implement tools/council/vote/tiebreak.py providing explicit, "
            "declared tie-break rules (chair casting vote, seniority, "
            "recorded-seed coin flip, escalation, or no-decision) rather than "
            "an implicit ordering artifact. Falsifiable question: on an exact "
            "tie, is the outcome reproducible from the recorded rule and seed, "
            "and is 'no-decision' actually reachable rather than nominal?"
        ),
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "premise": {
            "catalog_inputs": [
                "tools/council/vote/tiebreak.py",
                "tools/council/vote/tally.py",
                "tools/council/outcomes/kinds.py",
            ],
            "inputs_were_absent": True,
            "action": (
                "Created tools/council/vote/tiebreak.py on this sparse worktree. "
                "Did not exit on predicate:absent. Did not invent tally.py or "
                "outcomes/kinds.py."
            ),
        },
        "implementation": {
            "api_module": LIB,
            "declared_rules": sorted(DECLARED_RULES),
            "entry_points": [
                "council.vote.tiebreak.resolve",
                "council.vote.tiebreak.reproduce",
                "council.vote.tiebreak.policy_census",
            ],
            "no_implicit_list_order": True,
            "module_sha256": lib_sha,
            "module_bytes": lib_n,
            "seed_replay_identical": coin == coin2,
            "coin_flip_winner": coin.winner,
        },
        "policy_census": census,
        "artifact_paths": artifact_paths,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Each declared tie-break rule is reachable on the same "
                    f"2-2 fixture; census rules={sorted(census)}."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{LIB}:policy_census",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[:16000],
                    }
                ],
            },
            {
                "claim": (
                    "The 2-2 fixture resolved twice from recorded seed "
                    f"{coin.seed_used!r} with identical winner {coin.winner!r}."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{LIB}:_coin_flip",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[:8000],
                    }
                ],
            },
            {
                "claim": (
                    "Removing the seed record raises MissingSeedRecord so "
                    "reproducibility FAILS; a first-listed mutant still picks "
                    "and flips under option reversal."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{LIB}:MissingSeedRecord",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2[:16000],
                    }
                ],
            },
        ],
        "test_ids": test_ids,
        "tests": [
            {
                "id": test_ids[0],
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": test_ids[1],
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
                "detail": "seed replay is T2's good state; strip-seed is C1",
            },
        ],
        "negative_control_ids": negative_control_ids,
        "negative_controls": [
            {
                "id": negative_control_ids[0],
                "kind": "both-states",
                "description": (
                    "recorded-seed-coin-flip with seed replays identically; "
                    "the same call with seed stripped raises MissingSeedRecord."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": negative_control_ids[1],
                "kind": "mutation",
                "description": (
                    "implicit_order_mutant_winner returns options[0]; reversing "
                    "the listing flips the mutant winner while resolve() stays "
                    "invariant."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0354-probe2-seed-removed",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Adversarial control is seed-stripping plus the list-order "
                "mutant, not a self-attested prose review."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0302 tools/council/vote/tally.py is absent on this "
                    "sparse worktree. Tie-break consumes already-tallied "
                    "option vote counts and does not implement a tally engine."
                ),
                "settling_experiment": (
                    "Re-run resolve() on live tally artifacts once IMP-0302 "
                    "is delivered on this tree."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "IMP-0311 tools/council/outcomes/kinds.py is absent. "
                    "NO-DECISION and ESCALATION are typed in tiebreak.py and "
                    "are not coerced to a winner; a downstream PASS/FAIL "
                    "consumer census was not run."
                ),
                "settling_experiment": (
                    "Wire Outcome.kind through IMP-0311 kinds and census "
                    "consumers that map NO-DECISION to FAIL."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "Catalog input 11-COUNCIL-SPECIFICATION.md is a Windows "
                    "harness-restore path and is not present here."
                ),
                "settling_experiment": "Validate against that spec file if restored.",
                "verdict": "NOT-CHECKED",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0354/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "notes": (
            "G-1 IMP-0354: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py "
            "--write. SUCCESS:IMP-0354"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    primary = row(OUT, "primary")
    artifacts_man = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0354",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "every-declared-rule-census",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "seed-removed-reproducibility-fails",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0354/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0354-probe2-seed-removed",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": ended,
        "notes": (
            "G-1 for IMP-0354: live named probes exit 0, IMP-0354.json "
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
        "expected": len(artifacts_man),
        "present": len(artifacts_man),
        "artifacts": artifacts_man,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0354 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
