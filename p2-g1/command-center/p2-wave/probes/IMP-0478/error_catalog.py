#!/usr/bin/env python3
"""IMP-0478 user-facing error catalog (rebuilt 2026-10-25, shard16-wave2 resume).

The message ids and next_command forms are the receipt's own coverage_table
(command-center/receipts/IMP-0478.json) taken as SSOT; WHAT/WHY texts carry the
human-facing content. Any class outside closed_classes is reported UNMAPPED,
never force-fitted (receipt negative control "later-class-unmapped").
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RECEIPT = REPO / "command-center" / "receipts" / "IMP-0478.json"

WHY = {
    "severed-stream": "The stream died without a terminal receipt, so the last visible state is not a state the program promised.",
    "adapter-exit-n": "A vendor adapter exited non-zero and the code N is the only fact that survived.",
    "win-arg-limit": "Windows command-line length caps truncated the argv, so the child saw a different job than the one intended.",
    "timeout": "The step exceeded its budget and was killed; a timeout is a measured fact, not a verdict.",
    "schema-invalid": "The artifact does not parse against its declared schema, so consumers cannot trust any field inside it.",
    "partial-artifact": "Some work units landed and some did not; reporting the union as one state would overclaim.",
    "degraded": "The step completed in a reduced mode; the result is usable but weaker than the contract.",
    "blocked": "A gate refused the step; the refusal is the outcome and carries its reason.",
}


def _coverage_rows():
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    return doc.get("coverage_table") or []


def closed_classes():
    return [row["taxonomy_class"] for row in _coverage_rows()]


def lookup(taxonomy_class: str):
    for row in _coverage_rows():
        if row.get("taxonomy_class") == taxonomy_class:
            return {
                "taxonomy_class": taxonomy_class,
                "message_id": row.get("message_id"),
                "mapped": True,
                "what": WHY.get(taxonomy_class, "Condition reported by the failing step."),
                "why": WHY.get(taxonomy_class, "Unmapped condition."),
                "next_command": row.get("next_command"),
            }
    return {
        "taxonomy_class": taxonomy_class,
        "message_id": None,
        "mapped": False,
        "what": "This taxonomy class has no user-facing message.",
        "why": "Unknown or later-added class; reported unmapped rather than force-fitted.",
        "next_command": None,
    }
