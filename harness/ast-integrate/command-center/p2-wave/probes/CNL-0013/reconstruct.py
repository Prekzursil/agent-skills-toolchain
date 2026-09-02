"""Reconstruct dials from an explanation record's embedded rule table.

Does not call selector.select(). A reviewer who has the explanation (and this
module) can recompute why each dial was chosen.
"""
from __future__ import annotations

from selector import apply_tables, classify


def reconstruct(record: dict) -> dict:
    if not isinstance(record, dict):
        raise TypeError("explanation record must be an object")
    inputs = record.get("inputs") or {}
    desc = str(inputs.get("task_description") or "")
    tier = str(inputs.get("risk_tier") or "")
    table = record.get("rule_table")
    if not isinstance(table, dict):
        raise ValueError("explanation is missing rule_table; cannot reconstruct")
    task_class, class_rule_id = classify(desc, table.get("task_class_rules") or [])
    chosen, meta = apply_tables(tier, task_class, table=table)
    return {
        "task_class": task_class,
        "task_class_rule_id": class_rule_id,
        "dials": chosen,
        "last_setter": meta["last_setter"],
    }


def recorded_dials(record: dict) -> dict:
    out = {}
    for row in record.get("dials") or []:
        if isinstance(row, dict) and row.get("dial"):
            out[str(row["dial"])] = row.get("value")
    return out


def matches(record: dict) -> tuple[bool, str]:
    got = reconstruct(record)
    want = recorded_dials(record)
    for name, value in got["dials"].items():
        if want.get(name) != value:
            return False, f"{name}: reconstructed={value!r} recorded={want.get(name)!r}"
    if got["task_class"] != record.get("task_class"):
        return (
            False,
            f"task_class reconstructed={got['task_class']!r} recorded={record.get('task_class')!r}",
        )
    return True, "ok"
