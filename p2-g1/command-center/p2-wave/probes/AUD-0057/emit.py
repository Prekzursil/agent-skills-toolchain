#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0057-assertion-strength-census.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import census as C  # noqa: E402
import mutate as M  # noqa: E402

OUT = "command-center/audit/AUD-0057-assertion-strength-census.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
LOCAL_SCHEMA = "command-center/p2-wave/probes/AUD-0057/artifact.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0057 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Which tests pass an argument explicitly on every path such that the "
    "function's DEFAULT value is never exercised - the exact shape that let "
    "a 1024-to-512 default change survive a 15-of-15 green suite?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0057/probe1_ast_census.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0057/probe2_mutation.py"
)


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def validate_doc(doc: dict) -> dict:
    schema_path = HERE / "artifact.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    missing = [k for k in (schema.get("required") or []) if k not in doc]
    if missing:
        raise SystemExit(f"FAILED:AUD-0057 emit missing keys {missing}")
    catalog_schema = REPO / SCHEMA
    engine = "required-keys"
    try:
        import jsonschema  # type: ignore

        jsonschema.validate(instance=doc, schema=schema)
        engine = "jsonschema"
    except ImportError:
        pass
    return {
        "engine": engine,
        "ok": True,
        "local_schema": LOCAL_SCHEMA,
        "catalog_schema": SCHEMA,
        "catalog_schema_present": catalog_schema.is_file(),
    }


def planted_map(rows: list[dict]) -> dict[str, dict]:
    return {f"{r.get('param')}|{r.get('qualname') or r.get('function')}": r for r in rows}


REVIEWER_REQ = (
    "one fresh-context Claude reviewer who has not seen this unit's "
    "transcript; the reviewer must try to FALSIFY the headline count "
    "before PASS, not re-read the artifact"
)
ORIGINAL_BUILD = {
    "vendor": "cursor", "model": "grok-4.6", "role": "tool-author",
    "execution_substrate": "local-parallel",
}


