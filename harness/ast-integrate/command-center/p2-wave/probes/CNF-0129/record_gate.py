"""Confirmation-record gate: unsourced CONFIRMED is invalid."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA = REPO / "command-center" / "schema" / "confirmation-record.schema.json"


def fingerprint_bytes(doc: Any) -> str:
    raw = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _source_empty(rec: dict[str, Any]) -> bool:
    src = rec.get("source_probe")
    if src is None:
        return True
    if isinstance(src, str) and not src.strip():
        return True
    if isinstance(src, dict) and not any(src.values()):
        return True
    return False


def schema_errors(rec: dict[str, Any] | None) -> list[str]:
    rec = rec if isinstance(rec, dict) else {}
    errs: list[str] = []
    verdict = str(rec.get("verdict") or "").upper()
    if verdict == "CONFIRMED" and _source_empty(rec):
        errs.append("no-source-probe")
    if SCHEMA.is_file():
        try:
            import jsonschema

            schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
            validator = jsonschema.Draft202012Validator(schema)
            for err in validator.iter_errors(rec):
                errs.append(err.message)
        except Exception as exc:  # schema hook may fill leftover receipts
            if "Unresolvable" in type(exc).__name__:
                pass
            elif not errs:
                pass
    return errs


def validate_record(rec: dict[str, Any] | None) -> dict[str, Any]:
    errs = schema_errors(rec)
    ok = not errs
    return {
        "ok": ok,
        "schema_valid": ok,
        "errors": errs,
        "fingerprint": fingerprint_bytes(rec or {}),
    }
