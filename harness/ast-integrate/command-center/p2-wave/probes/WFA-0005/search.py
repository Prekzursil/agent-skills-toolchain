"""Signal B: decision-rule search over does/mechanisms/notes only.

Never reads candidates[].classification, so a zero histogram cannot certify
that a value is dead vocabulary.
"""
from __future__ import annotations

import json
from typing import Any

from vocabulary import RULES, UNUSED_VALUES


TEXT_FIELDS = ("does", "mechanisms", "notes")


def field_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(field_text(x) for x in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def blob(rec: dict[str, Any]) -> str:
    parts = [field_text(rec.get(k)) for k in TEXT_FIELDS]
    return "\n".join(p for p in parts if p).lower()


def matches_rule(rec: dict[str, Any], value: str) -> bool:
    rule = RULES[value]
    text = blob(rec)
    if not text.strip():
        return False
    return all(tok.lower() in text for tok in rule["all_tokens"])


def matching_tokens(rec: dict[str, Any], value: str) -> list[str]:
    text = blob(rec)
    return [tok for tok in RULES[value]["all_tokens"] if tok.lower() in text]


def search_records(
    records: list[dict[str, Any]], values: tuple[str, ...] = UNUSED_VALUES
) -> dict[str, list[dict[str, Any]]]:
    hits: dict[str, list[dict[str, Any]]] = {v: [] for v in values}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        for value in values:
            if matches_rule(rec, value):
                hits[value].append(
                    {
                        "id": rec.get("id"),
                        "assigned_classification": rec.get("classification"),
                        "matched_tokens": matching_tokens(rec, value),
                        "fields_used": list(TEXT_FIELDS),
                    }
                )
    return hits


def fired_values(hits: dict[str, list[dict[str, Any]]]) -> list[str]:
    return [v for v, rows in hits.items() if rows]
