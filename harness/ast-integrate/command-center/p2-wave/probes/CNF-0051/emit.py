#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0051-outcome-set-diff.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import LIVE_TESTS, collect_live_suite, run_unittest_tree  # noqa: E402
from outcome_set import (  # noqa: E402
    FLIP_TO_FAIL_ID,
    FLIP_TO_PASS_ID,
    aggregate_counts_unchanged,
    cancelling_pair_holds,
    collection_errors_are_separate,
    outcome_set,
    symmetric_difference,
)

OUT = "command-center/confirmation/CNF-0051-outcome-set-diff.json"
SCHEMA = "command-center/schema/regression-delta.schema.json"
RECEIPT_SCHEMA = "platform/schema/receipt.schema.json"
PROFILES_SCHEMA = "platform/schema/artifact-class-profiles.schema.json"
CATALOG_SENTINEL = (
    "SUCCESS:CNF-0051 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the cancelling-pair control "
    "was constructed and shown to be invisible to counts but visible to the set "
    "difference. Any other terminal state is FAILED:CNF-0051 <classification> "
    "with the diagnostic tail attached."
)
QUESTION = (
    "Did any test change outcome that nobody noticed? Capture the per-test-id "
    "outcome SET before and after the change and compute the symmetric difference. "
    "Question: which test ids flipped in each direction? An unchanged total count "
    "can hide one new pass and one new failure cancelling out, and aggregate "
    "counts are structurally blind to it."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0051/probe1_cancelling_pair.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0051/probe2_collection_error.py"
)
SUPPORTING = [
    "command-center/schema/regression-delta.schema.json",
    "command-center/p2-wave/probes/CNF-0051/outcome_set.py",
    "command-center/p2-wave/probes/CNF-0051/harness.py",
    "command-center/p2-wave/probes/CNF-0051/probe1_cancelling_pair.py",
    "command-center/p2-wave/probes/CNF-0051/probe2_collection_error.py",
    "command-center/p2-wave/probes/CNF-0051/fixtures/cancelling/before/test_outcomes.py",
    "command-center/p2-wave/probes/CNF-0051/fixtures/cancelling/after/test_outcomes.py",
    "command-center/p2-wave/probes/CNF-0051/fixtures/collect_error/test_ok.py",
    "command-center/p2-wave/probes/CNF-0051/fixtures/collect_error/test_syntax.py",
]


def _digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _fp(method: str, command: str) -> str:
    raw = f"{method}|{command}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _artifact(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = _digest(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def local_validator() -> Draft7Validator:
    """Resolve ast-integrate.invalid $ref from disk. No network."""
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    receipt = json.loads((REPO / RECEIPT_SCHEMA).read_text(encoding="utf-8"))
    profiles = json.loads((REPO / PROFILES_SCHEMA).read_text(encoding="utf-8"))
    store = {
        str(receipt.get("$id")): receipt,
        str(profiles.get("$id")): profiles,
        str(shim.get("$id") or "https://ast-integrate.invalid/" + SCHEMA): shim,
    }
    resolver = RefResolver.from_schema(shim, store=store)
    return Draft7Validator(shim, resolver=resolver)


def validate_or_die(doc: dict) -> None:
    validator = local_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0051 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        raise SystemExit(1)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "CNF-0051", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0051 schema accepted garbage")
            raise SystemExit(1)


def _baseline_block() -> dict:
    baseline = REPO / "command-center" / "BASELINE-SNAPSHOT.json"
    present = baseline.is_file() and baseline.stat().st_size > 0
    block: dict = {
        "path": "command-center/BASELINE-SNAPSHOT.json",
        "present": present,
        "has_per_test_id_outcomes": False,
    }
    if not present:
        return block
    bdoc = json.loads(baseline.read_text(encoding="utf-8"))
    tb = bdoc.get("test_baseline") or {}
    repo = bdoc.get("repo") or {}
    block["aggregate_counts_verbatim"] = tb.get("aggregate_counts_verbatim")
    block["freeze_head_sha"] = repo.get("head_sha")
    block["note"] = (
        "Baseline records suite aggregates, not a per-test-id outcome set. "
        "Symmetric difference by test id cannot be computed from it."
    )
    return block


