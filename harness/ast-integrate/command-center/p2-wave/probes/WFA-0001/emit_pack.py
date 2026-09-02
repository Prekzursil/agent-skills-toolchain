#!/usr/bin/env python3
"""Emit command-center/wfa/schema/wfa-schema-pack.json (WFA-0001)."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pack_lib as L  # noqa: E402

DISPOSITIONS = [
    "ADOPT-AS-IS",
    "ADOPT-WITH-WRAPPER",
    "UNKNOWN-NEEDS-PROBE",
    "DISTILL",
    "RETIRE",
    "REPAIR",
    "EXTEND",
    "MERGE",
    "SPECIALIZE",
    "CLEAN-ROOM-REIMPLEMENT",
    "COMPOSE",
    "GENERALIZE",
    "REBUILD-FROM-SPEC",
    "REJECT",
    "TRANSLATE",
]

DIMENSIONS = [
    "provenance_anchor",
    "license",
    "maintenance_state",
    "task_taxonomy",
    "stages",
    "roles",
    "tool_permission_surface",
    "stopping_rule",
    "failure_behaviour",
    "benchmark_evidence",
]

CELL_STATES = ["EVIDENCED", "HONEST-NULL", "EMPTY"]

UNIT_ID = {"type": "string", "pattern": r"^WFA-[0-9]{4}$", "minLength": 8}
NON_EMPTY = {"type": "string", "minLength": 1}
ANCHOR = {"type": "string", "minLength": 8}
PATH = {"type": "string", "minLength": 8}
CLAIM = {"type": "string", "minLength": 8}
STATE = {
    "type": "string",
    "enum": ["SUCCESS", "PARTIAL", "BLOCKED", "FAILED", "TIMEOUT", "SEVERED"],
}


def closed(required: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


def envelope(record_type: str, extra_required: list[str], extra_props: dict[str, Any]) -> dict[str, Any]:
    props = {
        "record_type": {"type": "string", "const": record_type},
        "unit_id": UNIT_ID,
        "state": STATE,
        "sentinel": {"type": "string", "minLength": 8},
        "evidence": {
            "type": "array",
            "items": closed(["path", "claim"], {"path": PATH, "claim": CLAIM}),
        },
        "reviewer": closed(
            ["reviewer_id", "verdict", "independent"],
            {
                "reviewer_id": {"type": "string", "minLength": 3},
                "verdict": {"type": "string", "enum": ["PASS", "FAIL", "NOT-CHECKED"]},
                "independent": {"type": "boolean"},
            },
        ),
        "notes": {"type": "string", "minLength": 1},
    }
    props.update(extra_props)
    return closed(["record_type", "unit_id"] + extra_required, props)


def evidence_row(path: str, claim: str) -> dict[str, str]:
    return {"path": path, "claim": claim}


def reviewer_pass(rid: str) -> dict[str, Any]:
    return {"reviewer_id": rid, "verdict": "PASS", "independent": True}


def candidate_schema() -> dict[str, Any]:
    return closed(
        [
            "id",
            "name",
            "family",
            "classification",
            "origin",
            "does",
            "mechanisms",
            "license_class",
            "provenance_anchor",
            "source_uri",
            "content_hash",
            "maintenance_state",
            "task_classes",
        ],
        {
            "id": {"type": "string", "minLength": 3},
            "name": {"type": "string", "minLength": 3},
            "family": {"type": "string", "minLength": 1},
            "classification": {"type": "string", "enum": DISPOSITIONS},
            "origin": {"type": "string", "minLength": 3},
            "does": {"type": "string", "minLength": 8},
            "mechanisms": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 2},
            },
            "license_class": {"type": "string", "minLength": 3},
            "provenance_anchor": ANCHOR,
            "source_uri": {"type": "string", "minLength": 8},
            "content_hash": {"type": "string", "minLength": 8},
            "maintenance_state": {
                "type": "string",
                "enum": ["ACTIVE", "ARCHIVED", "STALE", "UNKNOWN", "OWNER-MAINTAINED"],
            },
            "task_classes": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 2},
            },
        },
    )


def sample_candidate() -> dict[str, Any]:
    return {
        "id": "wf-0001",
        "name": "saved-workflow-gate",
        "family": "H-executed-corpus",
        "classification": "ADOPT-AS-IS",
        "origin": "live:~/.claude/workflows/plan-gate.mjs",
        "does": "Serialises a plan gate before a design gate.",
        "mechanisms": ["typed-fan-in", "barrier"],
        "license_class": "OWNER-AUTHORED",
        "provenance_anchor": "HEAD:workflows/plan-gate.mjs:1",
        "source_uri": "file://workflows/plan-gate.mjs",
        "content_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "maintenance_state": "OWNER-MAINTAINED",
        "task_classes": ["orchestration-gate"],
    }


def node_schema() -> dict[str, Any]:
    return closed(
        ["id", "kind", "source_anchor"],
        {
            "id": NON_EMPTY,
            "kind": {
                "type": "string",
                "enum": [
                    "stage",
                    "role",
                    "gate",
                    "barrier",
                    "loop",
                    "checkpoint",
                    "retry",
                    "stop",
                    "mechanism",
                    "blueprint",
                    "candidate",
                    "licence",
                    "other",
                ],
            },
            "source_anchor": ANCHOR,
            "label": NON_EMPTY,
            "license_class": NON_EMPTY,
        },
    )


def edge_schema() -> dict[str, Any]:
    return closed(
        ["source", "target", "relation"],
        {
            "source": NON_EMPTY,
            "target": NON_EMPTY,
            "relation": {
                "type": "string",
                "enum": [
                    "compat",
                    "implements",
                    "requires",
                    "conflicts-with",
                    "substitutes-for",
                    "derived-from",
                    "cites",
                    "other",
                ],
            },
        },
    )


def cell_count_schema() -> dict[str, Any]:
    return closed(
        ["name", "evidenced", "honest_null", "empty"],
        {
            "name": NON_EMPTY,
            "evidenced": {"type": "integer", "minimum": 0},
            "honest_null": {"type": "integer", "minimum": 0},
            "empty": {"type": "integer", "minimum": 0},
        },
    )


def attach_examples(defn: dict[str, Any], valid: dict[str, Any]) -> dict[str, Any]:
    invalid = deepcopy(valid)
    invalid[L.EXTRA_KEY] = True
    out = deepcopy(defn)
    out["examples"] = [valid]
    out["x-valid-example"] = valid
    out["x-invalid-example"] = invalid
    return out


def build_defs() -> dict[str, dict[str, Any]]:
    defs: dict[str, dict[str, Any]] = {}

    defs["WorkflowRecord"] = attach_examples(
        envelope(
            "WorkflowRecord",
            ["records", "counts"],
            {
                "records": {"type": "array", "minItems": 1, "items": candidate_schema()},
                "counts": closed(
                    ["record_count"],
                    {"record_count": {"type": "integer", "minimum": 1}},
                ),
            },
        ),
        {
            "record_type": "WorkflowRecord",
            "unit_id": "WFA-0078",
            "state": "SUCCESS",
            "sentinel": "SUCCESS:WFA-0078",
            "records": [sample_candidate()],
            "counts": {"record_count": 1},
            "evidence": [
                evidence_row(
                    "command-center/wfa/schema/wfa-schema-pack.json",
                    "Registry v2 validates as WorkflowRecord.",
                )
            ],
            "reviewer": reviewer_pass("WFA-0001-pack"),
        },
    )

    defs["SweepReport"] = attach_examples(
        envelope(
            "SweepReport",
            ["corpus", "classified", "ambiguous", "provenance_rule"],
            {
                "corpus": closed(
                    ["root", "commit"],
                    {"root": PATH, "commit": {"type": "string", "minLength": 7}},
                ),
                "classified": {
                    "type": "array",
                    "minItems": 1,
                    "items": closed(
                        ["path", "verdict", "commit"],
                        {
                            "path": PATH,
                            "verdict": {
                                "type": "string",
                                "enum": ["WORKFLOW", "NOT-WORKFLOW", "AMBIGUOUS"],
                            },
                            "commit": {"type": "string", "minLength": 7},
                        },
                    ),
                },
                "ambiguous": {
                    "type": "array",
                    "items": closed(
                        ["path", "reason"],
                        {"path": PATH, "reason": CLAIM},
                    ),
                },
                "provenance_rule": {
                    "type": "string",
                    "const": "commit-anchored-blob-not-working-tree",
                },
                "new_candidates": {"type": "integer", "minimum": 0},
            },
        ),
        {
            "record_type": "SweepReport",
            "unit_id": "WFA-0013",
            "corpus": {"root": "command-center", "commit": "deadbeef"},
            "classified": [
                {
                    "path": "tools/foundry/workflows/workflow-scout.json",
                    "verdict": "WORKFLOW",
                    "commit": "deadbeef",
                }
            ],
            "ambiguous": [],
            "provenance_rule": "commit-anchored-blob-not-working-tree",
            "new_candidates": 0,
        },
    )

    defs["ProbeReport"] = attach_examples(
        envelope(
            "ProbeReport",
            ["probes", "both_states"],
            {
                "probes": {
                    "type": "array",
                    "minItems": 1,
                    "items": closed(
                        ["id", "command", "exit_code", "verdict"],
                        {
                            "id": NON_EMPTY,
                            "command": {"type": "string", "minLength": 3},
                            "exit_code": {"type": "integer", "minimum": 0},
                            "verdict": {
                                "type": "string",
                                "enum": ["PASS", "FAIL", "NOT-RUN"],
                            },
                        },
                    ),
                },
                "both_states": closed(
                    ["good_passes", "bad_fails"],
                    {
                        "good_passes": {"type": "boolean"},
                        "bad_fails": {"type": "boolean"},
                        "bad_fixture": NON_EMPTY,
                    },
                ),
            },
        ),
        {
            "record_type": "ProbeReport",
            "unit_id": "WFA-0002",
            "probes": [
                {
                    "id": "closure",
                    "command": "python3 -B probes/check_closure.py",
                    "exit_code": 0,
                    "verdict": "PASS",
                }
            ],
            "both_states": {
                "good_passes": True,
                "bad_fails": True,
                "bad_fixture": "reinjected unresolved ref wf-missing",
            },
        },
    )

    defs["ExtractionReport"] = attach_examples(
        envelope(
            "ExtractionReport",
            ["dimension", "records", "unresolved"],
            {
                "dimension": {"type": "string", "enum": DIMENSIONS},
                "records": {
                    "type": "array",
                    "minItems": 1,
                    "items": closed(
                        ["candidate_id", "cell_state"],
                        {
                            "candidate_id": {"type": "string", "minLength": 3},
                            "cell_state": {"type": "string", "enum": CELL_STATES},
                            "value": {"type": "string", "minLength": 1},
                            "anchor": ANCHOR,
                        },
                    ),
                },
                "unresolved": {
                    "type": "array",
                    "items": closed(
                        ["candidate_id", "failing_route"],
                        {
                            "candidate_id": {"type": "string", "minLength": 3},
                            "failing_route": {"type": "string", "minLength": 3},
                        },
                    ),
                },
            },
        ),
        {
            "record_type": "ExtractionReport",
            "unit_id": "WFA-0032",
            "dimension": "provenance_anchor",
            "records": [
                {
                    "candidate_id": "wf-0001",
                    "cell_state": "EVIDENCED",
                    "value": "HEAD:workflows/plan-gate.mjs:1",
                    "anchor": "HEAD:workflows/plan-gate.mjs:1",
                }
            ],
            "unresolved": [],
        },
    )

    defs["DispositionRecord"] = attach_examples(
        envelope(
            "DispositionRecord",
            ["vocabulary", "decisions", "tie_break_order", "refusal_path"],
            {
                "vocabulary": {
                    "type": "array",
                    "minItems": 15,
                    "maxItems": 15,
                    "items": {"type": "string", "enum": DISPOSITIONS},
                },
                "decisions": {
                    "type": "array",
                    "minItems": 1,
                    "items": closed(
                        ["candidate_id", "disposition", "criteria_id"],
                        {
                            "candidate_id": {"type": "string", "minLength": 3},
                            "disposition": {"type": "string", "enum": DISPOSITIONS},
                            "criteria_id": NON_EMPTY,
                            "inputs_missing": {"type": "boolean"},
                        },
                    ),
                },
                "tie_break_order": {
                    "type": "array",
                    "minItems": 2,
                    "items": NON_EMPTY,
                },
                "refusal_path": {
                    "type": "string",
                    "const": "UNKNOWN-NEEDS-PROBE",
                },
            },
        ),
        {
            "record_type": "DispositionRecord",
            "unit_id": "WFA-0068",
            "vocabulary": list(DISPOSITIONS),
            "decisions": [
                {
                    "candidate_id": "wf-0001",
                    "disposition": "ADOPT-AS-IS",
                    "criteria_id": "C-ADOPT-EXECUTABLE",
                    "inputs_missing": False,
                }
            ],
            "tie_break_order": ["UNKNOWN-NEEDS-PROBE", "REPAIR", "ADOPT-AS-IS"],
            "refusal_path": "UNKNOWN-NEEDS-PROBE",
        },
    )

    defs["Graph"] = attach_examples(
        envelope(
            "Graph",
            ["nodes", "edges", "directed", "counts"],
            {
                "nodes": {"type": "array", "minItems": 1, "items": node_schema()},
                "edges": {"type": "array", "items": edge_schema()},
                "directed": {"type": "boolean"},
                "counts": closed(
                    ["node_count", "edge_count"],
                    {
                        "node_count": {"type": "integer", "minimum": 1},
                        "edge_count": {"type": "integer", "minimum": 0},
                    },
                ),
                "invariants": {
                    "type": "array",
                    "items": closed(
                        ["name", "holds"],
                        {"name": NON_EMPTY, "holds": {"type": "boolean"}},
                    ),
                },
            },
        ),
        {
            "record_type": "Graph",
            "unit_id": "WFA-0004",
            "nodes": [
                {
                    "id": "BP-001",
                    "kind": "blueprint",
                    "source_anchor": "09-WORKFLOW-BLUEPRINT-LIBRARY.json#BP-001",
                    "label": "discovery-only",
                },
                {
                    "id": "BP-002",
                    "kind": "blueprint",
                    "source_anchor": "09-WORKFLOW-BLUEPRINT-LIBRARY.json#BP-002",
                    "label": "editable",
                },
            ],
            "edges": [
                {
                    "source": "BP-001",
                    "target": "BP-002",
                    "relation": "compat",
                },
                {
                    "source": "BP-002",
                    "target": "BP-001",
                    "relation": "compat",
                },
            ],
            "directed": True,
            "counts": {"node_count": 2, "edge_count": 2},
            "invariants": [{"name": "compat-symmetric", "holds": True}],
        },
    )

    defs["WorkflowIR"] = attach_examples(
        envelope(
            "WorkflowIR",
            ["ir_version", "has_runtime_entrypoint", "nodes", "lossy_field_ledger"],
            {
                "ir_version": {"type": "string", "minLength": 1},
                "has_runtime_entrypoint": {"type": "boolean", "const": False},
                "nodes": {
                    "type": "array",
                    "minItems": 1,
                    "items": closed(
                        ["id", "kind", "source_anchor"],
                        {
                            "id": NON_EMPTY,
                            "kind": {
                                "type": "string",
                                "enum": [
                                    "stage",
                                    "role",
                                    "gate",
                                    "barrier",
                                    "loop",
                                    "checkpoint",
                                    "retry",
                                    "stop",
                                    "fan-out",
                                    "other",
                                ],
                            },
                            "source_anchor": ANCHOR,
                            "inputs": {
                                "type": "array",
                                "items": closed(
                                    ["name", "type"],
                                    {"name": NON_EMPTY, "type": NON_EMPTY},
                                ),
                            },
                            "outputs": {
                                "type": "array",
                                "items": closed(
                                    ["name", "type"],
                                    {"name": NON_EMPTY, "type": NON_EMPTY},
                                ),
                            },
                        },
                    ),
                },
                "lossy_field_ledger": {
                    "type": "array",
                    "items": closed(
                        ["construct", "reason"],
                        {"construct": NON_EMPTY, "reason": CLAIM},
                    ),
                },
            },
        ),
        {
            "record_type": "WorkflowIR",
            "unit_id": "WFA-0044",
            "ir_version": "wfa-ir/v1",
            "has_runtime_entrypoint": False,
            "nodes": [
                {
                    "id": "stage-plan-gate",
                    "kind": "gate",
                    "source_anchor": "live:workflows/plan-gate.mjs:12",
                    "inputs": [{"name": "plan", "type": "PlanDoc"}],
                    "outputs": [{"name": "verdict", "type": "GateVerdict"}],
                }
            ],
            "lossy_field_ledger": [],
        },
    )

    defs["AdapterConformanceReport"] = attach_examples(
        envelope(
            "AdapterConformanceReport",
            ["adapter_id", "dialect", "parsed", "uncarryable", "counts"],
            {
                "adapter_id": NON_EMPTY,
                "dialect": NON_EMPTY,
                "parsed": {
                    "type": "array",
                    "minItems": 1,
                    "items": closed(
                        ["source_path", "accepted"],
                        {
                            "source_path": PATH,
                            "accepted": {"type": "boolean"},
                            "agent_sites": {"type": "integer", "minimum": 0},
                            "phases": {"type": "integer", "minimum": 0},
                            "barriers": {"type": "integer", "minimum": 0},
                        },
                    ),
                },
                "uncarryable": {
                    "type": "array",
                    "items": closed(
                        ["construct", "source_path"],
                        {
                            "construct": NON_EMPTY,
                            "source_path": PATH,
                            "reason": CLAIM,
                        },
                    ),
                },
                "counts": closed(
                    ["parsed", "refused"],
                    {
                        "parsed": {"type": "integer", "minimum": 0},
                        "refused": {"type": "integer", "minimum": 0},
                    },
                ),
            },
        ),
        {
            "record_type": "AdapterConformanceReport",
            "unit_id": "WFA-0045",
            "adapter_id": "claude-code-saved-workflow",
            "dialect": "agent/parallel/phase globals",
            "parsed": [
                {
                    "source_path": "live/workflows/plan-gate.mjs",
                    "accepted": True,
                    "agent_sites": 2,
                    "phases": 3,
                    "barriers": 1,
                }
            ],
            "uncarryable": [],
            "counts": {"parsed": 1, "refused": 0},
        },
    )

    defs["SemanticDiff"] = attach_examples(
        envelope(
            "SemanticDiff",
            ["scope", "pairs", "collapse_count", "remaining_distinct"],
            {
                "scope": {"type": "string", "const": "LEXICAL"},
                "pairs": {
                    "type": "array",
                    "items": closed(
                        ["left_id", "right_id", "jaccard", "verdict"],
                        {
                            "left_id": {"type": "string", "minLength": 3},
                            "right_id": {"type": "string", "minLength": 3},
                            "jaccard": {"type": "number", "minimum": 0},
                            "verdict": {
                                "type": "string",
                                "enum": ["NEAR-DUPLICATE", "DISTINCT", "PLANTED-MUTANT"],
                            },
                        },
                    ),
                },
                "collapse_count": {"type": "integer", "minimum": 0},
                "remaining_distinct": {"type": "integer", "minimum": 0},
                "settling_experiment": CLAIM,
            },
        ),
        {
            "record_type": "SemanticDiff",
            "unit_id": "WFA-0007",
            "scope": "LEXICAL",
            "pairs": [
                {
                    "left_id": "wf-0001",
                    "right_id": "wf-0001-rename",
                    "jaccard": 0.95,
                    "verdict": "NEAR-DUPLICATE",
                }
            ],
            "collapse_count": 1,
            "remaining_distinct": 283,
            "settling_experiment": "embedding rescan for deep paraphrase",
        },
    )

    defs["FusionResult"] = attach_examples(
        envelope(
            "FusionResult",
            ["strategy", "host_id", "donor_id", "refused", "lineage"],
            {
                "strategy": {
                    "type": "string",
                    "enum": [
                        "stage-splice",
                        "prefix",
                        "suffix",
                        "interleave",
                        "replace-stage",
                    ],
                },
                "host_id": NON_EMPTY,
                "donor_id": NON_EMPTY,
                "refused": {"type": "boolean"},
                "refusal_reason": CLAIM,
                "insertion_index": {"type": "integer", "minimum": 0},
                "lineage": {
                    "type": "array",
                    "minItems": 1,
                    "items": closed(
                        ["node_id", "source_anchor"],
                        {"node_id": NON_EMPTY, "source_anchor": ANCHOR},
                    ),
                },
                "untouched_byte_identical": {"type": "boolean"},
            },
        ),
        {
            "record_type": "FusionResult",
            "unit_id": "WFA-0100",
            "strategy": "stage-splice",
            "host_id": "wf-host",
            "donor_id": "wf-donor",
            "refused": False,
            "insertion_index": 1,
            "lineage": [
                {
                    "node_id": "stage-plan-gate",
                    "source_anchor": "live:workflows/plan-gate.mjs:12",
                }
            ],
            "untouched_byte_identical": True,
        },
    )

    defs["BenchmarkResult"] = attach_examples(
        envelope(
            "BenchmarkResult",
            ["corpus_id", "cases", "raw_repetitions"],
            {
                "corpus_id": NON_EMPTY,
                "cases": {
                    "type": "array",
                    "minItems": 1,
                    "items": closed(
                        ["case_id", "family", "oracle"],
                        {
                            "case_id": NON_EMPTY,
                            "family": NON_EMPTY,
                            "oracle": CLAIM,
                            "postcondition_on_artifact": {"type": "boolean"},
                        },
                    ),
                },
                "raw_repetitions": {
                    "type": "array",
                    "minItems": 1,
                    "items": closed(
                        ["order", "case_id", "passed"],
                        {
                            "order": {"type": "integer", "minimum": 1},
                            "case_id": NON_EMPTY,
                            "passed": {"type": "boolean"},
                            "wall_ms": {"type": "number", "minimum": 0},
                        },
                    ),
                },
            },
        ),
        {
            "record_type": "BenchmarkResult",
            "unit_id": "WFA-0112",
            "corpus_id": "wfa-matched-family-v1",
            "cases": [
                {
                    "case_id": "gate-family-01",
                    "family": "orchestration-gate",
                    "oracle": "artifact exists and schema-validates",
                    "postcondition_on_artifact": True,
                }
            ],
            "raw_repetitions": [
                {
                    "order": 1,
                    "case_id": "gate-family-01",
                    "passed": True,
                    "wall_ms": 12.5,
                }
            ],
        },
    )

    defs["CertificationRecord"] = attach_examples(
        envelope(
            "CertificationRecord",
            [
                "subject_id",
                "certified",
                "conditions",
                "capability_loss",
                "control_plane_count",
            ],
            {
                "subject_id": NON_EMPTY,
                "certified": {"type": "boolean"},
                "conditions": {
                    "type": "array",
                    "minItems": 1,
                    "items": closed(
                        ["id", "holds"],
                        {"id": NON_EMPTY, "holds": {"type": "boolean"}, "note": CLAIM},
                    ),
                },
                "capability_loss": {"type": "boolean"},
                "control_plane_count": {"type": "integer", "minimum": 1},
            },
        ),
        {
            "record_type": "CertificationRecord",
            "unit_id": "WFA-0118",
            "subject_id": "wf-fused-01",
            "certified": True,
            "conditions": [
                {
                    "id": "matched-pair-advantage",
                    "holds": True,
                    "note": "Advantage above variance floor on the matched corpus.",
                }
            ],
            "capability_loss": False,
            "control_plane_count": 1,
        },
    )

    defs["RegressionFixture"] = attach_examples(
        envelope(
            "RegressionFixture",
            ["guard_id", "planted_bad", "planted_good", "silent_on_good", "loud_on_bad"],
            {
                "guard_id": NON_EMPTY,
                "planted_bad": CLAIM,
                "planted_good": CLAIM,
                "silent_on_good": {"type": "boolean", "const": True},
                "loud_on_bad": {"type": "boolean", "const": True},
                "detected_name": NON_EMPTY,
            },
        ),
        {
            "record_type": "RegressionFixture",
            "unit_id": "WFA-0056",
            "guard_id": "second-control-plane",
            "planted_bad": "import of a torn-down scheduler runtime",
            "planted_good": "library dependency with no execution order ownership",
            "silent_on_good": True,
            "loud_on_bad": True,
            "detected_name": "torn-down-scheduler",
        },
    )

    defs["AuditReport"] = attach_examples(
        envelope(
            "AuditReport",
            ["subject", "findings"],
            {
                "subject": CLAIM,
                "findings": {
                    "type": "array",
                    "minItems": 1,
                    "items": closed(
                        ["id", "severity", "summary"],
                        {
                            "id": NON_EMPTY,
                            "severity": {
                                "type": "string",
                                "enum": ["INFO", "WARNING", "COLLISION", "ABSENT", "ERROR"],
                            },
                            "summary": CLAIM,
                            "token": NON_EMPTY,
                        },
                    ),
                },
                "collisions": {
                    "type": "array",
                    "items": closed(
                        ["token", "left_title", "right_title"],
                        {
                            "token": NON_EMPTY,
                            "left_title": NON_EMPTY,
                            "right_title": NON_EMPTY,
                        },
                    ),
                },
                "absents": {
                    "type": "array",
                    "items": closed(
                        ["token", "cited_from"],
                        {"token": NON_EMPTY, "cited_from": PATH},
                    ),
                },
            },
        ),
        {
            "record_type": "AuditReport",
            "unit_id": "WFA-0003",
            "subject": "workflow id namespace collision audit",
            "findings": [
                {
                    "id": "F-ABSENT-M12",
                    "severity": "ABSENT",
                    "summary": "Pinned option id M-12 resolves to no record.",
                    "token": "M-12",
                }
            ],
            "collisions": [],
            "absents": [
                {
                    "token": "M-12",
                    "cited_from": "command-center/WORK-UNIT-CATALOG.json",
                }
            ],
        },
    )

    defs["HandoffContract"] = attach_examples(
        envelope(
            "HandoffContract",
            ["contract_version", "artifacts", "consumers", "residual_unknowns"],
            {
                "contract_version": {"type": "string", "minLength": 1},
                "artifacts": {
                    "type": "array",
                    "minItems": 1,
                    "items": closed(
                        ["path", "schema_ref"],
                        {"path": PATH, "schema_ref": PATH, "unit_id": UNIT_ID},
                    ),
                },
                "consumers": {
                    "type": "array",
                    "minItems": 1,
                    "items": closed(
                        ["bucket", "artifact_path"],
                        {"bucket": NON_EMPTY, "artifact_path": PATH},
                    ),
                },
                "residual_unknowns": {
                    "type": "array",
                    "items": closed(
                        ["id", "owned_by"],
                        {"id": NON_EMPTY, "owned_by": NON_EMPTY, "note": CLAIM},
                    ),
                },
            },
        ),
        {
            "record_type": "HandoffContract",
            "unit_id": "WFA-0126",
            "contract_version": "wfa-handoff/v1",
            "artifacts": [
                {
                    "path": "command-center/wfa/schema/wfa-schema-pack.json",
                    "schema_ref": "command-center/wfa/schema/wfa-schema-pack.json",
                    "unit_id": "WFA-0001",
                }
            ],
            "consumers": [
                {
                    "bucket": "implementation",
                    "artifact_path": "command-center/wfa/schema/wfa-schema-pack.json",
                }
            ],
            "residual_unknowns": [],
        },
    )

    defs["MechanismRecord"] = attach_examples(
        envelope(
            "MechanismRecord",
            ["vocabulary_version", "mechanisms"],
            {
                "vocabulary_version": {"type": "string", "minLength": 1},
                "mechanisms": {
                    "type": "array",
                    "minItems": 1,
                    "items": closed(
                        ["id", "definition", "discriminating_example"],
                        {
                            "id": {"type": "string", "minLength": 3},
                            "definition": CLAIM,
                            "discriminating_example": CLAIM,
                            "namespace": NON_EMPTY,
                        },
                    ),
                },
                "unmapped_strings": {
                    "type": "array",
                    "items": NON_EMPTY,
                },
            },
        ),
        {
            "record_type": "MechanismRecord",
            "unit_id": "WFA-0058",
            "vocabulary_version": "wfa-mech/v1",
            "mechanisms": [
                {
                    "id": "mec.typed-fan-in",
                    "definition": "Schema-typed join of parallel branch outputs.",
                    "discriminating_example": "parallel() results merged by schema, not by array concat.",
                    "namespace": "mechanism",
                }
            ],
            "unmapped_strings": [],
        },
    )

    defs["RepairRecord"] = attach_examples(
        envelope(
            "RepairRecord",
            ["defect_id", "repair", "mutation_red", "mutation_green"],
            {
                "defect_id": NON_EMPTY,
                "repair": closed(
                    ["summary", "path"],
                    {"summary": CLAIM, "path": PATH},
                ),
                "mutation_red": {"type": "boolean", "const": True},
                "mutation_green": {"type": "boolean", "const": True},
                "reverted_fix_turns_suite_red": {"type": "boolean"},
            },
        ),
        {
            "record_type": "RepairRecord",
            "unit_id": "WFA-0086",
            "defect_id": "asymmetric-compat-BP-001-BP-002",
            "repair": {
                "summary": "Add the missing reverse compat declaration.",
                "path": "command-center/wfa/WFA-0004-compat-symmetric.json",
            },
            "mutation_red": True,
            "mutation_green": True,
            "reverted_fix_turns_suite_red": True,
        },
    )

    defs["CoverageMatrix"] = attach_examples(
        envelope(
            "CoverageMatrix",
            ["dimensions", "families", "totals", "states_collapsed"],
            {
                "dimensions": {
                    "type": "array",
                    "minItems": 1,
                    "items": cell_count_schema(),
                },
                "families": {
                    "type": "array",
                    "minItems": 1,
                    "items": cell_count_schema(),
                },
                "totals": closed(
                    ["evidenced", "honest_null", "empty", "cells"],
                    {
                        "evidenced": {"type": "integer", "minimum": 0},
                        "honest_null": {"type": "integer", "minimum": 0},
                        "empty": {"type": "integer", "minimum": 0},
                        "cells": {"type": "integer", "minimum": 1},
                    },
                ),
                "states_collapsed": {"type": "boolean", "const": False},
            },
        ),
        {
            "record_type": "CoverageMatrix",
            "unit_id": "WFA-0043",
            "dimensions": [
                {
                    "name": "provenance_anchor",
                    "evidenced": 200,
                    "honest_null": 40,
                    "empty": 44,
                }
            ],
            "families": [
                {
                    "name": "G-skill",
                    "evidenced": 50,
                    "honest_null": 20,
                    "empty": 26,
                }
            ],
            "totals": {
                "evidenced": 200,
                "honest_null": 40,
                "empty": 44,
                "cells": 284,
            },
            "states_collapsed": False,
        },
    )

    missing = [n for n in L.RECORD_TYPES if n not in defs]
    extra = [n for n in defs if n not in L.RECORD_TYPES]
    if missing or extra:
        raise RuntimeError(f"def set mismatch missing={missing} extra={extra}")
    return {name: defs[name] for name in L.RECORD_TYPES}


def build_pack() -> dict[str, Any]:
    defs = build_defs()
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ast-integrate.local/command-center/wfa/schema/wfa-schema-pack.json",
        "$comment": L.SENTINEL,
        "title": "WFA schema pack: 18 record types",
        "description": (
            "JSON Schema 2020-12 bundle for workflow-archaeology artifacts. "
            "Each $def is closed (additionalProperties:false), carries required "
            "fields, and bundles one valid plus one invalid example. "
            + L.SENTINEL
        ),
        "$defs": defs,
        "oneOf": [{"$ref": f"#/$defs/{name}"} for name in L.RECORD_TYPES],
    }


def main() -> int:
    pack = build_pack()
    L.PACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(pack, indent=2, ensure_ascii=True) + "\n"
    if L.SENTINEL not in text:
        print("FAILED:WFA-0001 emit sentinel absent")
        return 1
    L.PACK_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {L.PACK_REL} bytes={len(text.encode('utf-8'))}")
    print(L.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
