"""Validate confirmation records: local field schema plus same-probe-rerun.

The catalog path command-center/schema/confirmation-record.schema.json is a
generated $ref shim to https://ast-integrate.invalid/... . Draft7Validator
follows that URL onto the network (RefResolutionError) and, if resolved, is
receipt_core/generic_report — the wrong class for nested per-claim records.
CNF-0129 owns that field set; this unit validates it locally. G-1 does not
require the remote hop.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "confirmation-record.local.schema.json"

TERMINAL_VERDICTS = frozenset({"CONFIRMED", "REFUTED"})


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _probe_token(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("fingerprint", "sha256", "id"):
            token = value.get(key)
            if isinstance(token, str) and token.strip():
                return token.strip()
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return ""


def schema_errors(record: dict[str, Any]) -> list[str]:
    validator = jsonschema.Draft7Validator(load_schema())
    errs = []
    for e in validator.iter_errors(record):
        path = ".".join(str(p) for p in e.path) or "<root>"
        errs.append(f"{path}: {e.message}")
    src = record.get("source_probe")
    ver = record.get("verifier_probe")
    verdict = record.get("verdict")
    if verdict in TERMINAL_VERDICTS:
        src_tok = _probe_token(src)
        ver_tok = _probe_token(ver)
        if not src_tok:
            errs.append("source_probe: empty on CONFIRMED|REFUTED")
        if not ver_tok:
            errs.append("verifier_probe: empty on CONFIRMED|REFUTED")
        if src_tok and ver_tok and src_tok == ver_tok:
            errs.append("same-probe-rerun: source_probe fingerprint equals verifier_probe")
    return errs


def schema_valid(record: dict[str, Any]) -> bool:
    return not schema_errors(record)


def validation_result(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {"ok": False, "errors": ["not-an-object"]}
    errs = schema_errors(record)
    return {"ok": not errs, "errors": errs}
