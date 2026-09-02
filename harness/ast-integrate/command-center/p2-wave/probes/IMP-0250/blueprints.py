#!/usr/bin/env python3
"""Four data blueprints 1-4 as contract-gated registrations (IMP-0230 elements)."""
from __future__ import annotations

from typing import Any

import data_quality as dq
import dataset_docs as dd
import extract_normalize as en
import knowledge_base as kb
from contract import omission_matrix, register

EXTRACT = {
    "name": "extraction-normalization",
    "workflow": {
        "id": "wf.data.extraction-normalization",
        "kind": "workflow_blueprint",
        "discovery_only": False,
        "stages": [
            {
                "id": "ingest",
                "kind": "read-bytes",
                "inputs": ["records.bin"],
                "outputs": ["raw"],
            },
            {
                "id": "sanitize-then-split",
                "kind": "parse-delimited",
                "inputs": ["raw"],
                "outputs": ["rows"],
                "invariant": "strip C0/C1 except designated delimiter BEFORE split",
            },
            {
                "id": "emit-normalized",
                "kind": "write-table",
                "inputs": ["rows"],
                "outputs": ["table.norm"],
            },
        ],
        "stopping": {"max_stages": 3, "on_error": "halt"},
    },
    "example": {
        "id": "ex.extraction-normalization.planted-us",
        "input": {"fixture": "planted_fixture", "planted": "0x1F inside title"},
        "expect": {"widths": [3, 3, 3], "title": "widgetdeluxe"},
    },
    "preset": {
        "id": "preset.extraction-normalization.comma-us-strip",
        "bindings": {
            "field_delimiter": ",",
            "record_delimiter": "\\n",
            "control_policy": "strip-before-split",
            "naive_extra_delims": ["TAB", "VT", "FF", "RS", "US", "NEL"],
        },
    },
    "stopping_rules": {
        "max_stages": 3,
        "on_error": "halt",
        "documented": (
            "Halt if any record's post-sanitize column count differs from the "
            "header width; do not guess extra columns back into fields."
        ),
    },
    "smoke_test": en.smoke,
    "capability_vector": [
        "parse.delimited",
        "sanitize.control-bytes-before-split",
        "normalize.emit",
    ],
}

QUALITY = {
    "name": "data-quality-audit",
    "workflow": {
        "id": "wf.data.data-quality-audit",
        "kind": "workflow_blueprint",
        "discovery_only": False,
        "stages": [
            {
                "id": "parse-fixed",
                "kind": "parse-delimited",
                "inputs": ["records.bin"],
                "outputs": ["rows"],
            },
            {
                "id": "audit-width",
                "kind": "quality-audit",
                "inputs": ["rows"],
                "outputs": ["audit.json"],
            },
        ],
        "stopping": {"max_stages": 2, "on_error": "halt"},
    },
    "example": {
        "id": "ex.data-quality-audit.naive-drift",
        "input": {"fixture": "planted_fixture"},
        "expect": {"fixed_ok": True, "naive_drift": True},
    },
    "preset": {
        "id": "preset.data-quality-audit.width-3",
        "bindings": {"expected_width": 3, "required_columns": [0, 1, 2]},
    },
    "stopping_rules": {
        "max_stages": 2,
        "on_error": "halt",
        "documented": "Column-count drift is a hard halt, not a warning.",
    },
    "smoke_test": dq.smoke,
    "capability_vector": ["quality.column-drift", "quality.empty-required"],
}

DOCS = {
    "name": "dataset-documentation",
    "workflow": {
        "id": "wf.data.dataset-documentation",
        "kind": "workflow_blueprint",
        "discovery_only": False,
        "stages": [
            {
                "id": "parse",
                "kind": "parse-delimited",
                "inputs": ["records.bin"],
                "outputs": ["rows"],
            },
            {
                "id": "card",
                "kind": "emit-dataset-card",
                "inputs": ["rows"],
                "outputs": ["card.json"],
            },
        ],
        "stopping": {"max_stages": 2, "on_error": "halt"},
    },
    "example": {
        "id": "ex.dataset-documentation.stable-schema",
        "input": {"fixture": "planted_fixture"},
        "expect": {"columns": ["sku", "title", "qty"]},
    },
    "preset": {
        "id": "preset.dataset-documentation.card-v1",
        "bindings": {"sample_rows": 5, "halt_on_unstable_schema": True},
    },
    "stopping_rules": {
        "max_stages": 2,
        "on_error": "halt",
        "documented": "Unstable column count refuses the card (halt), no guessed schema.",
    },
    "smoke_test": dd.smoke,
    "capability_vector": ["docs.dataset-card", "docs.schema-stability"],
}

KB = {
    "name": "knowledge-base-construction",
    "workflow": {
        "id": "wf.data.knowledge-base-construction",
        "kind": "workflow_blueprint",
        "discovery_only": False,
        "stages": [
            {
                "id": "parse",
                "kind": "parse-delimited",
                "inputs": ["records.bin"],
                "outputs": ["rows"],
            },
            {
                "id": "index",
                "kind": "inverted-index",
                "inputs": ["rows"],
                "outputs": ["kb.json"],
            },
        ],
        "stopping": {"max_stages": 2, "on_error": "halt"},
    },
    "example": {
        "id": "ex.knowledge-base-construction.joined-title",
        "input": {"fixture": "planted_fixture", "query": "widgetdeluxe"},
        "expect": {"hits": [1]},
    },
    "preset": {
        "id": "preset.knowledge-base-construction.cell-tokens",
        "bindings": {"token": "cell-exact", "split_on_controls": False},
    },
    "stopping_rules": {
        "max_stages": 2,
        "on_error": "halt",
        "documented": "Stop after one index pass; do not re-tokenize on control bytes.",
    },
    "smoke_test": kb.smoke,
    "capability_vector": ["kb.inverted-index", "kb.lookup"],
}

ALL = (EXTRACT, QUALITY, DOCS, KB)


def register_all() -> list[dict[str, Any]]:
    return [register(bp) for bp in ALL]


def contract_omission_controls() -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for bp in ALL:
        matrix = omission_matrix(bp)
        ids = [r["rejection"] for r in matrix]
        rows[bp["name"]] = {
            "distinct": len(set(ids)) == 6,
            "all_rejected": all(r["ok"] is False for r in matrix),
            "rejections": ids,
        }
    return rows
