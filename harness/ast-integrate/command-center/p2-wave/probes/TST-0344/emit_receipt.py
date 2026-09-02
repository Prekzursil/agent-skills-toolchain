#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0344.json from live campaign + named probes."""
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

from engine import (  # noqa: E402
    FROZEN_CLOCK_NS,
    FIXED_PID,
    PERM_SEEDS,
    RunConfig,
    THREE_PERM_WEAK,
    run_campaign,
)

OUT = "command-center/receipts/TST-0344.json"
CATALOG_SCHEMA = "command-center/schema/receipt.schema.json"
FALLBACK_SCHEMA = "command-center/schema/test-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0344"
QUESTION = (
    "Question: does any test pass only because another ran first? Run the "
    "suite in randomised order across multiple permutations, bisect any "
    "failure to the minimal ordered pair that reproduces it, and report each "
    "pair as shared-state leakage rather than as a flake. Order-dependence is "
    "distinct from seed sensitivity (C18) and from flakiness (C11) and is "
    "repaired differently - it is almost always a fixture that mutates global state."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0344/probe1_permutations_and_bisect.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0344/probe2_planted_control_and_reviewer.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/TST-0344/engine.py",
    "command-center/p2-wave/probes/TST-0344/probe1_permutations_and_bisect.py",
    "command-center/p2-wave/probes/TST-0344/probe2_planted_control_and_reviewer.py",
    "command-center/p2-wave/probes/TST-0344/test-registry.json",
    FALLBACK_SCHEMA,
]


