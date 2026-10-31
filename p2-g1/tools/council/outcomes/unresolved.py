"""Unresolved leftover capture with settling_experiment schema (IMP-0341)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SPEC_ANCHOR = "command-center/schema/unresolved-leftover.schema.json"


def load_path(path: Path) -> list[dict[str, Any]]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if isinstance(doc, dict):
        for key in ("entries", "leftovers", "unresolved", "items"):
            rows = doc.get(key)
            if isinstance(rows, list):
                return [x for x in rows if isinstance(x, dict)]
        if "id" in doc or "question" in doc:
            return [doc]
    return []


def schema_errors_entry(entry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if "settling_experiment" not in entry:
        errors.append("missing settling_experiment")
        return errors
    exp = entry.get("settling_experiment")
    if exp == "" or exp is None:
        errors.append("empty settling_experiment")
        return errors
    if isinstance(exp, dict):
        if not exp:
            errors.append("empty settling_experiment object")
        elif not exp.get("command"):
            errors.append("command missing from settling_experiment")
        return errors
    # string (including vague) is schema-present
    return errors


def audit_entry(entry: dict[str, Any]) -> dict[str, Any]:
    errs = schema_errors_entry(entry)
    vague = isinstance(entry.get("settling_experiment"), str)
    return {
        "id": entry.get("id"),
        "ok": not errs and not vague,
        "errors": errs,
        "vague": vague,
    }


def schema_errors(entries: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for e in entries:
        out.extend(schema_errors_entry(e))
    return out


def capture(council_artifact: dict[str, Any], source: str = "council") -> list[dict[str, Any]]:
    leftovers = (
        council_artifact.get("unresolved")
        or council_artifact.get("leftovers")
        or council_artifact.get("open_questions")
        or []
    )
    outcomes = council_artifact.get("outcomes") or {}
    if isinstance(outcomes, dict):
        leftovers = leftovers or outcomes.get("unresolved_questions") or outcomes.get("leftovers") or []
    if not leftovers and isinstance(council_artifact.get("questions"), list):
        leftovers = council_artifact["questions"]
    out: list[dict[str, Any]] = []
    for i, row in enumerate(leftovers):
        if isinstance(row, str):
            out.append({"id": f"CQ-STRING-{i}", "question": row, "source": source})
            continue
        if not isinstance(row, dict):
            continue
        entry = dict(row)
        entry.setdefault("source", source)
        out.append(entry)
    if not out:
        out.append(
            {
                "id": "CQ-MISSING-EXPERIMENT",
                "question": str(council_artifact.get("question") or "unresolved leftover"),
                "source": source,
            }
        )
    return out
