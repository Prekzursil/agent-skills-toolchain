"""JSON Schema (Draft-07) for a proof-of-impossibility record.

A not-found result is not impossibility. The schema refuses an empty
exhausted_sources list (catalog both-states control) and refuses a
record with the falsifier field removed (catalog evidence requirement).
"""
from __future__ import annotations

RECORD_KIND = "proof-of-impossibility"

# Reconstructed from catalog fragments. The canonical 16-name list lives
# in _USER-PROMPTS.md:10683, which is absent on this worktree.
SOURCE_CLASS_VOCABULARY = (
    "official-docs",
    "source-code",
    "issue-trackers",
    "changelogs-release-notes",
    "standards",
    "papers",
    "engineering-blogs",
    "forums",
    "archival",
    "niche",
    "multilingual",
    "anecdotal",
    "video-talk-transcripts",
    "public-tor",
    "mailing-lists",
    "q-and-a",
)

SHERMAN_KENT_BANDS = (
    "almost-certain",
    "likely",
    "roughly-even",
    "unlikely",
    "remote",
)

ACCESS_BARRIER_KINDS = (
    "file-absent",
    "path-not-mounted",
    "recovered-placeholder-only",
    "owner-gated",
    "paywalled",
    "auth-required",
    "legal-policy",
    "tool-unavailable",
)

QUERY_ITEM = {
    "type": "object",
    "additionalProperties": True,
    "required": ["query", "result_count", "backend"],
    "properties": {
        "query": {"type": "string", "minLength": 1},
        "result_count": {"type": "integer", "minimum": 0},
        "backend": {"type": "string", "minLength": 1},
        "hit_summary": {"type": "string"},
    },
}

EXHAUSTED_SOURCE_ITEM = {
    "type": "object",
    "additionalProperties": True,
    "required": ["source_class", "queries", "status"],
    "properties": {
        "source_class": {"type": "string", "minLength": 3},
        "status": {"type": "string", "enum": ["exhausted", "blocked-unattempted"]},
        "queries": {
            "type": "array",
            "minItems": 1,
            "items": QUERY_ITEM,
        },
        "notes": {"type": "string"},
    },
}

LINEAGE = {
    "type": "object",
    "additionalProperties": True,
    "required": [
        "resolved_url",
        "fetch_timestamp",
        "sha256_of_fetched_bytes",
    ],
    "properties": {
        "resolved_url": {"type": "string", "minLength": 8},
        "fetch_timestamp": {"type": "string", "minLength": 20},
        "sha256_of_fetched_bytes": {
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "bytes": {"type": "integer", "minimum": 0},
        "http_status": {"type": ["integer", "null"]},
        "note": {"type": "string"},
    },
}

CLAIM = {
    "type": "object",
    "additionalProperties": True,
    "required": [
        "id",
        "text",
        "verdict",
        "sherman_kent_band",
        "lineage",
        "independent_verification_path",
        "signals",
    ],
    "properties": {
        "id": {"type": "string", "minLength": 2},
        "text": {"type": "string", "minLength": 16},
        "verdict": {
            "type": "string",
            "enum": [
                "CONFIRMED",
                "REFUTED",
                "PARTIAL",
                "NOT-CHECKED",
                "BLOCKED",
            ],
        },
        "sherman_kent_band": {"type": "string", "enum": list(SHERMAN_KENT_BANDS)},
        "lineage": {
            "type": "array",
            "minItems": 1,
            "items": LINEAGE,
        },
        "independent_verification_path": {"type": "string", "minLength": 8},
        "signals": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "required": ["id", "mechanism", "observation"],
                "properties": {
                    "id": {"type": "string"},
                    "mechanism": {"type": "string", "minLength": 4},
                    "observation": {"type": "string", "minLength": 4},
                },
            },
        },
    },
}

RECORD_SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": (
        "command-center/research/evidence-quality/"
        "RES-0149-proof-of-impossibility-record-schema.json#/record_schema"
    ),
    "title": "Proof-of-impossibility record",
    "description": (
        "Closes a research question as unanswerable. Distinguishes "
        "'cannot be obtained' from 'not found' by requiring a non-empty "
        "exhausted_sources list, exact queries with counts, an access "
        "barrier, a retry_after expiry, and a single-observation falsifier."
    ),
    "type": "object",
    "additionalProperties": True,
    "required": [
        "record_kind",
        "question",
        "program_unit_id",
        "exhausted_sources",
        "access_barrier",
        "retry_after",
        "falsifier",
        "claims",
    ],
    "properties": {
        "record_kind": {"type": "string", "const": RECORD_KIND},
        "question": {"type": "string", "minLength": 24},
        "program_unit_id": {
            "type": "string",
            "pattern": "^[A-Z]{2,5}-[0-9]{4}$",
        },
        "exhausted_sources": {
            "type": "array",
            "minItems": 1,
            "description": (
                "Empty list is a not-found masquerading as impossible "
                "and MUST be rejected."
            ),
            "items": EXHAUSTED_SOURCE_ITEM,
        },
        "access_barrier": {
            "type": "object",
            "additionalProperties": True,
            "required": ["kind", "description"],
            "properties": {
                "kind": {"type": "string", "minLength": 4},
                "description": {"type": "string", "minLength": 16},
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "owner_gate": {"type": "string"},
            },
        },
        "retry_after": {
            "type": "string",
            "minLength": 20,
            "description": "ISO-8601 UTC instant after which the record must be retried.",
        },
        "retry_triggers": {
            "type": "array",
            "items": {"type": "string"},
        },
        "falsifier": {
            "type": "object",
            "additionalProperties": True,
            "required": ["single_observation", "how_it_overturns"],
            "properties": {
                "single_observation": {"type": "string", "minLength": 16},
                "how_it_overturns": {"type": "string", "minLength": 16},
            },
        },
        "claims": {
            "type": "array",
            "minItems": 1,
            "items": CLAIM,
        },
        "closed_as": {
            "type": "string",
            "enum": ["unanswerable", "cannot-be-obtained"],
        },
        "notes": {"type": "string"},
    },
}


def record_schema() -> dict:
    return RECORD_SCHEMA