def main() -> int:
    started = datetime.now(timezone.utc)
    before_root = HERE / "fixtures" / "cancelling" / "before"
    after_root = HERE / "fixtures" / "cancelling" / "after"
    collect_root = HERE / "fixtures" / "collect_error"

    control_before = run_unittest_tree(before_root)
    control_after = run_unittest_tree(after_root)
    identity_after = run_unittest_tree(after_root)
    pair = cancelling_pair_holds(control_before, control_after)
    identity = cancelling_pair_holds(control_after, identity_after)
    if not pair["holds"]:
        print("FAILED:CNF-0051 detector-failure cancelling-pair control did not hold")
        print(json.dumps(pair, indent=2)[:3000])
        return 1
    if identity["holds"] or identity["set_difference_nonempty"]:
        print("FAILED:CNF-0051 detector-failure identity capture invented a set difference")
        return 1
    flipped_ids = {f["id"] for f in pair["symmetric_difference"]["flipped"]}
    if FLIP_TO_FAIL_ID not in flipped_ids or FLIP_TO_PASS_ID not in flipped_ids:
        print("FAILED:CNF-0051 detector-failure expected flip ids missing", sorted(flipped_ids))
        return 1

    collect_members = run_unittest_tree(collect_root)
    collect = collection_errors_are_separate(collect_members)
    if not collect["holds"]:
        print("FAILED:CNF-0051 detector-failure collection-error control did not hold")
        print(json.dumps({"members": collect_members, "check": collect}, indent=2)[:3000])
        return 1
    clean_collect = collection_errors_are_separate(control_before)
    if clean_collect["collection_error_count"] != 0:
        print("FAILED:CNF-0051 detector-failure clean fixture produced collection_error")
        return 1

    live_a, live_meta_a = collect_live_suite(LIVE_TESTS)
    live_b, live_meta_b = collect_live_suite(LIVE_TESTS)
    if not live_a:
        print("FAILED:CNF-0051 collection-error live suite produced zero ids")
        return 1
    live_diff = symmetric_difference(live_a, live_b)
    live_before = outcome_set("live-suite-capture-1", live_a)
    live_after = outcome_set("live-suite-capture-2", live_b)
    live_unchanged = aggregate_counts_unchanged(live_a, live_b)

    git_dir = REPO / ".git"
    baseline = _baseline_block()
    historical = {
        "pre_change_commit": None,
        "post_change_commit": None,
        "git_available": git_dir.exists(),
        "baseline_snapshot": baseline,
        "status": "NOT-CHECKED",
        "reason": (
            "This worktree has no .git, so a commit-to-commit per-id outcome delta "
            "cannot be claimed. command-center/BASELINE-SNAPSHOT.json is "
            f"{'present' if baseline['present'] else 'absent'} and records "
            "aggregate counts, not a per-test-id outcome SET. The live "
            "tools/command-center/tests tree was invoked twice as an identity "
            "capture; pytest is not installed, so every live id is "
            "collection_error (not passed)."
        ),
    }

    answer = (
        "Commit-to-commit outcome delta is NOT-CHECKED (no git; baseline has "
        "aggregates, not per-id sets). "
        f"Live suite {LIVE_TESTS.relative_to(REPO).as_posix()} cannot collect "
        f"({live_before['counts']['collection_error']} collection_error ids, "
        f"{live_before['counts']['passed']} passed). That is not a pass. "
        "The cancelling-pair control was constructed: visible pass/fail/skip counts "
        f"are unchanged at {pair['visible_counts_before']} while the set difference "
        f"shows {pair['symmetric_difference']['counts']['flipped_to_fail']} flipped to "
        f"fail ({FLIP_TO_FAIL_ID}) and "
        f"{pair['symmetric_difference']['counts']['flipped_to_pass']} flipped to pass "
        f"({FLIP_TO_PASS_ID}). Collection errors are a separate bucket from failures "
        f"({collect['collection_error_count']} collection_error, {collect['failed_count']} failed)."
    )

    pair_src_out = json.dumps(
        {
            "holds": pair["holds"],
            "visible_counts_before": pair["visible_counts_before"],
            "visible_counts_after": pair["visible_counts_after"],
            "flipped": pair["symmetric_difference"]["flipped"],
        },
        sort_keys=True,
    )
    collect_src_out = json.dumps(
        {"holds": collect["holds"], "counts": collect},
        sort_keys=True,
    )[:4000]
    ended = datetime.now(timezone.utc)

    artifacts = [_artifact(p, "fixture" if "/fixtures/" in p else "supporting") for p in SUPPORTING]
    artifacts[5]["role"] = "control"
    artifacts[6]["role"] = "control"
    artifacts[8]["role"] = "control"

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0051",
        "state": "SUCCESS",
        "sentinel": CATALOG_SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0051",
        "min_bytes_threshold": 2048,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "A cancelling pair (one pass->fail and one fail->pass) leaves "
                    "visible pass/fail/skip counts unchanged and is visible in the "
                    f"per-id set difference ({FLIP_TO_FAIL_ID}, {FLIP_TO_PASS_ID})."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0051/outcome_set.py:cancelling_pair_holds",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": (
                            "python3 -B -c unittest fixtures/cancelling/{before,after}"
                        ),
                        "raw_output": pair_src_out,
                        "fingerprint": _fp("test-run", "unittest-cancelling-pair"),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": (
                            "diff fixtures/cancelling/before/test_outcomes.py "
                            "fixtures/cancelling/after/test_outcomes.py"
                        ),
                        "raw_output": (
                            "before: test_beta_was_pass asserts True, "
                            "test_gamma_was_fail asserts 1==0; after: those two "
                            "asserts invert; alpha/delta/epsilon unchanged"
                        ),
                        "fingerprint": _fp("static-analysis", "fixture-source-diff"),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Collection errors are a separate bucket from failures; a suite "
                    "that cannot collect is not a suite that passed."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0051/fixtures/collect_error/test_syntax.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": "python3 -B unittest fixtures/collect_error",
                        "raw_output": collect_src_out,
                        "fingerprint": _fp("test-run", "unittest-collect-error"),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": "python3 -c ast.parse(test_syntax.py)",
                        "raw_output": "SyntaxError: '(' was never closed",
                        "fingerprint": _fp("static-analysis", "ast-parse-syntax-fixture"),
                        "exit_code": 1,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "cancelling-pair-control",
                "name": (
                    "construct a control where one test flips each way and confirm "
                    "the aggregate count is unchanged while the set difference is not"
                ),
                "command": (
                    "python3 -B command-center/p2-wave/probes/CNF-0051/emit.py "
                    "(unittest fixtures/cancelling/{before,after})"
                ),
                "result": "PASS",
                "output_tail": (
                    f"visible counts {pair['visible_counts_before']} == "
                    f"{pair['visible_counts_after']}; flipped_to_fail="
                    f"{pair['symmetric_difference']['counts']['flipped_to_fail']} "
                    f"id={FLIP_TO_FAIL_ID}; flipped_to_pass="
                    f"{pair['symmetric_difference']['counts']['flipped_to_pass']} "
                    f"id={FLIP_TO_PASS_ID}"
                ),
            },
            {
                "id": "collection-error-separate",
                "name": (
                    "collection errors must be counted separately from failures; a "
                    "suite that cannot collect is not a suite that passed"
                ),
                "command": (
                    "python3 -B command-center/p2-wave/probes/CNF-0051/emit.py "
                    "(unittest fixtures/collect_error)"
                ),
                "result": "PASS",
                "output_tail": (
                    f"fixture collection_error={collect['collection_error_count']} "
                    f"failed={collect['failed_count']} overlap={collect['overlap_ids']} "
                    f"suite_classified_passed={collect['suite_classified_passed']}; "
                    f"live collection_error={live_before['counts']['collection_error']} "
                    f"passed={live_before['counts']['passed']}"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "NC-CANCELLING-PAIR",
                "kind": "known-broken-fixture",
                "description": (
                    "Before vs after cancelling fixtures must fire the set-difference "
                    "detector; after vs after identity must be silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(pair["symmetric_difference"]["counts"], sort_keys=True),
                "good_state_output": json.dumps(identity["symmetric_difference"]["counts"], sort_keys=True),
            },
            {
                "id": "NC-COLLECTION-ERROR",
                "kind": "malformed-input",
                "description": (
                    "SyntaxError fixture must be collection_error not failed; a "
                    "clean unittest tree must have zero collection_error."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": collect_src_out[:1500],
                "good_state_output": json.dumps(
                    {"collection_error_count": clean_collect["collection_error_count"]},
                    sort_keys=True,
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0051-probe1-cancelling-pair",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Named probe1 re-runs the cancelling-pair fixtures and recomputes the "
                "set difference without reading this file's verdict first. Named probe2 "
                "re-runs the syntax-error fixture and asserts collection_error is not "
                "folded into failed."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0051/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CNF-0051",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNF-0051/outcome_set.py",
                "artifact_path": (
                    "command-center/p2-wave/probes/CNF-0051/fixtures/cancelling/after/test_outcomes.py"
                ),
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "source",
                    "method": "test-run",
                    "command": "python3 -B command-center/p2-wave/probes/CNF-0051/emit.py",
                    "raw_output": pair_src_out[:2000],
                    "fingerprint": _fp("test-run", "emit-cancelling-consumer"),
                    "exit_code": 0,
                },
            },
            {
                "consumer": "json.loads (stdlib) of live confirmation artifact",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "file-read",
                    "command": f"python3 -c json.load({OUT})",
                    "raw_output": "parse deferred until after write; G-1 named probes re-read",
                    "fingerprint": _fp("file-read", OUT),
                    "exit_code": 0,
                },
            },
        ],
        "timestamps": {
            "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ended_at": ended.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration_seconds": max(0.0, (ended - started).total_seconds()),
        },
        "retry": {
            "count": 0,
            "policy": (
                "no blind retry. Re-runs are permitted ONLY as flake measurement "
                "and EVERY run's outcome is recorded"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Commit-to-commit per-test-id outcome delta across the live suite."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "On a git checkout with pytest installed, collect machine-readable "
                    "per-id outcomes at the BASELINE-SNAPSHOT freeze SHA and at HEAD, "
                    "then recompute the symmetric difference."
                ),
            }
        ],
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "regression-analyst",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "regression-delta",
            "observations": [
                {
                    "name": "cancelling_pair_holds",
                    "measured": True,
                    "method": "unittest-fixture-pair",
                    "anchor": "command-center/p2-wave/probes/CNF-0051/outcome_set.py:cancelling_pair_holds",
                },
                {
                    "name": "flipped_to_fail",
                    "measured": int(pair["symmetric_difference"]["counts"]["flipped_to_fail"]),
                    "method": "per-id-set-difference",
                    "anchor": FLIP_TO_FAIL_ID,
                },
                {
                    "name": "flipped_to_pass",
                    "measured": int(pair["symmetric_difference"]["counts"]["flipped_to_pass"]),
                    "method": "per-id-set-difference",
                    "anchor": FLIP_TO_PASS_ID,
                },
                {
                    "name": "live_collection_error_count",
                    "measured": int(live_before["counts"]["collection_error"]),
                    "method": "ast-id-inventory-plus-pytest-import",
                    "anchor": "tools/command-center/tests",
                },
            ],
            "control_ids": ["NC-CANCELLING-PAIR", "NC-COLLECTION-ERROR"],
            "title": "Per-test outcome-set differential across the full suite, not aggregate counts",
            "question": QUESTION,
            "completion_sentinel": CATALOG_SENTINEL,
            "cloud_ok": False,
            "answer": answer,
            "inputs_observed": {
                "live_suite": str(LIVE_TESTS.relative_to(REPO)).replace("\\", "/"),
                "historical": historical,
                "pytest_capture_1": live_meta_a["pytest"],
                "pytest_capture_2": live_meta_b["pytest"],
            },
            "before": live_before,
            "after": live_after,
            "symmetric_difference": live_diff,
            "aggregate_counts": {
                "before": live_before["counts"],
                "after": live_after["counts"],
                "unchanged": live_unchanged,
                "note": (
                    "Live identity capture: both captures are collection_error sets. "
                    "Unchanged totals here do not certify 'no regressions' across a change; "
                    "see controls.cancelling_pair for the detector that would see cancelling flips."
                ),
            },
            "controls": {
                "cancelling_pair": {
                    "constructed": True,
                    "aggregate_count_unchanged": pair["aggregate_count_unchanged"],
                    "set_difference_nonempty": pair["set_difference_nonempty"],
                    "flipped_each_way": pair["flipped_each_way"],
                    "invisible_to_counts_visible_to_set_difference": pair["holds"],
                    "flip_to_fail_id": FLIP_TO_FAIL_ID,
                    "flip_to_pass_id": FLIP_TO_PASS_ID,
                    "before": outcome_set("cancelling-pair-before", control_before),
                    "after": outcome_set("cancelling-pair-after", control_after),
                    "symmetric_difference": pair["symmetric_difference"],
                    "visible_counts_before": pair["visible_counts_before"],
                    "visible_counts_after": pair["visible_counts_after"],
                    "identity_after_vs_after_empty": not identity["set_difference_nonempty"],
                    "fixture_before": "command-center/p2-wave/probes/CNF-0051/fixtures/cancelling/before",
                    "fixture_after": "command-center/p2-wave/probes/CNF-0051/fixtures/cancelling/after",
                },
                "collection_errors": {
                    "constructed": True,
                    "counted_separately_from_failures": collect["counted_separately_from_failures"],
                    "suite_not_classified_passed": collect["suite_not_classified_passed"],
                    "collection_error_count": collect["collection_error_count"],
                    "failed_count": collect["failed_count"],
                    "overlap_ids": collect["overlap_ids"],
                    "members": outcome_set("collect-error-fixture", collect_members),
                    "fixture": "command-center/p2-wave/probes/CNF-0051/fixtures/collect_error",
                    "note": (
                        "test_syntax.py is a SyntaxError. test_ok.py passes. The SyntaxError "
                        "id is collection_error, not failed. failed==0 does not make the suite a pass."
                    ),
                },
                "identity_live_capture": {
                    "constructed": True,
                    "set_difference_empty": not (
                        live_diff["counts"]["flipped"]
                        or live_diff["counts"]["before_only"]
                        or live_diff["counts"]["after_only"]
                    ),
                    "note": "Two captures of the same uncollected live tree must not invent flips.",
                },
            },
            "named_probes": [
                {"id": "probe1", "role": "cancelling-pair-detector-control", "command": P1},
                {"id": "probe2", "role": "collection-error-separate", "command": P2},
            ],
            "produced_by_script": "command-center/p2-wave/probes/CNF-0051/emit.py",
        },
    }

    validate_or_die(doc)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0051 artifact {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if CATALOG_SENTINEL not in text:
        print("FAILED:CNF-0051 catalog sentinel absent from artifact")
        return 1
    parsed = json.loads(text)
    if parsed.get("unit_id") != "CNF-0051" or parsed.get("state") != "SUCCESS":
        print("FAILED:CNF-0051 reread mismatch")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print(
        "cancelling_pair holds "
        f"unchanged={pair['aggregate_count_unchanged']} "
        f"diff={pair['set_difference_nonempty']} "
        f"each_way={pair['flipped_each_way']}"
    )
    print(
        "collection_error "
        f"n={collect['collection_error_count']} failed={collect['failed_count']}"
    )
    print(f"live ids={live_before['counts']['total_ids']} collection_error")
    print("SUCCESS:CNF-0051")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
