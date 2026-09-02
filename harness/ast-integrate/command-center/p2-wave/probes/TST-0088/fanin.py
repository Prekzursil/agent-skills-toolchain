#!/usr/bin/env python3
"""Fan-in classifier for a streamed unit artifact.

Condition 5 is the named reject for a file that exists, parses, and looks
plausible but does not carry its completion sentinel (spec 11313). Distinct
from condition 2 (artifact wholly absent; TST-0004).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
VICTIM_SCHEMA = json.loads(
    (HERE / "victim.schema.json").read_text(encoding="utf-8")
)
TERMINAL = frozenset(
    {"SUCCESS", "PARTIAL", "BLOCKED", "FAILED", "TIMEOUT", "SEVERED"}
)
CONDITIONS = (
    (1, "process/task reached a valid terminal state"),
    (2, "expected artifact exists"),
    (3, "artifact is non-empty and exceeds a meaningful minimum size"),
    (4, "artifact parses against its schema"),
    (5, "required sentinel is present"),
)


def _load(path: Path) -> tuple[dict[str, Any] | None, str | None, int]:
    if not path.is_file():
        return None, "absent", 0
    raw = path.read_bytes()
    if not raw:
        return None, "empty", 0
    try:
        text = raw.decode("utf-8")
        doc = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"unparseable:{type(exc).__name__}", len(raw)
    if not isinstance(doc, dict):
        return None, "not-object", len(raw)
    return doc, None, len(raw)


def classify(
    path: Path,
    *,
    expected_sentinel: str,
    expected_unit_id: str,
    min_bytes: int = 64,
    schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify one on-disk artifact. Never SUCCESS when condition 5 fails."""
    schema = schema or VICTIM_SCHEMA
    doc, parse_err, nbytes = _load(path)
    exists = path.is_file()
    rows: list[dict[str, Any]] = []
    first: int | None = None

    def rec(n: int, name: str, ok: bool, basis: str) -> None:
        nonlocal first
        if not ok and first is None:
            first = n
        rows.append(
            {
                "n": n,
                "name": name,
                "outcome": "SATISFIED" if ok else "UNSATISFIED",
                "basis": basis,
            }
        )

    state_ok = isinstance(doc, dict) and str(doc.get("state") or "") in TERMINAL
    rec(
        1,
        CONDITIONS[0][1],
        state_ok,
        (
            f"artifact.state={doc.get('state')!r} is a valid terminal"
            if state_ok
            else f"no valid terminal state on disk (parse_err={parse_err})"
        ),
    )
    rec(
        2,
        CONDITIONS[1][1],
        exists,
        f"path exists={exists} bytes={nbytes}",
    )
    rec(
        3,
        CONDITIONS[2][1],
        exists and nbytes >= min_bytes,
        f"bytes={nbytes} min_bytes={min_bytes}",
    )
    schema_ok = False
    schema_basis = parse_err or "no object"
    if isinstance(doc, dict):
        try:
            jsonschema.Draft7Validator(schema).validate(doc)
            schema_ok = True
            schema_basis = "json parses and satisfies victim schema (sentinel not required by schema)"
        except jsonschema.ValidationError as exc:
            schema_basis = f"schema:{exc.message}"
    rec(4, CONDITIONS[3][1], schema_ok, schema_basis)

    sentinel_val = None if not isinstance(doc, dict) else doc.get("sentinel")
    sentinel_ok = isinstance(sentinel_val, str) and sentinel_val == expected_sentinel
    rec(
        5,
        CONDITIONS[4][1],
        sentinel_ok,
        (
            f"typed sentinel field {sentinel_val!r} matches {expected_sentinel!r}"
            if sentinel_ok
            else (
                "file exists but does not carry the completion sentinel in the typed "
                f"sentinel field (observed={sentinel_val!r}, expected={expected_sentinel!r}) "
                "- partial artifact without sentinel is INCOMPLETE (spec 11313, condition 5)"
            )
        ),
    )

    # Named classes: wholly absent is condition 2 (TST-0004), not "no terminal
    # state". A present-but-sentinel-less file is condition 5 (TST-0088 / 11313).
    if not exists:
        first = 2
    elif exists and nbytes < min_bytes:
        first = 3
    elif not schema_ok:
        first = 4
    elif not sentinel_ok:
        first = 5

    plausible = (
        isinstance(doc, dict)
        and doc.get("unit_id") == expected_unit_id
        and str(doc.get("state") or "") == "SUCCESS"
        and schema_ok
    )
    verdict = "SUCCESS" if first is None else "FAILED"
    return {
        "verdict": verdict,
        "condition_id": first,
        "condition_name": (
            dict(CONDITIONS).get(first, "none") if first is not None else None
        ),
        "never_success": verdict != "SUCCESS",
        "exists": exists,
        "bytes": nbytes,
        "parses": isinstance(doc, dict) and parse_err is None,
        "looks_plausible": bool(plausible),
        "sentinel_present": bool(sentinel_ok),
        "observed_sentinel": sentinel_val,
        "expected_sentinel": expected_sentinel,
        "expected_unit_id": expected_unit_id,
        "parse_err": parse_err,
        "conditions": rows,
        "path": str(path),
    }
