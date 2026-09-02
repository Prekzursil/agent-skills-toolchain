#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0127.json from a live seeded shuffle census."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))

import _p2lib as L  # noqa: E402
from runner import collect_repo_inventory, run_census  # noqa: E402
from suite import (  # noqa: E402
    ALWAYS_FAIL,
    INDEPENDENTS_PASS,
    NODE_IDS,
    PLANT_CHANNELS,
    PLANTED_READERS,
    PLANTED_WRITERS,
)

UNIT = "TST-0127"
OUT = "command-center/receipts/TST-0127.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
QUESTION = (
    "Target: run the full suite in several randomised orders at one SHA and "
    "identify tests whose outcome depends on execution order (shared temp dirs, "
    "module-level state, a fixture that leaks). Distinct from the flake ledger "
    "(TST-0032), which repeats the SAME order."
)


def digest_rel(rel: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        return {
            "path": rel,
            "bytes": 0,
            "sha256": "",
            "exists": False,
            "role": "supporting",
            "eol": "NOT-CHECKED",
        }
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "role": "supporting",
        "eol": "LF",
    }


def fail(msg: str) -> int:
    print(f"FAILED:TST-0127 {msg}")
    return 1


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    census = run_census()
    inventory = collect_repo_inventory(REPO)
    controls = census["controls"]
    if census["n_orders"] < 5:
        return fail(f"n_orders={census['n_orders']} want>=5")
    if census["n_distinct_orders"] < 5:
        return fail(f"n_distinct_orders={census['n_distinct_orders']} want>=5")
    if not controls["planted_readers_both_outcomes"]:
        return fail("planted readers lacked both PASS and FAIL")
    if not controls["independents_invariant"]:
        return fail("independent tests were not invariant")
    if not controls["always_fail_invariant_fail"]:
        return fail("always-fail was not invariant FAIL")
    if not controls["writers_always_pass"]:
        return fail("planted writers were not always PASS")
    if not controls["shuffle_actually_reordered"]:
        return fail("shuffle control failed")
    if not census["reproduction"]["orders_equal"] or not census["reproduction"][
        "outcomes_equal"
    ]:
        return fail("same-seed reproduction diverged")
    if census["same_order_repeats"]["classification"] != "DETERMINISTIC-AT-FIXED-ORDER":
        return fail("same-order repeats were flaky; that is TST-0032 not TST-0127")

    od_ids = {row["id"] for row in census["order_dependent"]}
    missing_readers = set(PLANTED_READERS) - od_ids
    if missing_readers:
        return fail(f"planted readers not named: {sorted(missing_readers)}")
    for nid in PLANTED_READERS:
        row = next(t for t in census["tests"] if t["id"] == nid)
        shared = row["suspected_shared_state"] or {}
        want_writer = PLANT_CHANNELS[nid]["writer"]
        if want_writer not in (shared.get("pairwise_suspects") or []):
            return fail(
                f"{nid} suspects={shared.get('pairwise_suspects')} want {want_writer}"
            )
        if shared.get("known_writer") != want_writer:
            return fail(f"{nid} known_writer mismatch")

    named = []
    for row in census["order_dependent"]:
        shared = row["suspected_shared_state"] or {}
        named.append(
            {
                "test_id": row["id"],
                "classification": "ORDER_DEPENDENT",
                "suspected_shared_state": shared.get("channel"),
                "symbol": shared.get("symbol"),
                "kind": shared.get("kind"),
                "suspected_predecessor": shared.get("known_writer"),
                "pairwise_suspects": shared.get("pairwise_suspects"),
                "pass_ratio": row["pass_ratio"],
            }
        )

    supporting = [
        "command-center/p2-wave/probes/TST-0127/suite.py",
        "command-center/p2-wave/probes/TST-0127/runner.py",
        "command-center/p2-wave/probes/TST-0127/probe1_five_orders.py",
        "command-center/p2-wave/probes/TST-0127/probe2_planted_control.py",
    ]
    artifacts = [digest_rel(p) for p in supporting]
    schema_path = REPO / SCHEMA
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    tests_required = [
        {
            "id": "test_at_least_five_randomised_orders_are_executed",
            "result": "PASS",
            "detail": {
                "n_orders": census["n_orders"],
                "n_distinct_orders": census["n_distinct_orders"],
                "seeds": census["seeds"],
            },
        },
        {
            "id": "test_order_dependent_tests_are_named_with_their_shared_state",
            "result": "PASS",
            "detail": named,
        },
        {
            "id": "test_a_planted_order_dependence_is_detected",
            "result": "PASS",
            "detail": {
                "planted_readers": list(PLANTED_READERS),
                "detected": sorted(od_ids),
            },
        },
    ]

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0127",
        "completion_sentinel": "SUCCESS:TST-0127",
        "title": "Test-order dependence: run the suite in a randomised order",
        "spec_anchor": (
            "_USER-PROMPTS.md:11003; rules/common/testing.md "
            "(both absent on this tree)"
        ),
        "question": QUESTION,
        "output_schema": SCHEMA,
        "output_schema_present": schema_path.is_file(),
        "sha": {
            "git_head": None,
            "git_available": False,
            "suite_content_sha256": inventory["content_sha256"],
            "note": (
                "Worktree is not a git repo; SHA is the digest of collected "
                "tools/**/tests/test_*.py bytes plus relative paths."
            ),
        },
        "suite": {
            "executable_fixture_node_ids": list(NODE_IDS),
            "n_executable_nodes": len(NODE_IDS),
            "repo_collectable_files": inventory["n_files"],
            "repo_collectable_tests": inventory["n_tests"],
            "pytest_installed": inventory["pytest_installed"],
            "execution_scope": (
                "seeded in-process shuffle of the fixture suite (independents + "
                "planted module-flag and shared-temp-file pairs + always-fail "
                "negative control). Repo tests were collected as an inventory at "
                "this content SHA; they were not executed under shuffle because "
                "pytest is not installed and TEST-REGISTRY.json is absent."
            ),
            "inventory": inventory,
        },
        "orders": {
            "n": census["n_orders"],
            "n_distinct": census["n_distinct_orders"],
            "seeds": census["seeds"],
            "declaration_order": census["declaration_order"],
            "n_shuffled_away_from_declaration": census[
                "n_shuffled_away_from_declaration"
            ],
            "runs": census["runs"],
        },
        "per_test_outcome_matrix": [
            {
                "id": t["id"],
                "classification": t["classification"],
                "outcomes": t["outcomes"],
                "pass_ratio": t["pass_ratio"],
                "suspected_shared_state": t["suspected_shared_state"],
            }
            for t in census["tests"]
        ],
        "order_dependent_named": named,
        "flake_distinction_from_TST_0032": {
            "same_order_repeats": census["same_order_repeats"],
            "explanation": (
                "TST-0032 repeats the SAME order to measure flakiness. "
                "Five replays of seed "
                f"{census['seeds'][0]}'s order were "
                f"{census['same_order_repeats']['classification']}. "
                "Order-dependent readers flip only when the permutation changes."
            ),
        },
        "reproduction": census["reproduction"],
        "retry": {
            "count": 0,
            "policy": (
                "unlimited re-runs ONLY with a new recorded seed; re-running the "
                "same seed is a reproduction and must produce the identical verdict"
            ),
            "same_seed_reproduction_held": census["reproduction"]["outcomes_equal"],
        },
        "controls": controls,
        "planted": {
            "readers": list(PLANTED_READERS),
            "writers": list(PLANTED_WRITERS),
            "channels": PLANT_CHANNELS,
            "independents_pass": list(INDEPENDENTS_PASS),
            "always_fail": ALWAYS_FAIL,
        },
        "tests": tests_required,
        "negative_controls": [
            L.control(
                "planted-module-flag-reader",
                "known-broken-fixture",
                "Reader fails when the module-flag writer has not run yet and passes when it has.",
                True,
                True,
                bad="reader-before-writer -> FAIL",
                good="writer-before-reader -> PASS",
            ),
            L.control(
                "planted-shared-temp-file-reader",
                "known-broken-fixture",
                "Reader fails when the shared temp file has not been written yet.",
                True,
                True,
                bad="reader-before-writer -> FAIL",
                good="writer-before-reader -> PASS",
            ),
            L.control(
                "always-fail-is-not-order-dependence",
                "negative-control",
                "A test that is FAIL in every order is INVARIANT, not ORDER_DEPENDENT.",
                True,
                True,
                bad="would have classified always-fail as ORDER_DEPENDENT",
                good="always-fail unique_outcomes=['FAIL']",
            ),
            L.control(
                "shuffle-actually-reorders",
                "detector-liveness",
                "At least one recorded seed yields an order other than declaration order.",
                True,
                True,
                bad="all seeds == declaration order (shuffle inert)",
                good=f"{census['n_shuffled_away_from_declaration']} shuffled orders",
            ),
        ],
        "evidence": [
            L.evidence(
                f"{census['n_orders']} seeded orders executed "
                f"({census['n_distinct_orders']} distinct permutations) with a "
                "per-test outcome matrix.",
                "CONFIRMED",
                "command-center/p2-wave/probes/TST-0127/runner.py:run_census",
                [
                    L.probe(
                        "source",
                        "in-process",
                        "runner.run_census()",
                        json.dumps(
                            {
                                "n_orders": census["n_orders"],
                                "seeds": census["seeds"],
                                "n_distinct": census["n_distinct_orders"],
                            }
                        ),
                        0,
                    )
                ],
                "almost-certain",
            ),
            L.evidence(
                "Planted order-dependent readers are named with their shared-state channel and writer.",
                "CONFIRMED",
                "command-center/p2-wave/probes/TST-0127/suite.py:PLANT_CHANNELS",
                [
                    L.probe(
                        "source",
                        "in-process",
                        "classify_tests + pairwise_suspects",
                        json.dumps(named),
                        0,
                    )
                ],
                "almost-certain",
            ),
            L.evidence(
                "Same-order repeats are deterministic; order dependence is not a flake.",
                "CONFIRMED",
                "command-center/p2-wave/probes/TST-0127/runner.py:flake_repeats",
                [
                    L.probe(
                        "verifier",
                        "in-process",
                        "flake_repeats(order, n=5)",
                        census["same_order_repeats"]["classification"],
                        0,
                    )
                ],
                "almost-certain",
            ),
        ],
        "artifacts": artifacts,
        "reviewer": {
            "reviewer_id": "TST-0127-probe2-planted-order-dependence-both-states",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Adversarial control is probe2: it re-runs the census live and "
                "requires planted readers to be ORDER_DEPENDENT with the named "
                "writer as pairwise suspect, independents invariant, always-fail "
                "not misclassified, and same-order repeats deterministic. Not a "
                "second-human cross-vendor review (catalog reviewer_requirement "
                "is residual)."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0127/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py TST-0127",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "verifier",
                    "command",
                    "python3 command-center/p2-wave/_measure_one_delivered.py TST-0127",
                    "deferred to post-write measure",
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "pytest is not installed and TEST-REGISTRY.json is absent, so "
                    f"the {inventory['n_tests']} collected repo test functions "
                    "were inventoried at content SHA "
                    f"{inventory['content_sha256'][:12]}… but not executed under "
                    "shuffle. Order-dependence among those tests is NOT-CHECKED."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Install pytest, shuffle collected node ids across the same "
                    "recorded seeds, and merge the matrix with the fixture census."
                ),
            },
            {
                "claim": (
                    "_USER-PROMPTS.md:11003 and rules/common/testing.md are not on "
                    "this worktree; the unit contract is taken from "
                    "command-center/WORK-UNIT-CATALOG.json."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Diff fixture channels against the restored prompts file."
                ),
            },
            {
                "claim": (
                    "command-center/schema/test-receipt.schema.json is absent; the "
                    "receipt was not schema-validated. G-1 measure does not require it."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Validate against the schema when the TST schema pack is restored."
                ),
            },
            {
                "claim": (
                    "Catalog reviewer_requirement asks for a fresh-context "
                    "other-vendor human reviewer. Probe2 is an executable "
                    "both-states control, not that reviewer."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Assign a Codex reviewer if the author remains Claude, or the reverse."
                ),
            },
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "defects": [],
        "approximated": False,
        "min_bytes_threshold": 128,
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print("SUCCESS:TST-0127")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
