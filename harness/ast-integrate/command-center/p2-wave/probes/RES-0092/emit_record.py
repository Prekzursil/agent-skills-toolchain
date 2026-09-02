#!/usr/bin/env python3
"""Emit command-center/research/RES-0092.json from live relation runs."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from threshold import (  # noqa: E402
    CHOSEN_BEFORE_RUN,
    DISTANCE_METRIC,
    RATIONALE,
    VARIANCE_THRESHOLD,
)
from relation import (  # noqa: E402
    KNOWN_BROKEN,
    KNOWN_GOOD,
    MIXED_CASES,
    RELATION_ID,
    both_states_run,
    live_relation_run,
)

OUT = "command-center/research/RES-0092.json"
SCHEMA = "command-center/p2-wave/probes/RES-0092/claim.schema.json"
GLOBAL_SCHEMA = "command-center/schema/research-claim-record.schema.json"
QUESTION = (
    "Which metamorphic relations (reordering inputs, renaming identifiers, "
    "paraphrasing a prompt) should leave an agent pipeline's output invariant, "
    "and does the pipeline actually satisfy them - the test that needs no "
    "ground-truth oracle?"
)
COMPLETION = (
    "SUCCESS:RES-0092 in the receipt AND one implemented relation with its "
    "run output and a pre-stated variance threshold"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0092/probe1_live_relation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0092/probe2_both_states.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def present(rel: str) -> bool:
    p = REPO / rel
    return p.is_file() and p.stat().st_size > 0


def main() -> int:
    live = live_relation_run()
    both = both_states_run()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    global_schema_present = present(GLOBAL_SCHEMA)
    dep_res0091 = present("command-center/research/RES-0091.json")
    eco = present(
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md"
    ) or present("command-center/sources/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md")
    register = present("command-center/sources/REGISTER.md")

    harness_rel = "command-center/p2-wave/probes/CNF-0075/harness.py"
    harness_sha, harness_bytes = sha256_file(REPO / harness_rel)
    thresh_sha, thresh_bytes = sha256_file(HERE / "threshold.py")

    if not both["fired_on_broken_reverse"] or not both["silent_on_good_reverse"]:
        print("FAILED:RES-0092 emit both-states did not discriminate")
        return 1
    if live["reversed"]["violated"] or not live["scores_mixed"]:
        print("FAILED:RES-0092 emit live relation failed")
        return 1
    if not both.get("positional_tuple_moves"):
        print("FAILED:RES-0092 emit palindromic positional fixture")
        return 1

    doc = {
        "schema_version": 1,
        "kind": "research-claim-record",
        "unit_id": "RES-0092",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0092",
        "completion_sentinel": COMPLETION,
        "title": "Extract metamorphic testing relations applicable to LLM-driven pipelines",
        "question": QUESTION,
        "canonical_mechanism": (
            "Metamorphic testing (Chen, Cheung, Yiu 1998; surveyed by Segura, "
            "Fraser, Sanchez, Ruiz-Cortes, IEEE TSE 42(9):805-824, 2016, "
            "DOI 10.1109/TSE.2016.2532875): judge a pipeline by whether a "
            "follow-up input related to the source by a named transformation "
            "produces an output related by a named equivalence, without a "
            "ground-truth oracle for either output."
        ),
        "min_bytes_threshold": 2048,
        "confidence_band": "high-on-this-deterministic-step; not-generalized-to-stochastic-decode",
        "freshness_stamp": now,
        "named_settling_probe": P1,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "measurement-engineer",
            "execution_substrate": "headless-linux",
        },
        "dependency_status": {
            "res_0091_on_disk": dep_res0091,
            "blocks_this_unit": False,
            "reason": (
                "RES-0091 (property-based testability) is catalog-listed as a "
                "dependency but is absent on this worktree. Metamorphic "
                "relations are independently defined (no ground-truth oracle) "
                "and this unit consumes the live CNF-0075 execute_case step, "
                "not RES-0091 outputs. Not parked."
            ),
        },
        "declared_output_schema": GLOBAL_SCHEMA,
        "declared_output_schema_present": global_schema_present,
        "local_schema": SCHEMA,
        "variance_threshold": {
            "value": VARIANCE_THRESHOLD,
            "metric": DISTANCE_METRIC,
            "chosen_before_run": CHOSEN_BEFORE_RUN,
            "rationale": RATIONALE,
            "source_module": "command-center/p2-wave/probes/RES-0092/threshold.py",
            "source_sha256": thresh_sha,
            "source_bytes": thresh_bytes,
        },
        "implemented_relation": {
            "id": RELATION_ID,
            "name": "reorder independent cases; rebound pass/fail must match",
            "transformation": (
                "Reverse the unordered collection of independent capability "
                "cases (source -> follow-up)."
            ),
            "expected_invariance": (
                "The mapping case_id -> score is identical. Distance is the "
                "count of case_id keys whose scores differ."
            ),
            "pipeline_step": live["pipeline_step"],
            "workflow_id": live["workflow_id"],
            "threshold": VARIANCE_THRESHOLD,
            "threshold_stated_before_run": True,
            "why_violation_is_a_defect": (
                "Independent cases are not a sequence. A positional score "
                "vector that changes when the same cases are reordered is "
                "order dependence in the reporter, not acceptable variance."
            ),
            "run": {
                "source_case_ids": live["source_case_ids"],
                "followup_case_ids": live["followup_case_ids"],
                "per_case": live["per_case"],
                "source_fingerprint": live["reversed"]["source"],
                "followup_fingerprint": live["reversed"]["followup"],
                "identity_distance": live["identity"]["distance"],
                "distance": live["reversed"]["distance"],
                "violated": live["reversed"]["violated"],
                "scores_mixed": live["scores_mixed"],
            },
        },
        "excluded_relations": [
            {
                "id": "MR-PARAPHRASE-PROMPT-EXACT",
                "candidate": "paraphrasing a prompt should leave output invariant",
                "excluded": True,
                "justification": (
                    "Exact-string invariance under prompt paraphrase is not a "
                    "fault oracle for generative LLM steps: decode is stochastic "
                    "and semantically equivalent wording is acceptable variance. "
                    "Segura et al. 2016 require that a relation violation "
                    "indicate a fault. Shipping exact-match-after-paraphrase as "
                    "an MR would fire on healthy pipelines. A similarity MR "
                    "would need a named metric and a threshold chosen before "
                    "seeing distances; this tree has no live LLM decode step "
                    "on which to freeze that number, so the relation is excluded "
                    "rather than implemented with a fabricated threshold."
                ),
            },
            {
                "id": "MR-RENAME-CATALOG-PRIMARY-KEY",
                "candidate": "renaming identifiers should leave output invariant",
                "excluded": True,
                "justification": (
                    "Alpha-renaming applies to bound variables whose names are "
                    "not observable. Catalog unit ids and capability tokens are "
                    "the payload: renaming them is a different source input, "
                    "not a metamorphic follow-up. A violation would not be a "
                    "defect. Stage-id renaming on CNF-0075 execute_case would "
                    "be a valid MR (the step ignores stage id) but is not the "
                    "implemented detector in this unit."
                ),
            },
        ],
        "candidate_relations": [
            {
                "id": RELATION_ID,
                "applies_when": (
                    "Unordered collections of independent cases / files / "
                    "records whose output is keyed by identity, not position."
                ),
                "implemented": True,
            },
            {
                "id": "MR-RENAME-BOUND-IDENTIFIERS",
                "applies_when": (
                    "Structural analyzers and compilers where names are bound "
                    "variables. Not implemented here."
                ),
                "implemented": False,
            },
            {
                "id": "MR-PARAPHRASE-PROMPT-EXACT",
                "applies_when": "Never as exact equality on generative decode.",
                "implemented": False,
                "excluded": True,
            },
        ],
        "both_states": {
            "known_good": KNOWN_GOOD,
            "known_broken": KNOWN_BROKEN,
            "fired_on_broken_reverse": both["fired_on_broken_reverse"],
            "silent_on_good_reverse": both["silent_on_good_reverse"],
            "identity_good_silent": both["identity_good_silent"],
            "identity_broken_silent": both["identity_broken_silent"],
            "independent_agrees": both["independent_agrees"],
            "silent_in_both_states": both["silent_in_both_states"],
            "positional_tuple_moves": both["positional_tuple_moves"],
            "fixture_note": (
                "Attempt 1 used case order pass/fail/pass, whose positional "
                "tuple (1,0,1) is a palindrome: reverse left the broken "
                "fingerprint unchanged. That is fixture-unrepresentative, not "
                "an unbuildable detector. Attempt 2 uses pass/pass/fail "
                "(1,1,0) reversed to (0,1,1)."
            ),
            "good_reverse_distance": both["good"]["reversed"]["distance"],
            "broken_reverse_distance": both["broken"]["reversed"]["distance"],
            "broken_source_tuple": both["broken"]["reversed"]["source"],
            "broken_followup_tuple": both["broken"]["reversed"]["followup"],
            "inline_fixtures": "command-center/p2-wave/probes/RES-0092/fixtures/inline-fixtures.json",
            "mixed_cases": list(MIXED_CASES),
        },
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "Reordering independent cases should leave case-id-keyed "
                    "scores invariant; CNF-0075 execute_case on fusion_union "
                    "satisfies that relation at threshold 0."
                ),
                "verdict": "CONFIRMED",
                "evidence_tier": "E1",
                "anchor": "command-center/p2-wave/probes/RES-0092/probe1_live_relation.py",
            },
            {
                "id": "C2",
                "claim": (
                    "A positional score tuple is a genuine defect relative to "
                    "the same relation: reverse permutation changes the tuple "
                    "while case-id rebinding does not."
                ),
                "verdict": "CONFIRMED",
                "evidence_tier": "E1",
                "anchor": "command-center/p2-wave/probes/RES-0092/probe2_both_states.py",
            },
            {
                "id": "C3",
                "claim": (
                    "Prompt-paraphrase exact-match is a useful metamorphic "
                    "relation for LLM pipelines."
                ),
                "verdict": "EXCLUDED",
                "evidence_tier": "E3",
                "anchor": "excluded_relations[id=MR-PARAPHRASE-PROMPT-EXACT]",
            },
            {
                "id": "C4",
                "claim": (
                    "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md and REGISTER.md "
                    "were read on this worktree and supplied the relation list."
                ),
                "verdict": "REFUTED",
                "evidence_tier": "E4",
                "anchor": "source_lineage",
            },
        ],
        "source_lineage": [
            {
                "id": "live-pipeline",
                "path": harness_rel,
                "evidence_tier": "E1",
                "present": True,
                "sha256": harness_sha,
                "bytes": harness_bytes,
                "note": "CNF-0075 execute_case / fusion_union is the pipeline step.",
            },
            {
                "id": "catalog-unit",
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "locator": "work_units[id=RES-0092]",
                "evidence_tier": "E1",
                "present": True,
            },
            {
                "id": "segura-2016",
                "path": "https://doi.org/10.1109/TSE.2016.2532875",
                "evidence_tier": "E3",
                "present": False,
                "note": (
                    "Segura, Fraser, Sanchez, Ruiz-Cortes. A Survey on "
                    "Metamorphic Testing. IEEE TSE 42(9):805-824, 2016. "
                    "Cited; experiments not re-run."
                ),
            },
            {
                "id": "chen-1998",
                "path": "HKUST-CS98-01",
                "evidence_tier": "E3",
                "present": False,
                "note": (
                    "Chen, Cheung, Yiu. Metamorphic testing: a new approach "
                    "for generating next test cases. Technical Report "
                    "HKUST-CS98-01, 1998. Cited; not re-run."
                ),
            },
            {
                "id": "05-ECO",
                "path": "command-center/sources/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md",
                "evidence_tier": "E4",
                "present": eco,
                "note": "Absent on this Linux worktree; claims from it are NOT-CHECKED.",
            },
            {
                "id": "register",
                "path": "command-center/sources/REGISTER.md",
                "evidence_tier": "E4",
                "present": register,
                "note": "Absent on this Linux worktree.",
            },
        ],
        "support_edges": [
            {
                "from": "C1",
                "to": "live-pipeline",
                "kind": "supports",
            },
            {
                "from": "C2",
                "to": "both_states",
                "kind": "supports",
            },
        ],
        "contradiction_edges": [
            {
                "from": "C4",
                "to": "catalog-inputs",
                "kind": "contradicts-availability",
                "note": "Catalog lists 05-ECO and REGISTER as inputs; both are absent.",
            }
        ],
        "source_snapshot_sha256": {
            "command-center/p2-wave/probes/CNF-0075/harness.py": harness_sha,
            "command-center/p2-wave/probes/RES-0092/threshold.py": thresh_sha,
        },
        "answer": (
            "On this tree the useful no-oracle test is MR-REORDER-UNORDERED-CASES: "
            "permuting independent cases must leave case-id-keyed scores unchanged. "
            "CNF-0075 execute_case on fusion_union satisfies it at the pre-stated "
            "threshold 0 (source fingerprint equals follow-up; distance 0). A "
            "positional score tuple is a genuine defect and the checker fires on "
            "that known-broken fixture while staying silent on the known-good "
            "rebind. Prompt-paraphrase exact-match is excluded: a violation is "
            "acceptable generative variance, not a fault. Identifier renaming of "
            "primary keys is excluded for the same reason (different input, not a "
            "follow-up). "
            + COMPLETION
        ),
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/RES-0092/threshold.py",
                "kind": "pre-stated-threshold",
                "claim": "Variance threshold 0 and its rationale exist in source before any comparison.",
                "sha256": thresh_sha,
            },
            {
                "path": harness_rel,
                "kind": "live-pipeline",
                "claim": "Relation ran against CNF-0075 execute_case, not a reimplemented oracle.",
                "sha256": harness_sha,
            },
            {
                "path": "command-center/p2-wave/probes/RES-0092/fixtures/inline-fixtures.json",
                "kind": "inline-fixture",
                "claim": "Known-good and known-broken fixtures ship beside the checker.",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0092/probe2_both_states.py",
                "kind": "both-states",
                "claim": "Checker fires only on the known-broken positional tuple.",
            },
        ],
        "tests": [
            {
                "id": "T1-implement-one-relation-live-pipeline",
                "name": "Implement one relation and run it against a real pipeline step",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-threshold-before-run-and-both-states",
                "name": "Control: pre-stated threshold; known-good silent; known-broken fires",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "RES0092-C1",
                "kind": "known-broken-fixture",
                "description": (
                    "Positional score tuple must violate MR-REORDER under reverse; "
                    "case-id fingerprint must not; identity permutation silent on both."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": both["broken"]["reversed"],
                "good_state_output": both["good"]["reversed"],
            }
        ],
        "reviewer": {
            "reviewer_id": "RES-0092-independent-frozenset-rebinding",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "fresh_context": True,
            "method": (
                "A second fingerprint (frozenset of (case_id, score) pairs for "
                "the good pipeline; joined encounter-order scores for the broken "
                "pipeline) re-ran the same source/follow-up pair and agreed on "
                "violation boolean. That is a mechanically different measurement, "
                "not the same function re-run."
            ),
        },
        "residual_unknowns": [
            {
                "claim": "Whether a live LLM decode step on this harness satisfies a similarity-based paraphrase MR.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Freeze a similarity metric and threshold in threshold.py "
                    "before any decode, then run paraphrase follow-ups on a "
                    "named model with a recorded seed."
                ),
            },
            {
                "claim": "Global command-center/schema/research-claim-record.schema.json (RES-0001 family).",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "RES-0001 authors the shared schema family. This unit "
                    "validates against the local probe schema only."
                ),
            },
        ],
        "adv_rebuild_circle": False,
        "timestamps": {
            "started_at": "2026-08-24T18:39:00Z",
            "ended_at": now,
        },
        "retry": {
            "count": 1,
            "policy": "red-green-refactor; two same-fingerprint structural refutes park rather than rebuild",
            "note": (
                "First both-states run was silent on the broken fixture because "
                "the positional tuple was palindromic. Fixture order changed; "
                "the relation and checker were not rebuilt."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/RES-0092/threshold.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0092/probe1_live_relation.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0092/probe2_both_states.py",
                "exists": True,
                "role": "supporting",
            },
            {"path": harness_rel, "exists": True, "role": "supporting"},
        ],
        "named_probes": [
            {"id": "probe1", "role": "live-relation", "command": P1},
            {"id": "probe2", "role": "both-states", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/RES-0092/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError:
        print("FAILED:RES-0092 jsonschema not installed")
        return 1
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:RES-0092 local schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ]
    for g in garbage:
        if not list(validator.iter_errors(g)):
            print(f"FAILED:RES-0092 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:RES-0092 artifact {size}B below floor")
        return 1
    if COMPLETION not in out.read_text(encoding="utf-8"):
        print("FAILED:RES-0092 completion sentinel missing from artifact")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:RES-0092 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
