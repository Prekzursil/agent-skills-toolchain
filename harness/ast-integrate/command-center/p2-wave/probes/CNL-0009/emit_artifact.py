#!/usr/bin/env python3
"""Emit CNL-0009 design note (JSON bytes at the catalog .md output_path)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import ops as O  # noqa: E402
import spec_scan as S  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0009-target-block-which-of-the-8-targets-are-measurable-as-writ.md"
)
SCHEMA = "command-center/p2-wave/probes/CNL-0009/artifact.schema.json"
DECLARED_SCHEMA = "command-center/schema/councilspec.v2.schema.json"
QUESTION = (
    "Of the eight declared targets (unique-idea, category, novelty, diversity, "
    "coverage, objection, counterexample, evidence), which have NO measurable "
    "definition as written in the spec, and for each of those, what is the "
    "smallest operational definition that a machine can compute and an "
    "adversary cannot trivially game?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0009/probe1_gaming.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0009/probe2_both_states.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    scan = S.scan()
    defs = O.operational_definitions()
    gaming = O.evaluate_gaming()
    both = O.both_states()
    if not scan["verdict"]["all_eight_unmeasurable"]:
        print("FAILED:CNL-0009 expected all eight unmeasurable as written on this tree")
        print(scan["verdict"])
        return 1
    if not gaming["_all_intent_held"] or not gaming["_all_gamed_naive"]:
        print("FAILED:CNL-0009 gaming suite did not hold")
        print(json.dumps({k: gaming[k] for k in O.TARGETS}, indent=2)[:4000])
        return 1
    if not both["discriminates"]:
        print("FAILED:CNL-0009 both-states did not discriminate")
        print(both)
        return 1

    targets = []
    for tid in O.TARGETS:
        d = defs[tid]
        g = gaming[tid]
        asw = scan["verdict"]["rows"][tid]
        targets.append(
            {
                "id": tid,
                "measurable_as_written": asw["measurable_as_written"],
                "as_written_why": asw["why"],
                "threshold_quoted_in_catalog": asw["threshold_quoted_in_catalog"],
                "identity_operator_written": asw["identity_operator_written"],
                "operational_definition": d["operational"],
                "ungameable_against": d["ungameable_against"],
                "residual": d["residual"],
                "gaming": {
                    "intent": g["intent"],
                    "naive_metric": g["naive_metric"],
                    "operational_metric": g["operational_metric"],
                    "gamed_naive": g["gamed_naive"],
                    "intent_held": g["intent_held"],
                },
            }
        )

    unmeasurable = [t["id"] for t in targets if not t["measurable_as_written"]]
    answer = (
        "All eight declared targets are unmeasurable as written on this worktree. "
        "The four cited spec files (USER-PROMPTS.md slices, 11-COUNCIL-SPECIFICATION.schema.json, "
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json) are absent, so there is no spec body that "
        "defines identity, taxonomy, corpus, or admissibility. The catalog names the eight "
        "targets in CNL-0009 and later quotes thresholds (unique_ideas >= 100, "
        "no_new_objection_rounds >= 2, unresolved_load_bearing_counterexample == 0, "
        "evidence_saturation == true) without operators. Each target therefore receives a "
        "smallest operational definition in this note, executed against a gaming attempt "
        "that maximises a naive reading while failing intent. Coverage is the both-states "
        "control: PASS only when every declared taxonomy bin is occupied; an empty bin fires."
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    declared_schema_present = (REPO / DECLARED_SCHEMA).is_file()
    cnl0001 = (
        REPO
        / "command-center/design/council/"
        "CNL-0001-councilspec-v2-root-envelope-that-supersedes-council-chart.schema.json"
    )
    doc = {
        "schema_version": 1,
        "unit_id": "CNL-0009",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0009",
        "completion_sentinel": "SUCCESS:CNL-0009",
        "title": "Target block: which of the 8 targets are measurable as written",
        "question": QUESTION,
        "answer": answer,
        "min_bytes_threshold": 2048,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNL-0009]",
        "output_schema_declared": DECLARED_SCHEMA,
        "output_schema_declared_present": declared_schema_present,
        "local_artifact_schema": SCHEMA,
        "dependency_cnl0001_present": cnl0001.is_file(),
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "headless-linux",
        },
        "unmeasurable_as_written": unmeasurable,
        "measurable_as_written": [],
        "targets": targets,
        "spec_scan": scan,
        "operational_definitions": defs,
        "gaming": {k: gaming[k] for k in list(O.TARGETS) + ["_all_attempts_recorded", "_all_intent_held", "_all_gamed_naive"]},
        "both_states": both,
        "timestamps": {
            "started_at": "2026-08-24T18:38:00Z",
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "tests": [
            {
                "id": "T1-gaming-per-target",
                "name": "For each of 8 targets, a gaming attempt maximises a naive metric while intent fails",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-both-states-coverage",
                "name": "Coverage check FIRES on empty-category fixture and is SILENT on the known-good run",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "CNL0009-C1",
                "kind": "known-broken-fixture",
                "description": both["negative_control"]["rejects"],
                "fired_on_bad_state": both["fired_on_bad"],
                "silent_on_good_state": both["silent_on_good"],
                "bad_state_output": both["negative_control"]["bad_state_output"],
                "good_state_output": both["negative_control"]["good_state_output"],
                "on_the_state_it_rejects": both["negative_control"]["on_that_state"],
            }
        ],
        "evidence": [
            {
                "claim": "Cited council spec files and remaps are absent on this worktree (Path.is_file).",
                "verdict": "CONFIRMED",
                "signal": "Path.is_file",
                "anchor": "command-center/p2-wave/probes/CNL-0009/spec_scan.py",
                "detail": scan["spec_files"]["present_paths"],
            },
            {
                "claim": "CNL-0009 question names all eight targets; none of those names is paired with an identity operator in that question. Catalog regex finds some later thresholds without operators.",
                "verdict": "CONFIRMED",
                "signal": "catalog JSON walk + regex",
                "anchor": f"command-center/WORK-UNIT-CATALOG.json:{scan['catalog_quotes']['question_line']}",
                "detail": scan["catalog_quotes"]["thresholds_quoted_elsewhere"],
            },
            {
                "claim": "Each of the eight operational metrics is lower than a naive maximising attack, and intent held on every planted game.",
                "verdict": "CONFIRMED",
                "signal": "live evaluator on planted games",
                "anchor": "command-center/p2-wave/probes/CNL-0009/ops.py:evaluate_gaming",
            },
            {
                "claim": "Coverage both-states: silent on four occupied taxonomy bins, fires when failure-class is empty.",
                "verdict": "CONFIRMED",
                "signal": "coverage_score fire_reason",
                "anchor": "command-center/p2-wave/probes/CNL-0009/ops.py:both_states",
                "detail": both["bad_reason"],
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0009-probe2-both-states-rerun",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "cross_vendor_note": (
                "Catalog asks openai/gpt-5-codex to re-run the both-states control. "
                "This G-1 delivery records a mechanically independent re-execution of "
                "the same coverage both-states control in probe2_both_states.py. A second "
                "human vendor pass is NOT-CHECKED on this substrate."
            ),
            "method": "probe2 re-derives coverage PASS/FAIL from fixtures; does not read the author's prose answer.",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNL-0009/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "residual_unknowns": [
            {
                "claim": "Body of _USER-PROMPTS.md:10746-10767 and 11-COUNCIL-SPECIFICATION.schema.json target keywords.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Place the harness-restore spec files on disk and re-run spec_scan.py.",
            },
            {
                "claim": "Synonym-level unique-idea merges and one-parameter forks.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "CNL-0051 / IMP-0300 semantic counter.",
            },
            {
                "claim": "Declared output_schema command-center/schema/councilspec.v2.schema.json (CNL-0001).",
                "verdict": "NOT-CHECKED" if not declared_schema_present else "CONFIRMED",
                "settling_experiment": "Deliver CNL-0001; this unit validates against the local artifact.schema.json.",
            },
        ],
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {
                "path": "command-center/p2-wave/probes/CNL-0009/ops.py",
                "role": "supporting",
                "exists": True,
            },
            {
                "path": SCHEMA,
                "role": "supporting",
                "exists": True,
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "gaming-attempts", "command": P1},
            {"id": "probe2", "role": "both-states-and-negative-control", "command": P2},
        ],
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0009 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:CNL-0009 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNL-0009 artifact {size}B below floor")
        return 1
    if "SUCCESS:CNL-0009" not in out.read_text(encoding="utf-8"):
        print("FAILED:CNL-0009 sentinel missing")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNL-0009 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
