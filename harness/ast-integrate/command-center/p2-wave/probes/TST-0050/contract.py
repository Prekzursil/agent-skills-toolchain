"""Frozen telemetry/privacy contract for TST-0050.

Written BEFORE a product telemetry implementation. ARC-0096 is the catalog
contract unit; its JSON is not required on disk for this suite to exist.
The declared field set is the allowlist later implementation must satisfy.
"""
from __future__ import annotations

import hashlib
from typing import Any

DECLARED_FIELDS: frozenset[str] = frozenset(
    {
        "event_name",
        "event_id",
        "schema_version",
        "ts",
        "session_ref",
        "duration_ms",
        "outcome",
        "opt_in_record_id",
        "destination",
    }
)

OUTCOMES: frozenset[str] = frozenset({"ok", "error", "disabled"})
LOCAL_DESTINATIONS: frozenset[str] = frozenset({"local", "", "none"})

RULES: tuple[str, ...] = (
    "declared-fields",
    "no-credential",
    "no-path",
    "no-user-content",
    "egress-requires-opt-in",
    "opt-in-in-decision-log",
    "disabled-emits-nothing",
)

PATH_CANARY = "/home/tst0050-canary/project/secret.txt"
USER_CANARY = "USERPROMPT-CANARY-TST0050-do-not-transmit"
CREDENTIAL_PREFIX = "sk-ant-TESTONLY-"

LEAK_NEEDLES: tuple[str, ...] = (CREDENTIAL_PREFIX, PATH_CANARY, USER_CANARY)


def credential_canary() -> str:
    """Deterministic fake token. Pattern-matched; never a live key."""
    digest = hashlib.sha256(b"TST-0050-in-memory-credential-canary").hexdigest()
    return CREDENTIAL_PREFIX + digest


def value_fingerprint(value: Any) -> dict[str, Any]:
    """Describe a sensitive value without reproducing it."""
    if value is None:
        raw = b""
    elif isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
    else:
        raw = str(value).encode("utf-8")
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "len": len(raw),
    }


def is_off_box_destination(destination: Any) -> bool:
    if destination is None:
        return False
    text = str(destination).strip()
    if not text or text in LOCAL_DESTINATIONS:
        return False
    lowered = text.lower()
    return lowered.startswith("http://") or lowered.startswith("https://")
