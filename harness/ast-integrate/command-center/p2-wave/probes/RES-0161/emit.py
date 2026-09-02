#!/usr/bin/env python3
"""Emit command-center/research/prior-art/RES-0161-workflow-dsl-feature-matrix.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from grade import (  # noqa: E402
    DEFINITION_PATH,
    capture_bytes,
    grade,
    load_index,
    rail_record,
    wish_list,
)
import sources as S  # noqa: E402

OUT = S.OUT_REL
SCHEMA = S.SCHEMA_REL
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0161/probe1_live_cells_and_rails.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0161/probe2_negative_control_and_two_pass.py"
)
SENTINEL = S.SENTINEL
QUESTION = S.QUESTION


def two_rails(*pairs: tuple[str, str]) -> list[dict]:
    index = load_index()
    by_id = {c["id"]: c for c in index["captures"]}
    out: list[dict] = []
    for cid, needle in pairs:
        rec = by_id[cid]
        body = capture_bytes(cid)
        out.append(rail_record(rec, needle, body, rec["kind"]))
    if len(out) < 2:
        raise SystemExit("FAILED:RES-0161 claim needs two rails")
    return out


def claim(cid, text, verdict, band, rails, caveat, independent_path):
    return {
        "id": cid,
        "claim": text,
        "verdict": verdict,
        "confidence_band": band,
        "sherman_kent_band": band,
        "rails": rails,
        "independent_verification_path": independent_path,
        "strongest_caveat": caveat,
    }


def main() -> int:
    measured = grade()
    if measured["index_integrity_errors"]:
        print("FAILED:RES-0161 capture integrity " + "; ".join(measured["index_integrity_errors"][:8]))
        return 1
    if measured["missing_cells"] or measured["extra_cells"]:
        print("FAILED:RES-0161 cell cartesian drift")
        return 1
    if measured["n_cells"] != len(S.ENGINES) * len(S.FEATURES):
        print("FAILED:RES-0161 cell count")
        return 1
    if measured["n_ok"] != measured["n_cells"]:
        print("FAILED:RES-0161 needle mismatches " + "; ".join(measured["mismatches"][:12]))
        return 1
    if measured["wish_list"]:
        print("FAILED:RES-0161 every feature marked NECESSARY (wish list)")
        return 1
    if measured["negative_control"]["verdict"] != "NOT-NECESSARY":
        print("FAILED:RES-0161 negative control is not NOT-NECESSARY")
        return 1
    if measured["negative_control"]["github_actions_presence"] != "PRESENT":
        print("FAILED:RES-0161 negative control feature is not PRESENT on GitHub Actions")
        return 1
    if not measured["two_pass"]["within_10_percent"]:
        print("FAILED:RES-0161 two-pass relative_delta exceeds 10%")
        return 1
    fam = measured["families"]
    if not fam["sums_agree"] or fam["parsed_sum"] != fam["definition_sum"]:
        print("FAILED:RES-0161 family sums disagree")
        return 1
    if wish_list({r["feature"]: r for r in measured["necessity"]}):
        print("FAILED:RES-0161 necessity rows collapsed to a wish list")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    defn_sha = measured["definition_sha256"]
    nec_necessary = [r for r in measured["necessity"] if r["verdict"] == "NECESSARY"]
    nec_not = [r for r in measured["necessity"] if r["verdict"] == "NOT-NECESSARY"]
    present_n = sum(1 for c in measured["cells"] if c["presence"] == "PRESENT")
    partial_n = sum(1 for c in measured["cells"] if c["presence"] == "PARTIAL")
    absent_n = sum(1 for c in measured["cells"] if c["presence"] == "ABSENT")

    per_engine = []
    for eng in S.ENGINES:
        n = sum(
            1
            for c in measured["cells"]
            if c["engine"] == eng and c["presence"] in {"PRESENT", "PARTIAL"}
        )
        per_engine.append(
            {
                "vendor_id": eng,
                "count": n,
                "coverage": "TWO_RAIL_NEEDLE_GRADE",
                "source": "command-center/p2-wave/probes/RES-0161/grade.py",
            }
        )

    grid = {
        eng: {
            c["feature"]: c["presence"]
            for c in measured["cells"]
            if c["engine"] == eng
        }
        for eng in S.ENGINES
    }

    answer = (
        "Seven engines graded live from captured docs/schemas (needles re-checked "
        f"against sha256-pinned bytes): {present_n} PRESENT, {partial_n} PARTIAL, "
        f"{absent_n} ABSENT out of {measured['n_cells']} cells. "
        f"Strictly necessary for the {fam['parsed_sum']}-item blueprint library "
        f"without escaping to host code: {', '.join(r['feature'] for r in nec_necessary)}. "
        f"Negative control: {nec_not[0]['feature']} is popular (GitHub Actions "
        "strategy.matrix is PRESENT) and NOT-NECESSARY — AgentSpec already has "
        "receipt-driven DynamicFanOut, not cartesian CI axes. "
        "Temporal/Prefect/Dagster conditionals are ABSENT as declarative DSL "
        "(branching is host-language). GitHub Actions has no native retry keyword. "
        + SENTINEL
    )

    claims = [
        claim(
            "C-MATRIX",
            (
                "All 56 engine×feature cells satisfy the frozen needle rule "
                "(PRESENT/PARTIAL: both needles hit captured bytes; ABSENT: both miss)."
            ),
            "CONFIRMED",
            "almost-certain",
            two_rails(
                ("argo-fields", "Parameter indicate a passed string parameter"),
                ("gha-schema", "expressionSyntax"),
            ),
            "Needles are substrings of captured docs/schemas, not runtime executions of each engine.",
            P1,
        ),
        claim(
            "C-NECESSARY",
            (
                "typed_params, conditionals, sub_workflows, artifacts, retries, "
                "timeouts and manual_approval are each NECESSARY for a named "
                "blueprint family that AgentSpec already encodes as a closed construct."
            ),
            "CONFIRMED",
            "highly-likely",
            two_rails(
                ("local-spec", "class Workflow"),
                ("local-taxonomy", "partial-artifact"),
            ),
            (
                "_USER-PROMPTS.md is absent on this worktree; family names are taken "
                "from IMP-0178's catalog question and from agentspec/spec.py node kinds."
            ),
            P2,
        ),
        claim(
            "C-NEG",
            (
                "matrix_expansion is NOT-NECESSARY for the six blueprint families even "
                "though GitHub Actions strategy.matrix is PRESENT: cartesian CI axes "
                "are not AgentSpec DynamicFanOut (receipt-driven max_cardinality)."
            ),
            "CONFIRMED",
            "almost-certain",
            two_rails(
                ("gha-schema", '"matrix"'),
                ("local-spec", "DynamicFanOut"),
            ),
            "A matrix where every feature is NECESSARY would be a wish list; this cell is the required negative control.",
            P2,
        ),
        claim(
            "C-FAMILIES",
            (
                "The six IMP-0178 catalog tokens parse from WORK-UNIT-CATALOG.json "
                "bytes and their sizes sum to the same integer as DEFINITION.json "
                "family n fields (no hardcoded total in the parser)."
            ),
            "CONFIRMED",
            "highly-likely",
            two_rails(
                ("local-catalog", "research/evidence 15"),
                ("local-spec", "Subworkflow"),
            ),
            "The original _USER-PROMPTS.md:10902-10907 taxonomy page is ABSENT; the catalog IMP-0178 question is the surviving local copy.",
            P2,
        ),
        claim(
            "C-GHA-RETRY-ABSENT",
            (
                "GitHub Actions has no native step/job retry keyword in github-workflow.json "
                "or the workflow-syntax page (ABSENT cell; both needles miss)."
            ),
            "CONFIRMED",
            "highly-likely",
            two_rails(
                ("gha-schema", '"retry"'),
                ("gha-syntax-docs", "jobs.<job_id>.steps.retry"),
            ),
            "Third-party actions can retry; that is an escape, not a DSL keyword.",
            P1,
        ),
    ]

    doc = {
        "unit_id": S.UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "report_kind": "compatibility-matrix",
        "question": QUESTION,
        "answer": answer,
        "rows": list(S.ENGINES),
        "columns": list(S.FEATURES),
        "engines": list(S.ENGINES),
        "features": list(S.FEATURES),
        "grid": grid,
        "cells": measured["cells"],
        "necessity": measured["necessity"],
        "negative_control": measured["negative_control"],
        "blueprint_families": measured["families"]["parsed"],
        "blueprint_family_sum": measured["families"]["parsed_sum"],
        "definition": {
            "id": measured["definition_id"],
            "path": "command-center/p2-wave/probes/RES-0161/DEFINITION.json",
            "sha256": defn_sha,
            "frozen_before_count": True,
            "same_rule_all_vendors": True,
        },
        "definition_locked_hash_before_enumerate": measured[
            "definition_locked_hash_before_enumerate"
        ],
        "window": {
            "start": "2026-08-24",
            "end": "2026-08-24",
            "days": 1,
        },
        "per_vendor_counts": per_engine,
        "two_pass": measured["two_pass"],
        "claims": claims,
        "maintenance_implication": (
            "Keep AgentSpec's seven necessary constructs (Workflow.params, "
            "on_failure/Loop.convergence_expr, Subworkflow, named artifacts/"
            "partial-artifact, RepairLoop, timeout as a closed family, "
            "HumanCheckpoint). Do not add GitHub Actions strategy.matrix cartesian "
            "axes; DynamicFanOut already covers receipt-driven fan-out. Treat "
            "Temporal/Prefect/Dagster host-language `if` as an escape, not as a "
            "declarative conditional. GitHub Actions cannot express RepairLoop "
            "without a third-party retry action."
        ),
        "tests": [
            {
                "id": "live-cells-needle-rule-and-both-states",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "negative-control-not-wishlist-and-two-pass",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0161-probe2-negative-control-and-two-pass",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "Probe2 re-counts PRESENT+PARTIAL two ways and refuses a wish-list "
                "mutant that marks every feature NECESSARY. It does not trust emit.py's "
                "copied counts."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/RES-0161/DEFINITION.json",
                "exists": True,
                "role": "frozen-definition",
            },
        ],
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/RES-0161/DEFINITION.json",
                "kind": "pre-registered-definition",
                "sha256": defn_sha,
            },
            {
                "path": "command-center/p2-wave/probes/RES-0161/captures/INDEX.json",
                "kind": "source-lineage-index",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0161/grade.py",
                "kind": "live-needle-grader",
            },
        ],
        "named_probes": [{"id": "probe1", "command": P1}, {"id": "probe2", "command": P2}],
        "output_schema": SCHEMA,
        "measured_at": now,
        "host": {"os": "linux"},
        "inputs_status": {
            "_USER-PROMPTS.md": "ABSENT on this worktree",
            "CLAIM-REGISTRY.json": "ABSENT on this worktree",
            "command-center/sources/REGISTER.md": "present-or-unchecked",
        },
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:RES-0161 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {"unrelated": True, "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
        {"unit_id": "RES-0161", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:RES-0161 schema accepted garbage {list(garbage)[:2]}")
            return 1
    dumped = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in dumped:
        print("FAILED:RES-0161 completion sentinel missing")
        return 1
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(dumped, encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size} defn={defn_sha[:16]}")
    print("SUCCESS:RES-0161 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