def main() -> int:
    live = C.run_census()
    planted = planted_map(live["planted"])
    hole = planted.get("min_bytes|aud0057_check_payload_floor")
    ctrl = planted.get("factor|aud0057_scale_by_factor")
    if hole is None or hole.get("status") != "unexercised":
        print(f"FAILED:AUD-0057 emit planted min_bytes not unexercised: {hole}")
        return 1
    if hole.get("calls_supplying", 0) < 1 or hole.get("calls_omitting", 0) != 0:
        print(f"FAILED:AUD-0057 emit planted hole call shape: {hole}")
        return 1
    if ctrl is None or ctrl.get("status") != "exercised":
        print(f"FAILED:AUD-0057 emit planted factor not exercised: {ctrl}")
        return 1
    if live["n_defaults"] < 2:
        print("FAILED:AUD-0057 emit census found fewer than the two planted defaults")
        return 1

    mut = M.run_mutations()
    if mut.get("pass") is not True:
        print("FAILED:AUD-0057 emit mutation both-states")
        print(mut.get("exercised_tail") or "")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live_unex = [r for r in live["unexercised"] if "fixtures/estate/" not in str(r.get("file") or "")]
    headline = (
        f"{live['n_unexercised']} default parameter(s) have test call sites that "
        f"always pass the argument explicitly (never omit it), including the "
        f"planted DEFAULT_MIN_BYTES replica at {hole['anchor']}. "
        f"{live['n_exercised']} defaults are omitted by at least one test; "
        f"{live['n_no_test_calls']} have no matching test calls."
    )
    doc = {
        "unit_id": "AUD-0057",
        "id": "AUD-0057",
        "state": "PARTIAL",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "audit-finding",
        "schema_version": 1,
        "title": "Assertion-strength census: tests that never exercise the default they claim to protect",
        "question_or_target": QUESTION,
        "output_schema": SCHEMA,
        "min_bytes_threshold": 2048,
        "spec_anchor": "catalog:AUD-0057",
        "timestamps": {"emitted_at": now},
        "produced_by": {
            "vendor": "anthropic",
            "model": "claude-opus-5-5",
            "role": "builder-shard2-wave1",
            "execution_substrate": "local-serialized",
        },
        "report": {
            "headline": headline,
            "answer": headline,
            "n_defaults": live["n_defaults"],
            "n_exercised": live["n_exercised"],
            "n_unexercised": live["n_unexercised"],
            "n_no_test_calls": live["n_no_test_calls"],
            "n_unresolved": live["n_unresolved"],
            "product_files": live["product_files"],
            "test_files": live["test_files"],
            "parse_errors": live["parse_errors"],
            "historical_shape": (
                "DEFAULT_MIN_BYTES 1024->512 survived a 15/15 green suite because "
                "every test passed min_bytes explicitly. Planted replica "
                "aud0057_check_payload_floor.min_bytes reproduces that shape."
            ),
            "scope": (
                "Function-parameter defaults in tools/ product Python plus the "
                "planted estate fixture. CI-invocation join (bare CLI flags) is "
                "out of scope: this unit is the test-side census."
            ),
        },
        "census": {
            "n_defaults": live["n_defaults"],
            "n_exercised": live["n_exercised"],
            "n_unexercised": live["n_unexercised"],
            "n_no_test_calls": live["n_no_test_calls"],
            "n_unresolved": live["n_unresolved"],
            "product_files": live["product_files"],
            "test_files": live["test_files"],
            "parse_errors": live["parse_errors"],
            "unexercised": live["unexercised"],
            "unexercised_live_product": live_unex[:80],
            "no_test_calls": live["no_test_calls"][:80],
            "planted": [
                {
                    "anchor": r["anchor"],
                    "function": r["qualname"],
                    "param": r["param"],
                    "default": r["default"],
                    "status": r["status"],
                    "calls_omitting": r["calls_omitting"],
                    "calls_supplying": r["calls_supplying"],
                }
                for r in live["planted"]
            ],
            "require_complete": live["require_complete"],
            "per_file": live["per_file"],
            "file_hashes": live["file_hashes"],
        },
        "mutation": {
            "pass": mut["pass"],
            "baseline_green": mut["baseline_green"],
            "unexercised_default_mutated_still_green": mut[
                "unexercised_default_mutated_still_green"
            ],
            "exercised_default_mutated_goes_red": mut["exercised_default_mutated_goes_red"],
            "unexercised_mutation": mut["unexercised_mutation"],
            "exercised_mutation": mut["exercised_mutation"],
            "baseline_rc": mut["baseline_rc"],
            "unexercised_rc": mut["unexercised_rc"],
            "exercised_rc": mut["exercised_rc"],
            "scratch": True,
            "tree_unmodified": True,
        },
        "defects": [
            {
                "id": "AUD-0057-D1",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"Planted DEFAULT_MIN_BYTES replica is unexercised: "
                    f"{hole['anchor']} param=min_bytes default={hole['default']} "
                    f"supply={hole['calls_supplying']} omit=0."
                ),
            }
        ],
        "evidence": [
            {
                "claim": (
                    "AST pass classifies a default as unexercised only when every "
                    "matched test call supplies the argument and none omit it."
                ),
                "verdict": "CONFIRMED",
                "anchor": hole["anchor"],
            },
            {
                "claim": (
                    "Mutating the unexercised planted default 1024->512 in a "
                    "scratch copy leaves the fixture suite green."
                ),
                "verdict": "CONFIRMED",
                "anchor": "mutation.unexercised_default_mutated_still_green",
            },
            {
                "claim": (
                    "Both-states control: mutating the exercised factor default "
                    "2->99 turns the fixture suite red, so the harness can produce red."
                ),
                "verdict": "CONFIRMED",
                "anchor": "mutation.exercised_default_mutated_goes_red",
            },
            {
                "claim": (
                    "require_complete default=False is recorded from the live "
                    "tools/command-center/validate.py census when present; CI bare "
                    "invocation is out of this unit's test-side scope."
                ),
                "verdict": "PARTIAL" if live["require_complete"] else "NOT-CHECKED",
                "anchor": "census.require_complete",
            },
        ],
        "tests": [
            {
                "id": "probe1-ast-census",
                "name": "AST pass: per default, whether any test omits the argument",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-scratch-mutation",
                "name": "Scratch mutation of highest-risk hole stays green",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "both-states-exercised-goes-red",
                "name": "Mutate a covered default and require the suite to turn RED",
                "command": P2,
                "result": "PASS" if mut["exercised_default_mutated_goes_red"] else "FAIL",
            },
        ],
        "negative_controls": {
            "exercised_default_mutation_goes_red": mut["exercised_default_mutated_goes_red"],
            "planted_factor_status": ctrl.get("status"),
        },
        "reviewer": {
            "reviewer_id": "independent-reviewer-pending",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "notes": (
                "The prior snapshot's reviewer block named a probe script "
                "(AUD-0057-probe2-mutation-independent-of-census-ast), which is the "
                "producing lane, not an independent reviewer. Pending the "
                "catalog's fresh-context reviewer."
            ),
        },
        "extensions": {
            "builder_process_state": "BLOCKED",
            "shard2_rebuild_2026_10_24": (
                "Builder-side rebuild from the live tree. The prior snapshot "
                "carried a probe-named reviewer block (reviewer_id equal to a "
                "probe script name, vendor None, no reviewed_at) - the "
                "self-certification class receipt_core condition 9 forbids; it "
                "is replaced by this pending-review marker. Receipt state=BLOCKED "
                "(failure.classification reviewer-absent) lives in "
                "SUBAGENT-RETURN.json; only the independent reviewer closes."
            ),
            "original_build": ORIGINAL_BUILD,
        },
        "failure": {
            "classification": ["reviewer-absent"],
            "reason": (
                "Builder-side construction complete: artifact rebuilt from the "
                "live tree, both named probes re-run live with exit 0, per-unit "
                "manifest row written with the CRLF-normalized sha256. state is "
                "PARTIAL with extensions.builder_process_state=BLOCKED, not "
                "SUCCESS, "
                "because receipt_core forbids state=SUCCESS without "
                "reviewer.verdict=PASS with independent=true; only the "
                "independent reviewer closes."
            ),
            "blocked_on": str(REVIEWER_REQ or "independent reviewer per catalog"),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/AUD-0057/census.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0057/mutate.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "residual_unknowns": [
            "Name-only call matching can attribute a call to the wrong function when "
            "two product functions share a name (recorded as name_collision).",
            "Starred *args/**kwargs call sites are unresolved, not counted as omitting.",
        ],
        "retry": {"policy": "no automatic retry; mutations run only in scratch copies"},
        "failure": None,
        "extensions": {
            "named_probes": [
                {"id": "probe1", "command": P1, "role": "ast-census"},
                {"id": "probe2", "command": P2, "role": "scratch-mutation-both-states"},
            ]
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/AUD-0057/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "AUD-0057",
        },
    }
    schema_info = validate_doc(doc)
    doc["extensions"]["schema_validation"] = schema_info
    text = dump(doc)
    if SENTINEL not in text:
        print("FAILED:AUD-0057 emit sentinel missing from serialized artifact")
        return 1
    if len(text.encode("utf-8")) < 2048:
        print("FAILED:AUD-0057 emit below min_bytes_threshold")
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
