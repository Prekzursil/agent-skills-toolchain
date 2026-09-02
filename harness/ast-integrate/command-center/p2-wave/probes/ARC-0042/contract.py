"""A6 common-contract wrap: portable payload in, vendor remainder queued.

Portable fields round-trip in both directions. Remainder is held, never
stuffed through an opaque passthrough and never silently dropped.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

CONTRACT_ID = "a6-common/v1"
PORTABLE_FIELDS = ("unit_id", "sentinel", "body")
META_FIELDS = frozenset({"contract", "payload", "payload_sha256", "remainder"})


def canonical_bytes(obj: Any) -> bytes:
    return (
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_obj(obj: Any) -> str:
    return sha256_bytes(canonical_bytes(obj))


def portable(old: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in PORTABLE_FIELDS:
        if key not in old:
            raise KeyError(f"old artifact missing portable field {key!r}")
        out[key] = old[key]
    return out


def remainder_of(old: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in old.items() if k not in PORTABLE_FIELDS}


def wrap(old: Mapping[str, Any]) -> dict[str, Any]:
    payload = portable(old)
    rem = remainder_of(old)
    return {
        "contract": CONTRACT_ID,
        "payload": payload,
        "payload_sha256": sha256_obj(payload),
        "remainder": rem,
    }


def unwrap(wrapped: Mapping[str, Any]) -> dict[str, Any]:
    payload = wrapped.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("wrapped artifact missing payload object")
    return portable(payload)


def both_directions(old: Mapping[str, Any]) -> bool:
    wrapped = wrap(old)
    back = unwrap(wrapped)
    return sha256_obj(back) == sha256_obj(portable(old)) and sha256_obj(
        wrapped["payload"]
    ) == sha256_obj(portable(old))


def refuse_drop_remainder(wrapped: Mapping[str, Any], requested: str) -> dict[str, Any]:
    rem = wrapped.get("remainder") or {}
    nonempty = bool(rem)
    if requested == "TAKE-NEW-DROP-REMAINDER" and nonempty:
        return {
            "id": "neg-drop-remainder",
            "requested": requested,
            "refused": True,
            "decision": "REFUSE-DROP-REMAINDER",
            "reason": (
                "vendor-only remainder is queued for adjudication; "
                "TAKE-NEW-DROP-REMAINDER would lose working-rail fields"
            ),
            "held_fields": sorted(rem.keys()),
            "pass": True,
        }
    return {
        "id": "neg-drop-remainder",
        "requested": requested,
        "refused": False,
        "decision": "NOT-APPLICABLE" if not nonempty else "UNEXPECTED-ALLOW",
        "reason": "no remainder to refuse" if not nonempty else "drop was not refused",
        "held_fields": sorted(rem.keys()) if isinstance(rem, dict) else [],
        "pass": False,
    }
