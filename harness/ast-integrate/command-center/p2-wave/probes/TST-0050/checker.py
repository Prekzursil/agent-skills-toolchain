"""Telemetry payload checker. Never prints credential or path values."""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from contract import (
    CREDENTIAL_PREFIX,
    DECLARED_FIELDS,
    LEAK_NEEDLES,
    OUTCOMES,
    USER_CANARY,
    credential_canary,
    is_off_box_destination,
    value_fingerprint,
)

CREDENTIAL_RE = re.compile(
    r"(?i)("
    r"sk-ant-"
    r"|sk-[a-z]{2,}-"
    r"|gh[pousr]_"
    r"|github_pat_"
    r"|xox[baprs]-"
    r"|akia[0-9a-z]{16}"
    r"|begin (?:rsa |openssh )?private key"
    r")"
)

PATH_RE = re.compile(
    r"(?i)^("
    r"/(?:home|users|root|opt|var|tmp)/"
    r"|[a-z]:[\\/]"
    r"|~/"
    r")"
)

USER_MARKERS: tuple[str, ...] = (
    USER_CANARY,
    "USERPROMPT-CANARY-",
)


def shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    n = float(len(text))
    return -sum((c / n) * math.log2(c / n) for c in counts.values() if c)

def is_url(text: str) -> bool:
    lowered = text.lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


TS_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def is_credential_shaped(value: str) -> bool:
    if not value:
        return False
    if is_url(value) or TS_RE.match(value) or UUID_RE.match(value):
        return False
    if CREDENTIAL_RE.search(value):
        return True
    if len(value) >= 32 and shannon_entropy(value) >= 4.0:
        alnum = sum(ch.isalnum() for ch in value)
        if alnum / len(value) >= 0.85 and "://" not in value and "/" not in value:
            return True
    return False


def is_path_shaped(value: str) -> bool:
    if not value or is_url(value):
        return False
    if PATH_RE.match(value):
        return True
    if value.startswith("/") and "/" in value[1:] and "://" not in value:
        return True
    return False


def is_user_content(value: str) -> bool:
    if not value:
        return False
    for marker in USER_MARKERS:
        if marker in value:
            return True
    return False


def walk_strings(obj: Any, prefix: str = "") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for key, val in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            out.extend(walk_strings(val, path))
    elif isinstance(obj, list):
        for i, val in enumerate(obj):
            path = f"{prefix}[{i}]"
            out.extend(walk_strings(val, path))
    elif isinstance(obj, str):
        out.append((prefix, obj))
    return out


def walk_keys(obj: Any, prefix: str = "") -> list[str]:
    keys: list[str] = []
    if isinstance(obj, dict):
        for key, val in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            keys.append(path)
            keys.extend(walk_keys(val, path))
    elif isinstance(obj, list):
        for i, val in enumerate(obj):
            keys.extend(walk_keys(val, f"{prefix}[{i}]"))
    return keys


def extra_fields(payload: dict[str, Any]) -> list[str]:
    extras: list[str] = []
    for path in walk_keys(payload):
        top = path.split(".", 1)[0].split("[", 1)[0]
        if top not in DECLARED_FIELDS:
            extras.append(path)
    return sorted(set(extras))


def check_payload(
    payload: Any,
    *,
    decision_log_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Return findings. Sensitive values are fingerprinted, never copied."""
    findings: list[dict[str, Any]] = []
    log_ids = decision_log_ids or set()

    if not isinstance(payload, dict):
        return {
            "ok": False,
            "findings": [
                {
                    "rule": "declared-fields",
                    "field": "",
                    "kind": "not-object",
                    **value_fingerprint(payload),
                }
            ],
            "extra_fields": [],
            "credential_shaped_count": 0,
            "path_shaped_count": 0,
            "user_content_count": 0,
        }

    extras = extra_fields(payload)
    for field in extras:
        findings.append(
            {
                "rule": "declared-fields",
                "field": field,
                "kind": "undeclared-field",
            }
        )

    outcome = payload.get("outcome")
    if outcome is not None and outcome not in OUTCOMES:
        findings.append(
            {
                "rule": "declared-fields",
                "field": "outcome",
                "kind": "illegal-outcome",
            }
        )

    for field, text in walk_strings(payload):
        if is_credential_shaped(text):
            findings.append(
                {
                    "rule": "no-credential",
                    "field": field,
                    "kind": "credential-shaped",
                    **value_fingerprint(text),
                }
            )
        if is_path_shaped(text):
            findings.append(
                {
                    "rule": "no-path",
                    "field": field,
                    "kind": "path-shaped",
                    **value_fingerprint(text),
                }
            )
        if is_user_content(text):
            findings.append(
                {
                    "rule": "no-user-content",
                    "field": field,
                    "kind": "user-content",
                    **value_fingerprint(text),
                }
            )

    destination = payload.get("destination")
    opt_in = payload.get("opt_in_record_id")
    if is_off_box_destination(destination):
        if not isinstance(opt_in, str) or not opt_in.strip():
            findings.append(
                {
                    "rule": "egress-requires-opt-in",
                    "field": "destination",
                    "kind": "egress-without-opt-in",
                }
            )
        elif opt_in not in log_ids:
            findings.append(
                {
                    "rule": "opt-in-in-decision-log",
                    "field": "opt_in_record_id",
                    "kind": "opt-in-not-in-decision-log",
                    **value_fingerprint(opt_in),
                }
            )

    cred_n = sum(1 for f in findings if f.get("kind") == "credential-shaped")
    path_n = sum(1 for f in findings if f.get("kind") == "path-shaped")
    user_n = sum(1 for f in findings if f.get("kind") == "user-content")
    return {
        "ok": not findings,
        "findings": findings,
        "extra_fields": extras,
        "credential_shaped_count": cred_n,
        "path_shaped_count": path_n,
        "user_content_count": user_n,
    }


def leak_needles_in(text: str) -> list[str]:
    hits = [n for n in LEAK_NEEDLES if n in text]
    if credential_canary() in text and CREDENTIAL_PREFIX not in hits:
        hits.append(CREDENTIAL_PREFIX)
    return hits
