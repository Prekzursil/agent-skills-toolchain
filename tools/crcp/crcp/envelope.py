"""CRCP message envelope — shared bus contract."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_V1 = "crcp.envelope.v1"
SCHEMA_V1_1 = "crcp.envelope.v1.1"
_SCHEMAS = {SCHEMA_V1, SCHEMA_V1_1}
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def content_hash(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in _HEX_DIGITS for character in value)
    )


def _content_address(payload_ref: str | None) -> tuple[str | None, str | None, int | None]:
    """Return a preferred ref plus any digest and size known locally."""
    if payload_ref is None:
        return None, None, None
    if payload_ref.startswith("sha256:"):
        digest = payload_ref[7:]
        if _is_sha256(digest):
            return f"sha256:{digest.lower()}", digest.lower(), None
        return payload_ref, None, None

    try:
        path = Path(payload_ref)
        if path.is_file():
            data = path.read_bytes()
            digest = content_hash(data)
            return f"sha256:{digest}", digest, len(data)
    except (OSError, ValueError):
        # An opaque or legacy reference remains usable by v1-era consumers.
        pass
    return payload_ref, None, None


def _event_key(
    *,
    project_id: str,
    thread_id: str,
    from_rail: str,
    to_rail: str,
    intent: str,
    kind: str,
    payload_sha256: str | None,
) -> str:
    identity = {
        "from_rail": from_rail,
        "intent": intent,
        "kind": kind,
        "payload_sha256": payload_sha256 or "",
        "project_id": project_id,
        "thread_id": thread_id,
        "to_rail": to_rail,
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{content_hash(encoded)}"


def make_envelope(
    *,
    from_rail: str,
    to_rail: str,
    intent: str,
    payload: Any = None,
    payload_ref: str | None = None,
    project_id: str | None = None,
    thread_id: str | None = None,
    completion: str = "SUCCESS",
    capabilities_required: list[str] | None = None,
    meta: dict[str, Any] | None = None,
    event_key: str | None = None,
    trace_id: str | None = None,
    kind: str | None = None,
) -> dict[str, Any]:
    """Build an additive v1.1 CRCP envelope.

    Existing call sites remain valid. Local file references are represented by
    their content address; already-addressed and opaque legacy references are
    preserved. Supplying both ``payload`` and ``payload_ref`` retains the v1
    behavior of preferring the reference.
    """
    resolved_project_id = project_id or ""
    resolved_thread_id = thread_id or str(uuid.uuid4())
    resolved_kind = kind or intent
    resolved_ref, ref_digest, ref_size = _content_address(payload_ref)

    payload_digest: str | None = ref_digest
    if payload is not None and payload_ref is None:
        try:
            serialized = json.dumps(payload, sort_keys=True, default=str)
            payload_digest = content_hash(serialized)
        except Exception:
            payload_digest = None

    env: dict[str, Any] = {
        # Keep the major numeric version for readers that dispatch on v == 1.
        "v": 1,
        "schema": SCHEMA_V1_1,
        "id": str(uuid.uuid4()),
        "created_at": utc_now(),
        "project_id": resolved_project_id,
        "thread_id": resolved_thread_id,
        "from_rail": from_rail,
        "to_rail": to_rail,
        "intent": intent,
        "event_key": event_key
        or _event_key(
            project_id=resolved_project_id,
            thread_id=resolved_thread_id,
            from_rail=from_rail,
            to_rail=to_rail,
            intent=intent,
            kind=resolved_kind,
            payload_sha256=payload_digest,
        ),
        "trace_id": trace_id or str(uuid.uuid4()),
        "kind": resolved_kind,
        "payload_ref": resolved_ref,
        "capabilities_required": capabilities_required or [],
        "completion": completion,
        "meta": meta or {},
    }
    if payload is not None and payload_ref is None:
        env["payload"] = payload
        env["payload_sha256"] = payload_digest
    elif resolved_ref and ref_digest:
        env["payload_sha256"] = ref_digest
        if ref_size is not None:
            env["payload_bytes"] = ref_size
    return env


def validate_envelope(env: Any) -> tuple[bool, list[str]]:
    """Validate a CRCP v1 or v1.1 envelope without mutating it."""
    errors: list[str] = []
    if not isinstance(env, dict):
        return False, ["envelope must be an object"]

    schema = env.get("schema")
    if schema not in _SCHEMAS:
        errors.append(f"schema must be one of {sorted(_SCHEMAS)!r}")
    if env.get("v") != 1:
        errors.append("v must be 1")

    required_strings = ("id", "created_at", "from_rail", "to_rail", "intent", "completion")
    if schema == SCHEMA_V1_1:
        required_strings += ("event_key", "trace_id", "kind")
    for field in required_strings:
        value = env.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} must be a non-empty string")

    for field in ("project_id", "thread_id"):
        if field not in env or not isinstance(env[field], str):
            errors.append(f"{field} must be a string")

    capabilities = env.get("capabilities_required")
    if not isinstance(capabilities, list) or not all(
        isinstance(item, str) and bool(item.strip()) for item in capabilities
    ):
        errors.append("capabilities_required must be a list of non-empty strings")
    if not isinstance(env.get("meta"), dict):
        errors.append("meta must be an object")

    if "payload_ref" not in env:
        errors.append("payload_ref is required")
    payload_ref = env.get("payload_ref")
    if payload_ref is not None and (not isinstance(payload_ref, str) or not payload_ref.strip()):
        errors.append("payload_ref must be null or a non-empty string")
    if isinstance(payload_ref, str) and payload_ref.startswith("sha256:"):
        if not _is_sha256(payload_ref[7:]):
            errors.append("payload_ref sha256 digest must contain exactly 64 hexadecimal characters")

    if "payload" in env and payload_ref is not None:
        errors.append("payload and payload_ref are mutually exclusive")
    digest = env.get("payload_sha256")
    if digest is not None and not _is_sha256(digest):
        errors.append("payload_sha256 must be null or 64 hexadecimal characters")
    if (
        isinstance(payload_ref, str)
        and payload_ref.startswith("sha256:")
        and _is_sha256(payload_ref[7:])
        and isinstance(digest, str)
        and _is_sha256(digest)
        and payload_ref[7:].lower() != digest.lower()
    ):
        errors.append("payload_ref and payload_sha256 must identify the same content")
    size = env.get("payload_bytes")
    if size is not None and (not isinstance(size, int) or isinstance(size, bool) or size < 0):
        errors.append("payload_bytes must be a non-negative integer")

    created_at = env.get("created_at")
    if isinstance(created_at, str) and created_at.strip():
        try:
            parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                errors.append("created_at must include a timezone")
        except ValueError:
            errors.append("created_at must be an ISO-8601 timestamp")

    return not errors, errors


def write_envelope(path: Path, envelope: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(envelope, indent=2, default=str), encoding="utf-8")
    return path
