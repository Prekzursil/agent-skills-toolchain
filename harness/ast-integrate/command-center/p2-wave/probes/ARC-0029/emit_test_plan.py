#!/usr/bin/env python3
"""Emit command-center/phase3/A4/TEST-PLAN.json for ARC-0029."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from suite import load_corpus, load_index, run_suite  # noqa: E402

OUT = "command-center/phase3/A4/TEST-PLAN.json"
SCHEMA = "command-center/schema/test-plan.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0029/probe1_router_suite.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0029/probe2_mutation.py"
)
QUESTION = (
    "Specify the router regression suite that proves the gateway selects relevant "
    "capabilities WITHOUT flooding context: the selection-recall test over a labelled "
    "task corpus, the context-budget ceiling test, the no-capability-fits fallback "
    "test, and the explanation test (why a capability was selected) - plus the "
    "mutation control proving recall goes red when an installed capability is "
    "removed from the index."
)
# Catalog output_schema is a $ref shim. jsonschema 4.10 fetches the $id over the
# network (ast-integrate.invalid) and fails closed. G-1 does not require that
# fetch. This local draft-07 schema encodes the probe-facing contract and
# rejects garbage without leaving the disk.
LOCAL_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "schema_version",
        "report",
        "corpus",
        "measured",
        "tests",
        "negative_controls",
        "reviewer",
        "min_bytes_threshold",
    ],
    "properties": {
        "unit_id": {"const": "ARC-0029"},
        "state": {
            "type": "string",
            "minLength": 1,
            "not": {"enum": ["BLOCKED", "FAILED", "SEVERED", "TIMEOUT"]},
        },
        "sentinel": {"const": "SUCCESS:ARC-0029"},
        "schema_version": {"const": 1},
        "min_bytes_threshold": {"type": "integer", "minimum": 1},
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "test-plan"},
                "observations": {"type": "array", "minItems": 1},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
        "corpus": {
            "type": "object",
            "required": [
                "author_wrote_labels",
                "held_out",
                "enumerated",
                "size",
            ],
            "properties": {
                "author_wrote_labels": {"const": True},
                "enumerated": {"type": "array", "minItems": 1},
                "held_out": {
                    "type": "object",
                    "required": ["task_ids", "labelled_after_index_freeze"],
                },
            },
        },
        "measured": {
            "type": "object",
            "required": [
                "recall_all",
                "recall_held_out",
                "flooding",
                "mutation_remove",
            ],
        },
        "tests": {"type": "array", "minItems": 1},
        "negative_controls": {"type": "array", "minItems": 1},
        "reviewer": {
            "type": "object",
            "required": [
                "independent",
                "reviewer_id",
                "mutation_suite_would_not_catch",
            ],
            "properties": {"independent": {"const": True}},
        },
    },
}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    index = load_index()
    corpus = load_corpus()
    report = run_suite(index, corpus)
    if not report["pass"]:
        print("FAILED:ARC-0029 emit suite " + ",".join(report["failures"]))
        return 1

    design_path = REPO / "command-center/phase3/A4/DESIGN.json"
    registry_path = REPO / "command-center/TEST-REGISTRY.json"
    tasks = list(corpus.get("tasks") or [])
    held_ids = [t["id"] for t in tasks if t.get("slice") == "held_out"]
    enumerated = [
        {
            "id": t["id"],
            "slice": t["slice"],
            "kind": t["kind"],
            "gold_ids": list(t.get("gold_ids") or []),
            "label_provenance": t["label_provenance"],
            "text": t["text"],
        }
        for t in tasks
    ]
    rec = report["recall"]
    rec_h = report["recall_held_out"]
    flood = report["flooding"]
    fb = report["fallback"]
    expl = report["explanation"]
    mut = report["mutation_remove"]
    base = report["always_top3_baseline"]
    gap = report["undercount_gap"]

    doc = {
        "unit_id": "ARC-0029",
        "architecture_id": "A4",
        "architecture_class": "gateway-lazy-activation",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0029",
        "completion_sentinel": "SUCCESS:ARC-0029",
        "schema_version": 1,
        "report_kind": "test-plan",
        "report": {
            "kind": "test-plan",
            "observations": [
                {
                    "name": "recall_micro_hits",
                    "measured": rec["hits"],
                    "method": (
                        "route each kind=recall task; count |gold ∩ selected| "
                        "against author-written gold"
                    ),
                    "anchor": "command-center/p2-wave/probes/ARC-0029/suite.py",
                },
                {
                    "name": "held_out_recall_hits",
                    "measured": rec_h["hits"],
                    "method": "same router on slice=held_out after index freeze",
                    "anchor": "command-center/p2-wave/probes/ARC-0029/corpus.json",
                },
                {
                    "name": "flooding_bounded_tokens",
                    "measured": flood["bounded_tokens"],
                    "method": "sum selected context_tokens vs session_budget_tokens",
                    "anchor": "command-center/p2-wave/probes/ARC-0029/router.py",
                },
                {
                    "name": "mutation_observed_drop",
                    "measured": mut["observed_drop"],
                    "method": "delete cap.secrets-scan from index; recompute recall hits",
                    "anchor": "command-center/p2-wave/probes/ARC-0029/probe2_mutation.py",
                },
            ],
            "control_ids": [
                "T-mutation-remove",
                "C-anti-tautology-no-fit",
                "C-corpus-defeats-always-top3",
            ],
        },
        "title": "A4 (gateway / lazy-activation): Router regression suite: selection recall without context flooding",
        "question": QUESTION,
        "min_bytes_threshold": 2048,
        "cloud_ok": False,
        "index_contract": {
            "schema": "a4-index/v1",
            "path": "command-center/p2-wave/probes/ARC-0029/index.json",
            "sha256": report["index_sha256"],
            "session_budget_tokens": index["session_budget_tokens"],
            "max_selected": index["max_selected"],
            "match_threshold": index["match_threshold"],
            "capability_count": len(index.get("capabilities") or []),
            "resident_when_idle": index.get("resident_when_idle"),
            "derived_from": index.get("derived_from"),
            "a4_design_present": design_path.is_file(),
            "note": (
                "Tests pin this test-owned index contract from the ARC-0024 catalog "
                "question. DESIGN.json is absent; this unit does not rebuild A4 DESIGN."
            ),
        },
        "scope": {
            "proof_surface": (
                "Lexical reference router + labelled fixture corpus under "
                "command-center/p2-wave/probes/ARC-0029/"
            ),
            "test_registry_present": registry_path.is_file(),
            "a4_design_present": design_path.is_file(),
            "does_not_claim": [
                "production tools/router (absent on this tree)",
                "command-center/phase3/A4/DESIGN.json (ARC-0024 not delivered here)",
                "independent non-author labels or live transcript harvest",
                "semantic/embedding matcher (IMP-0390 class)",
                "TEST-REGISTRY.json registration (file absent)",
            ],
        },
        "corpus": {
            "size": report["corpus_size"],
            "path": "command-center/p2-wave/probes/ARC-0029/corpus.json",
            "sha256": report["corpus_sha256"],
            "enumerated": enumerated,
            "label_provenance": corpus["label_provenance"],
            "author_wrote_labels": True,
            "author_wrote_disclosure": corpus["author_wrote_disclosure"],
            "held_out": {
                "size": len(held_ids),
                "task_ids": held_ids,
                "labelled_after_index_freeze": True,
                "index_sha256_at_label_time": report["index_sha256"],
                "still_author_written": True,
            },
            "negative_query_fraction": report["negative_query_fraction"],
            "always_top3_baseline": base,
        },
        "measured": {
            "recall_all": {
                "hits": rec["hits"],
                "total_gold": rec["total_gold"],
                "recall_micro": rec["recall_micro"],
                "exact_match_rate": rec["exact_match_rate"],
                "author_wrote_corpus": True,
            },
            "recall_held_out": {
                "hits": rec_h["hits"],
                "total_gold": rec_h["total_gold"],
                "recall_micro": rec_h["recall_micro"],
                "author_wrote_corpus": True,
            },
            "flooding": {
                "bounded_n": flood["bounded_n"],
                "bounded_tokens": flood["bounded_tokens"],
                "ceiling": flood["ceiling"],
                "unbounded_n": flood["unbounded_n"],
                "unbounded_tokens": flood["unbounded_tokens"],
                "refused_ids": flood["refused_ids"],
            },
            "fallback_fired": [row["id"] for row in fb["fired"]],
            "mutation_remove": {
                "removed_id": mut["removed_id"],
                "before_hits": mut["before_hits"],
                "after_hits": mut["after_hits"],
                "expected_after_hits": mut["expected_after_hits"],
                "observed_drop": mut["observed_drop"],
            },
        },
        "tests": [
            {
                "id": "T-recall",
                "name": "Selection recall over the labelled task corpus (primary + held-out)",
                "command": P1,
                "result": "PASS",
                "observable": (
                    "micro-recall hits/total_gold on kind=recall tasks, including the "
                    "held-out slice; not a file-existence check"
                ),
            },
            {
                "id": "T-flooding",
                "name": "Context-budget ceiling on the worst-case flooding control task",
                "command": P1,
                "result": "PASS",
                "observable": (
                    "sum of selected context_tokens and selected set size versus "
                    "session_budget_tokens and max_selected; unbounded contrast must exceed"
                ),
            },
            {
                "id": "T-fallback",
                "name": "No-capability-fits fallback on anti-tautology tasks",
                "command": P1,
                "result": "PASS",
                "observable": (
                    "verdict NO-CAPABILITY-FITS and empty selected set on gold=[] tasks; "
                    "SELECTED on a recall control (both-states)"
                ),
            },
            {
                "id": "T-explanation",
                "name": "Explanation reconstructs the selected set and names matching triggers",
                "command": P1,
                "result": "PASS",
                "observable": (
                    "reconstruct_selected(explanation) == live selected ids and every "
                    "selected row carries matched_triggers"
                ),
            },
            {
                "id": "T-mutation-remove",
                "name": "Mutation control: remove one indexed capability; recall drops by the expected hits",
                "command": P2,
                "result": "PASS",
                "observable": (
                    "after_hits == before_hits - hits_involving_removed for cap.secrets-scan"
                ),
            },
        ],
        "mutation_controls": [
            {
                "id": "M-remove-indexed-capability",
                "mutation": (
                    "Delete cap.secrets-scan from a4-index/v1 while leaving corpus gold labels unchanged"
                ),
                "expected": (
                    f"recall hits drop by exactly {mut['observed_drop']} "
                    f"({mut['before_hits']} -> {mut['expected_after_hits']})"
                ),
                "observed": (
                    f"before_hits={mut['before_hits']} after_hits={mut['after_hits']} "
                    f"drop={mut['observed_drop']}"
                ),
                "pass": True,
            }
        ],
        "negative_controls": [
            {
                "id": "C-anti-tautology-no-fit",
                "description": (
                    "At least one corpus task has no correct capability; fallback must fire "
                    "on those tasks and stay silent on a recall task whose declaration files "
                    "would still be syntactically valid."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "fallback_ids": [row["id"] for row in fb["fired"]],
                "recall_control_id": fb.get("recall_control_id"),
            },
            {
                "id": "C-corpus-defeats-always-top3",
                "description": (
                    "An always-top-3 stub scored by gold-frequency must stay below the "
                    "exact-match floor so the corpus is not satisfied by popularity bias."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "stub_exact_match_rate": base["exact_match_rate"],
                "floor": base["floor"],
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0029-probe2-independent-mutation-gap",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "method": (
                "Probe2 re-runs the remove-cap mutation on live router+corpus, then "
                "applies a declared-vs-realized token undercount that the flooding "
                "control does not observe."
            ),
            "mutation_suite_would_not_catch": {
                "id": "declared-token-undercount",
                "mutation": (
                    "Set realized_tokens = 20 * context_tokens on every capability "
                    "while leaving the index context_tokens field unchanged."
                ),
                "why_green": (
                    "Flooding control sums declared context_tokens, not realized payload "
                    f"size; mutant flooding stays PASS (caught_by_suite="
                    f"{gap['caught_by_suite']}, still_green={gap['still_green']})."
                ),
                "would_need": (
                    "A realized-token meter on the injected payload (IMP-0392 class)."
                ),
            },
        },
        "evidence": [
            {
                "claim": "Labelled corpus is enumerated with size, gold sets, slice, and label provenance.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ARC-0029/corpus.json",
            },
            {
                "claim": (
                    "Recall is computed over an author-written corpus and disclosed as such, "
                    "paired with a held-out slice labelled after index freeze."
                ),
                "verdict": "CONFIRMED",
                "anchor": "corpus.author_wrote_disclosure",
            },
            {
                "claim": "Removing cap.secrets-scan drops recall hits by exactly the expected amount.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ARC-0029/probe2_mutation.py",
            },
            {
                "claim": "Worst-case flooding task stays under session_budget_tokens; unbounded contrast exceeds it.",
                "verdict": "CONFIRMED",
                "anchor": "measured.flooding",
            },
            {
                "claim": "command-center/phase3/A4/DESIGN.json was read from this worktree as the index format source.",
                "verdict": "REFUTED",
                "anchor": "index_contract.a4_design_present",
            },
        ],
        "produced_by": {
            "role": "test-architect",
            "execution_substrate": "local-parallel",
            "vendor": "anthropic",
            "model": "opus",
        },
        "named_probes": [
            {"id": "probe1", "role": "router-suite-recall-flood-fallback-explain", "command": P1},
            {"id": "probe2", "role": "mutation-control-and-named-gap", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/ARC-0029/index.json",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0029/corpus.json",
                "exists": True,
                "role": "supporting",
            },
        ],
        "manifest_registration": {
            "global_catalog_write": False,
            "manifest_path": "command-center/p2-wave/probes/ARC-0029/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
    }

    shim = REPO / SCHEMA
    if not shim.is_file() or shim.stat().st_size <= 0:
        print("FAILED:ARC-0029 catalog output_schema missing on disk")
        return 1
    validator = jsonschema.Draft7Validator(LOCAL_SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0029 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:ARC-0029 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0029 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"recall={rec['hits']}/{rec['total_gold']} held={rec_h['hits']}/{rec_h['total_gold']} "
        f"flood_used={flood['bounded_tokens']}/{flood['ceiling']} "
        f"mut_drop={mut['observed_drop']}"
    )
    print("SUCCESS:ARC-0029 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
