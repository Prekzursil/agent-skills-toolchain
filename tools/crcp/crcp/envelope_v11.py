"""CRCP envelope v1.1 validation contract."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any


SCHEMA = "crcp.envelope.v1.1"
REQUIRED = (
    "schema",
    "id",
    "created_at",
    "event_key",
    "trace_id",
    "kind",
    "from_rail",
    "to_rail",
    "intent",
)
KINDS = {"event", "task.request", "task.result", "status", "error"}
_SHA_REF = re.compile(r"^sha256:[0-9a-f]{64}$")


def validate_envelope(envelope: Any) -> list[str]:
    """Return all validation errors; an empty list means valid v1.1."""
    if not isinstance(envelope, dict):
        return ["envelope must be an object"]
    errors: list[str] = []
    for field in REQUIRED:
        if field not in envelope or envelope[field] in (None, ""):
            errors.append(f"missing required field: {field}")
    if envelope.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    for field in ("id", "trace_id"):
        value = envelope.get(field)
        if value:
            try:
                uuid.UUID(str(value))
            except (ValueError, TypeError, AttributeError):
                errors.append(f"{field} must be a UUID")
    created_at = envelope.get("created_at")
    if created_at:
        try:
            parsed = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                errors.append("created_at must include a timezone")
        except (ValueError, TypeError):
            errors.append("created_at must be ISO-8601")
    if envelope.get("kind") and envelope["kind"] not in KINDS:
        errors.append(f"kind must be one of: {', '.join(sorted(KINDS))}")
    for field in ("event_key", "from_rail", "to_rail", "intent"):
        if field in envelope and not isinstance(envelope[field], str):
            errors.append(f"{field} must be a string")
    payload_ref = envelope.get("payload_ref")
    if payload_ref is not None and (
        not isinstance(payload_ref, str) or not _SHA_REF.fullmatch(payload_ref)
    ):
        errors.append(
            "payload_ref must be a content address: sha256:<64 lowercase hex>"
        )
    if "payload" in envelope and payload_ref is not None:
        errors.append("payload and payload_ref are mutually exclusive")
    capabilities = envelope.get("capabilities_required", [])
    if not isinstance(capabilities, list) or not all(
        isinstance(item, str) and item for item in capabilities
    ):
        errors.append("capabilities_required must be a list of non-empty strings")
    meta = envelope.get("meta", {})
    if not isinstance(meta, dict):
        errors.append("meta must be an object")
    return errors


def require_valid(envelope: Any) -> None:
    errors = validate_envelope(envelope)
    if errors:
        raise ValueError("; ".join(errors))
