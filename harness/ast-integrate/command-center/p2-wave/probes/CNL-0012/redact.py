"""Credential-safe classification. Never returns or prints secret values."""
from __future__ import annotations

import os

PLANTED_SYNTHETIC = "cnl0012-planted-synthetic-credential-NOT-A-REAL-KEY"

_PREFIXES = (
    ("sk-ant-", "sk-ant-"),
    ("sk-proj-", "sk-proj-"),
    ("sk-", "sk-"),
    ("crv1_", "crv1_"),
)

_CRED_NEEDLES = ("API_KEY", "AUTH_TOKEN", "ACCESS_TOKEN", "SECRET", "PASSWORD")


def classify_secret(val: str | None) -> dict:
    if val is None:
        return {"present": False, "length": 0, "prefix_class": "absent", "ws_only": False}
    stripped = val.strip() if isinstance(val, str) else str(val).strip()
    if not stripped:
        return {"present": False, "length": 0, "prefix_class": "empty", "ws_only": True}
    prefix = "other"
    for raw, name in _PREFIXES:
        if stripped.startswith(raw):
            prefix = name
            break
    return {
        "present": True,
        "length": len(stripped),
        "prefix_class": prefix,
        "ws_only": False,
    }


def credential_env_names() -> list[str]:
    names = []
    for key in os.environ:
        upper = key.upper()
        if any(n in upper for n in _CRED_NEEDLES):
            names.append(key)
    return sorted(names)


def live_secret_needles() -> dict[str, str]:
    """Map env name -> value for leak scanning. Callers must not serialise values."""
    out: dict[str, str] = {}
    for name in credential_env_names():
        val = os.environ.get(name) or ""
        if len(val) >= 12:
            out[name] = val
    return out


def leak_hits(text: str, extra: list[str] | None = None) -> list[str]:
    """Return env *names* (never values) whose live secrets appear in text."""
    hits: list[str] = []
    for name, val in live_secret_needles().items():
        if val and val in text:
            hits.append(name)
    for item in extra or []:
        if item and item in text:
            hits.append("planted-synthetic")
    return hits


def scanner_detects_plant() -> bool:
    sample = "debug-prefix " + PLANTED_SYNTHETIC + " debug-suffix"
    return PLANTED_SYNTHETIC in sample and "planted-synthetic" in leak_hits(
        sample, extra=[PLANTED_SYNTHETIC]
    )
