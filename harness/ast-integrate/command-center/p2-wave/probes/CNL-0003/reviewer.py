#!/usr/bin/env python3
"""Independent recount of the branch table (does not import AXIS_MAPS).

Reads charter_block.schema.json enums and re-derives cartesian size and a
counterexample the losing silent-default compiler would accept.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = HERE / "charter_block.schema.json"


def recount() -> dict:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    props = schema["properties"]
    risk = list(props["risk_tier"]["enum"])
    output = list(props["desired_output"]["enum"])
    intent = list(props["consensus_intent"]["enum"])
    cartesian = len(risk) * len(output) * len(intent)
    counterexample = {
        "objective": "Reviewer counterexample: prose stuffed into an enum field.",
        "risk_tier": "urgent-ish",
        "desired_output": "decision",
        "success_criteria": "Must COMPILE_REJECT, never silent-default.",
        "consensus_intent": "majority",
    }
    return {
        "reviewer_id": "CNL-0003-schema-file-cartesian-recount",
        "independent": True,
        "mechanism": "jsonschema-file enum arrays, not compiler.py dict keys",
        "risk_n": len(risk),
        "output_n": len(output),
        "intent_n": len(intent),
        "cartesian": cartesian,
        "prose_fields_in_schema": ["objective", "success_criteria"],
        "enum_fields_in_schema": ["risk_tier", "desired_output", "consensus_intent"],
        "counterexample": counterexample,
        "counterexample_claim": (
            "If the compiler silent-defaulted, risk_tier='urgent-ish' would "
            "still yield a protocol_id. The live compiler must COMPILE_REJECT."
        ),
    }
