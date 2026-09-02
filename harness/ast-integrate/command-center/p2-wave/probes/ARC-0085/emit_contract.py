#!/usr/bin/env python3
"""Emit command-center/phase4/contracts/ARC-0085.json (draft 2020-12 claim-record schema)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/phase4/contracts/ARC-0085.json"

CLAIM_ID = {
    "type": "string",
    "minLength": 6,
    "maxLength": 96,
    "pattern": "^[A-Z][A-Z0-9_-]{5,95}$",
    "description": "Stable claim id. Not a slug of the latest authoring agent.",
}

MECHANISM = {
    "type": "string",
    "minLength": 24,
    "maxLength": 2000,
    "description": (
        "Canonical mechanism statement: the proposition that would be true or false "
        "in the world, independent of who repeated it."
    ),
}

EDGE_LIST = {
    "type": "array",
    "default": [],
    "items": CLAIM_ID,
    "uniqueItems": True,
    "description": "Zero or more claim ids. Unknown ids are a registry-level error.",
}

LINEAGE_PROBE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tool", "engine", "shell", "field"],
    "properties": {
        "tool": {"type": "string", "minLength": 1, "maxLength": 64},
        "engine": {"type": "string", "minLength": 1, "maxLength": 128},
        "shell": {"type": "string", "minLength": 1, "maxLength": 64},
        "field": {"type": "string", "minLength": 1, "maxLength": 128},
    },
}

LINEAGE_ENTRY = {
    "type": "object",
    "additionalProperties": False,
    "required": ["author", "path", "line"],
    "properties": {
        "author": {"type": "string", "minLength": 2, "maxLength": 128},
        "path": {"type": "string", "minLength": 8, "maxLength": 512},
        "line": {"type": "integer", "minimum": 1},
        "snippet": {"type": "string", "minLength": 8, "maxLength": 500},
        "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
        "url": {"type": "string", "minLength": 8, "maxLength": 1024},
        "fetched_at": {"type": "string", "minLength": 10, "maxLength": 40},
        "probe": LINEAGE_PROBE,
    },
}

SETTLING = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "command"],
    "properties": {
        "id": {"type": "string", "minLength": 2, "maxLength": 96},
        "command": {"type": "string", "minLength": 8, "maxLength": 1024},
        "independence_class": {"type": "string", "minLength": 8, "maxLength": 256},
    },
    "description": "The EXACT settling probe. An UNVERIFIED claim without this object is invalid.",
}

IMPACT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["class", "severity", "blocks_downstream"],
    "properties": {
        "class": {
            "type": "string",
            "enum": [
                "none",
                "docs",
                "test",
                "implementation",
                "architecture",
                "operator-decision",
            ],
        },
        "severity": {
            "type": "string",
            "enum": ["none", "P0", "P1", "P2", "P3"],
        },
        "blocks_downstream": {"type": "boolean"},
    },
}

BANDS = ["almost-certain", "likely", "roughly-even", "unlikely", "remote"]
STATUSES = [
    "UNVERIFIED",
    "CONFIRMED",
    "REFUTED",
    "PARTIAL",
    "NOT-CHECKED",
    "BLOCKED",
]

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "command-center/phase4/contracts/ARC-0085.json",
    "title": "ARC-0085 canonical claim record",
    "description": (
        "Phase 4 formal contract for the Phase 1 canonical claim record: stable claim id, "
        "canonical mechanism, duplicate-of / support / contradiction edges, source lineage, "
        "Sherman-Kent confidence band, verification status, implementation impact, and the "
        "EXACT settling probe. Ranking is by independent evidence and decision impact, never "
        "by how many agents repeated the same mechanism. SUCCESS:ARC-0085"
    ),
    "$comment": (
        "Edge semantics: duplicate_of means the same canonical_mechanism (collapse, do not vote). "
        "supports means independent evidence for a different mechanism. contradicts means the "
        "two propositions cannot both be CONFIRMED. A duplicate-of cycle is invalid. An "
        "UNVERIFIED record with no settling_probe is invalid. CLAIM-REGISTRY.json is the "
        "intended instance store; when absent, live phase-3 claim-bearing artifacts are the "
        "encoding source. SUCCESS:ARC-0085"
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "claim_id",
        "canonical_mechanism",
        "duplicate_of",
        "supports",
        "contradicts",
        "source_lineage",
        "confidence_band",
        "verification_status",
        "implementation_impact",
        "settling_probe",
    ],
    "properties": {
        "claim_id": CLAIM_ID,
        "canonical_mechanism": MECHANISM,
        "duplicate_of": {
            **EDGE_LIST,
            "description": (
                "Ids this record aliases. Empty on the canonical survivor after collapse. "
                "Same mechanism + different authors is a duplicate, not extra rank weight."
            ),
        },
        "supports": {
            **EDGE_LIST,
            "description": "Ids whose truth would raise confidence in this mechanism.",
        },
        "contradicts": {
            **EDGE_LIST,
            "description": (
                "Ids whose CONFIRMED status cannot coexist with this record CONFIRMED. "
                "Not a duplicate: different mechanisms that cannot both be true."
            ),
        },
        "source_lineage": {
            "type": "array",
            "minItems": 1,
            "items": LINEAGE_ENTRY,
            "description": (
                "Every authoring or confirming observation. Two lineage rows with the same "
                "independence key (tool, engine, shell, field) are one signal, even if the "
                "authors differ."
            ),
        },
        "confidence_band": {
            "type": "string",
            "enum": BANDS,
            "description": "Sherman-Kent vocabulary. Closed. No free-text hedges.",
        },
        "verification_status": {
            "type": "string",
            "enum": STATUSES,
            "description": (
                "Closed verification vocabulary. UNVERIFIED requires a nonempty settling_probe."
            ),
        },
        "implementation_impact": IMPACT,
        "settling_probe": SETTLING,
    },
    "if": {
        "properties": {"verification_status": {"const": "UNVERIFIED"}},
        "required": ["verification_status"],
    },
    "then": {
        "required": ["settling_probe"],
        "properties": {
            "settling_probe": SETTLING,
        },
    },
    "$defs": {
        "claimId": CLAIM_ID,
        "settlingProbe": SETTLING,
        "sourceLineageEntry": LINEAGE_ENTRY,
        "implementationImpact": IMPACT,
        "confidenceBand": {"type": "string", "enum": BANDS},
        "verificationStatus": {"type": "string", "enum": STATUSES},
        "claimRegistry": {
            "type": "object",
            "additionalProperties": False,
            "required": ["schema_version", "unit_id", "claims"],
            "properties": {
                "schema_version": {"const": 1},
                "unit_id": {"const": "ARC-0085"},
                "claims": {
                    "type": "array",
                    "minItems": 10,
                    "items": {"$ref": "#"},
                },
            },
        },
    },
    "x-ranking": {
        "rule": (
            "rank_score = independent_evidence_score * decision_impact_score. "
            "independent_evidence_score is the count of DISTINCT source_lineage probe keys "
            "(tool, engine, shell, field). Missing probe keys fall back to (path, line) only, "
            "still not to author identity. decision_impact_score is severity weight "
            "(P0=8,P1=4,P2=2,P3=1,none=0) multiplied by class weight "
            "(architecture=2, operator-decision=2, implementation=1, test=1, docs=1, none=0)."
        ),
        "forbidden_inputs": [
            "author_count",
            "agent_repeat_count",
            "lineage_row_count_without_independence_key",
            "how_many_agents_repeated_the_mechanism",
        ],
        "collapse": (
            "Records with the same NFKC/casefold/whitespace-collapsed canonical_mechanism "
            "collapse to one canonical claim_id (lexicographically smallest) carrying the "
            "union of source_lineage rows. Aliases keep duplicate_of=[canonical]."
        ),
    },
    "x-unit": {
        "id": "ARC-0085",
        "sentinel": "SUCCESS:ARC-0085",
        "output_path": "command-center/phase4/contracts/ARC-0085.json",
        "tests_required": [
            "Repetition-immunity: same mechanism, different authors -> one canonical claim, two lineage entries",
            "Settling-probe: UNVERIFIED with no settling_probe fails validation",
        ],
    },
    "x-reviewers": {
        "independent_contract_reviewer": (
            "command-center/p2-wave/probes/ARC-0085/probe1_repetition_immunity.py"
        ),
        "consumer_call_site": "command-center/p2-wave/probes/ARC-0085/validator.py",
    },
    "unit_id": "ARC-0085",
    "state": "SUCCESS",
    "sentinel": "SUCCESS:ARC-0085",
}


def main() -> int:
    jsonschema.Draft202012Validator.check_schema(SCHEMA)
    sys.path.insert(0, str(HERE))
    import claims as C  # noqa: E402

    records, source = C.load_encoded()
    C.write_fixture(records, source)
    doc = dict(SCHEMA)
    doc["x-encoding"] = {
        "source": source,
        "encoded": len(records),
        "claim_ids": [r["claim_id"] for r in records],
        "duplicate_pair": [C.DUP_SOURCE, C.DUP_VERIFIER],
        "contradiction_pair": [C.CONTRA_CLOSED, C.CONTRA_OPEN],
        "note": (
            "Live CLAIM-REGISTRY.json mapped into this schema (raw CC-* rows "
            "are not claim-record instances). phase3 DESIGN/REFUTATION absent."
        ),
    }
    doc["examples"] = [records[0]]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    validator = jsonschema.Draft202012Validator(SCHEMA)
    garbage = (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    )
    for probe in garbage:
        errs = list(validator.iter_errors(probe))
        if not errs:
            print(f"FAILED:ARC-0085 schema accepts garbage {probe!r:.80}")
            return 1
    example_errs = list(validator.iter_errors(records[0]))
    if example_errs:
        print(f"FAILED:ARC-0085 live example invalid: {example_errs[0]}")
        return 1
    print(
        f"wrote {OUT.relative_to(REPO).as_posix()} encoded={len(records)} "
        f"source={source} SUCCESS:ARC-0085"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