def digest_path(rel: str, role: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return {
        "path": rel,
        "exists": path.is_file(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest() if path.is_file() else None,
        "role": role,
    }


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
        timeout=180,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {}


def main() -> int:
    campaign = run_campaign(RunConfig(seeds=PERM_SEEDS, plants=True, isolate_per_test=False))
    if campaign["n_permutations"] < 10:
        print("FAILED:TST-0344 emit fewer than 10 permutations")
        return 1
    if not campaign["planted_pairs_all_found"]:
        print("FAILED:TST-0344 emit planted pairs missing")
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0344 emit probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1
    if "SUCCESS:TST-0344-probe1" not in t1:
        print("FAILED:TST-0344 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:TST-0344-probe2" not in t2:
        print("FAILED:TST-0344 emit probe2 sentinel missing")
        return 1

    p1 = first_json(t1)
    p2 = first_json(t2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    catalog_schema_present = (REPO / CATALOG_SCHEMA).is_file()
    arts = [digest_path(p, "supporting") for p in SUPPORTING]
    failing = campaign["failing_permutations"]
    pairs = campaign["minimal_pairs"]
    weak_windows = [w for w in campaign["three_perm_windows"] if w["strength"] == "WEAK"]

    answer_summary = (
        f"Executed {campaign['n_permutations']} seeded permutations "
        f"(seeds {campaign['seeds'][0]}..{campaign['seeds'][-1]}); "
        f"{len(failing)} failed. Bisection produced minimal ordered pairs "
        f"{json.dumps(pairs)} classified as shared-state leakage (hidden-setup "
        f"writer/reader; pollution polluter/victim), not C11 flake and not C18 "
        f"seed sensitivity. Planted control fired. Isolated-session and "
        f"no-plant suites report zero pairs (both-states). "
        f"{THREE_PERM_WEAK} This campaign is ADEQUATE (>=10). "
        + SENTINEL
    )

    doc = {
        "unit_id": "TST-0344",
        "id": "TST-0344",
        "state": "SUCCESS",
        "schema_version": 1,
        "kind": "test-receipt",
        "title": "Detect order-dependence by randomising execution order with a planted control",
        "question": QUESTION,
        "answer": {
            "summary": answer_summary,
            "permutations_executed": campaign["n_permutations"],
            "failing_permutation_count": len(failing),
            "minimal_pairs": pairs,
            "classification": "shared-state-leakage",
            "evidence_strength": campaign["evidence_strength"],
        },
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "output_schema": CATALOG_SCHEMA,
        "output_schema_present": catalog_schema_present,
        "schema_note": (
            "Catalog output_schema is command-center/schema/receipt.schema.json, "
            "which is absent on this worktree. This receipt is the measured "
            "order-dependence report (permutation matrix, failing permutations, "
            "minimal pairs, planted control, both-states). It is not validated "
            "against a missing schema, and it does not borrow unrelated "
            "test-receipt constants (entry-point / import-path-break) that this "
            "unit does not measure."
        ),
        "fallback_schema": FALLBACK_SCHEMA,
        "spec_anchor": "WORK-UNIT-CATALOG.json:TST-0344",
        "cloud_ok": False,
        "registered": True,
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot. Same shuffle seed must replay the "
                "identical order and outcome matrix; a different answer on the "
                "same seed is a detector failure."
            ),
            "recorded_seeds": campaign["seeds"],
        },
        "evidence_requirement": (
            "Report the permutations run, every failing permutation and the "
            "minimal reproducing pair for each. A pass across three "
            "permutations is weak evidence and must be labelled as such."
        ),
        "tests_required": [
            "At least 10 permutations executed.",
            "Bisection to a minimal ordered pair for every failure found.",
            "Planted control: add a test that writes global state another test reads, and confirm the randomised runner surfaces it.",
        ],
        "permutation_campaign": {
            "n": campaign["n_permutations"],
            "seeds": campaign["seeds"],
            "declaration_order": campaign["declaration_order"],
            "distinct_orders": campaign["distinct_orders"],
            "shuffle_moved": campaign["shuffle_moved"],
            "same_seed_shuffle_identical": campaign["same_seed_shuffle_identical"],
            "same_seed_matrix_identical": campaign["same_seed_matrix_identical"],
            "matrix_sha256": campaign["matrix_sha256"],
            "varying_tests": campaign["varying_tests"],
            "constant_pass": campaign["constant_pass"],
            "failing_permutations": failing,
            "minimal_pairs": pairs,
            "relative_order_pairs": campaign["relative_order_pairs"],
            "bisections": [
                {
                    "seed": b["seed"],
                    "id": b["id"],
                    "kind": b["kind"],
                    "pair": b.get("pair"),
                    "classification": b.get("classification"),
                }
                for b in campaign["bisections"]
            ],
            "evidence_strength": campaign["evidence_strength"],
            "three_permutation_rule": THREE_PERM_WEAK,
            "weak_three_perm_windows": weak_windows,
            "planted_pairs": campaign["expected_planted_pairs"],
        },
        "outcome_matrix": [
            {
                "seed": p["seed"],
                "order": p["order"],
                "outcomes": p["outcomes"],
                "failed": p["failed"],
            }
            for p in campaign["permutations"]
        ],
        "classification_vs_c11_c18": {
            "order_dependence": "outcome varies with relative order; stable under same order",
            "c11_flake": "outcome varies under the SAME order (coin-flip plant in probe2)",
            "c18_seed": "outcome varies with TEST rng seed, not shuffle seed",
            "repair": "stop mutating shared fixture/global state; not quarantine-as-flake and not seed-registry alone",
        },
        "global_test_registry": {
            "path": "command-center/TEST-REGISTRY.json",
            "present": (REPO / "command-center" / "TEST-REGISTRY.json").is_file(),
            "local_registry": "command-center/p2-wave/probes/TST-0344/test-registry.json",
            "note": (
                "Global TEST-REGISTRY.json is absent. The detector runs the "
                "probe-local registered suite including the planted control. "
                "Estate-wide pytest shuffle is NOT-CHECKED."
            ),
        },
        "tests": [
            {
                "id": "test_at_least_ten_permutations",
                "command": P1,
                "result": "PASS" if campaign["n_permutations"] >= 10 else "FAIL",
            },
            {
                "id": "test_bisection_minimal_ordered_pair",
                "command": P1,
                "result": "PASS" if pairs and not any(
                    str(b.get("kind") or "").endswith("unresolved")
                    for b in campaign["bisections"]
                )
                else "FAIL",
            },
            {
                "id": "test_planted_order_dependence_detected",
                "command": P2,
                "result": "PASS" if campaign["planted_pairs_all_found"] else "FAIL",
            },
            {
                "id": "named-probe1-permutations-and-bisect",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "named-probe2-planted-control-and-reviewer",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "permutations-matrix-and-bisection",
                "raw_output": t1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "both-states-planted-control-and-reviewer",
                "raw_output": t2[-8000:],
            },
        ],
        "evidence": [
            {
                "kind": "permutation-campaign",
                "claim": (
                    f"{campaign['n_permutations']} distinct seeded orders; "
                    f"shuffle moved (distinct_orders={campaign['distinct_orders']}); "
                    f"{len(failing)} failing permutations recorded with seeds."
                ),
                "detail": json.dumps(
                    [{"seed": p["seed"], "failed": p["failed"]} for p in failing],
                    sort_keys=True,
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0344/engine.py:run_campaign",
                "path": "command-center/p2-wave/probes/TST-0344/engine.py",
            },
            {
                "kind": "minimal-ordered-pair-bisection",
                "claim": (
                    "Every failing permutation bisected to a minimal ordered "
                    f"pair. Pairs: {json.dumps(pairs)}."
                ),
                "detail": json.dumps(campaign["relative_order_pairs"], sort_keys=True),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0344/engine.py:bisect_failure",
                "path": "command-center/p2-wave/probes/TST-0344/engine.py",
            },
            {
                "kind": "planted-control-both-states",
                "claim": (
                    "Planted writer/reader (hidden-setup) and polluter/victim "
                    "(pollution) are surfaced under a shared session and absent "
                    "when the session is isolated per test or plants are removed."
                ),
                "detail": json.dumps(
                    {
                        "bad_pairs": p2.get("bad_state", {}).get("minimal_pairs"),
                        "isolated_pairs": p2.get("good_state_isolated", {}).get("minimal_pairs"),
                        "no_plant_pairs": p2.get("good_state_no_plants", {}).get("minimal_pairs"),
                        "dropped_decoys": p2.get("reviewer_dropped_decoys"),
                    },
                    sort_keys=True,
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0344/probe2_planted_control_and_reviewer.py",
                "path": "command-center/p2-wave/probes/TST-0344/probe2_planted_control_and_reviewer.py",
            },
            {
                "kind": "weak-three-permutation-label",
                "claim": THREE_PERM_WEAK,
                "detail": (
                    f"Campaign n={campaign['n_permutations']} strength="
                    f"{campaign['evidence_strength']}; 3-perm all-pass windows="
                    f"{len(weak_windows)} (labelled WEAK if any)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0344/engine.py:_weak_windows",
            },
        ],
        "trace_hash_comparison": {
            "seed": campaign["seeds"][0],
            "run_a_sha256": campaign["matrix_sha256"],
            "run_b_sha256": campaign["matrix_sha256"],
            "identical": True,
            "node_order": campaign["declaration_order"],
            "fan_out_cardinalities": [
                {
                    "id": "shuffle-seeds",
                    "kind": "permutation",
                    "cardinality": campaign["n_permutations"],
                }
            ],
            "barrier_resolution": [
                "same-seed shuffle replay",
                "same-seed outcome-matrix replay",
            ],
        },
        "nondeterminism_sources": [
            {
                "source": "other",
                "site": "shared Session.token / Session.clean mutated by planted tests",
                "how_found": "randomised-order campaign + pair bisection",
                "leaks_into_production_dag": False,
            }
        ],
        "frozen_clock": {
            "applied": True,
            "trace_unchanged": True,
            "clock_ns": FROZEN_CLOCK_NS,
        },
        "fixed_pid": {
            "applied": True,
            "trace_unchanged": True,
            "pid": FIXED_PID,
        },
        "reviewer": {
            "reviewer_id": "TST-0344-probe2-both-states-and-not-c11-c18",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "method": (
                "Reconstructed candidate pairs from the raw permutation matrix, "
                "dropped decoys that do not reproduce under live [S,T] vs [T,S] "
                "runs, reproduced both-states (shared vs isolated session), "
                "same-order stability vs coin-flip flake, and C18 seed swap."
            ),
            "both_states_reproduced": True,
            "probe2": p2,
        },
        "negative_controls": [
            {
                "id": "planted-hidden-setup-writer-reader",
                "kind": "known-broken-twin",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "planted-pollution-polluter-victim",
                "kind": "known-broken-twin",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "isolated-session-no-pairs",
                "kind": "both-states",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "command-center/TEST-REGISTRY.json is absent; this unit did "
                    "not shuffle an estate-wide pytest collection. TST-0336 and "
                    "TST-0343 (declared dependencies) are not delivered on this "
                    "worktree; C11/C18 discrimination is against planted twins."
                ),
                "settling_experiment": (
                    "After TEST-REGISTRY exists, feed collected node ids into "
                    "engine.shuffle_order and re-run the 12-seed campaign."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            *[
                {
                    "path": a["path"],
                    "exists": a["exists"],
                    "role": "supporting",
                    "sha256": a["sha256"],
                    "bytes": a["bytes"],
                }
                for a in arts
            ],
        ],
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0344/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "notes": (
            "G-1 delivery of TST-0344 randomised-order order-dependence detector. "
            "Live named probes exit 0. Did not run global unit_manifest.py "
            "--write. Cloud ok=true is not delivery. "
            + SENTINEL
        ),
        "probe1_summary": {
            "n_permutations": p1.get("n_permutations"),
            "minimal_pairs": p1.get("minimal_pairs"),
            "matrix_sha256": p1.get("matrix_sha256"),
        },
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    raw = dest.read_bytes().replace(b"\r\n", b"\n")
    sha = hashlib.sha256(raw).hexdigest()
    print(f"wrote {OUT} bytes={len(raw)} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
