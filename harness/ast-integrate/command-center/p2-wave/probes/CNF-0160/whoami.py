#!/usr/bin/env python3
"""Read-only third-rail / session-rail auth posture.

Never prints credential values. Never creates, changes, or deletes a
credential. The only subprocess, if the binary exists, is
`cursor-agent whoami --format json` (status alias of the same command).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any

# Pair under CNF-0154 / Anthropic. A third rail must be independent of both.
PAIR_RAILS: dict[str, tuple[str, ...]] = {
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openai-codex": ("OPENAI_API_KEY",),
}
THIRD_RAILS: dict[str, tuple[str, ...]] = {
    "google-gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "xai": ("XAI_API_KEY",),
    "groq": ("GROQ_API_KEY",),
}
SESSION_RAILS: dict[str, tuple[str, ...]] = {
    "cursor": ("CURSOR_API_KEY",),
}

_ALL_CRED_NAMES: tuple[str, ...] = tuple(
    name
    for group in (PAIR_RAILS, THIRD_RAILS, SESSION_RAILS)
    for names in group.values()
    for name in names
)

WHOAMI_ARGV = ("cursor-agent", "whoami", "--format", "json")


def env_presence(names: tuple[str, ...]) -> dict[str, Any]:
    """Presence and byte-length only. Never the value."""
    rows = []
    present_any = False
    for name in names:
        raw = os.environ.get(name)
        present = bool(raw)
        present_any = present_any or present
        rows.append(
            {
                "name": name,
                "present": present,
                "bytes": len(raw) if raw else 0,
            }
        )
    return {"present": present_any, "variables": rows}


def snapshot_env() -> dict[str, Any]:
    """Hashable posture of credential env. Names + lengths, never values."""
    cred_lens = {n: len(os.environ.get(n) or "") for n in _ALL_CRED_NAMES}
    return {
        "environ_key_count": len(os.environ),
        "environ_names": sorted(os.environ.keys()),
        "credential_lengths": cred_lens,
    }


def snapshots_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return (
        a.get("environ_key_count") == b.get("environ_key_count")
        and a.get("environ_names") == b.get("environ_names")
        and a.get("credential_lengths") == b.get("credential_lengths")
    )


def _redact_whoami_payload(doc: Any) -> dict[str, Any]:
    """Keep authentication booleans. Drop email, names, tokens, ids."""
    if not isinstance(doc, dict):
        return {"parsed": False, "authenticated": False}
    user = doc.get("userInfo") if isinstance(doc.get("userInfo"), dict) else {}
    return {
        "parsed": True,
        "authenticated": bool(doc.get("isAuthenticated") or doc.get("status") == "authenticated"),
        "has_access_token": bool(doc.get("hasAccessToken")),
        "has_refresh_token": bool(doc.get("hasRefreshToken")),
        "user_info_present": bool(user),
        # no email, no userId, no names, no tokens
    }


def cursor_whoami() -> dict[str, Any]:
    """Read-only whoami. Does not pass a key flag. Does not sign in or out."""
    binary = shutil.which("cursor-agent")
    if not binary:
        return {
            "ran": False,
            "authenticated": False,
            "reason": "cursor-agent-binary-absent",
        }
    try:
        proc = subprocess.run(
            list(WHOAMI_ARGV),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "ran": False,
            "authenticated": False,
            "reason": f"whoami-error:{type(exc).__name__}",
        }
    payload: dict[str, Any]
    try:
        payload = _redact_whoami_payload(json.loads(proc.stdout or "{}"))
    except json.JSONDecodeError:
        payload = {"parsed": False, "authenticated": False}
    return {
        "ran": True,
        "argv": list(WHOAMI_ARGV),
        "exit_code": proc.returncode,
        "authenticated": bool(payload.get("authenticated")),
        "has_access_token": bool(payload.get("has_access_token")),
        "user_info_present": bool(payload.get("user_info_present")),
        "credential_printed": False,
    }


def third_rail_available(posture: dict[str, Any] | None = None) -> bool:
    doc = posture if posture is not None else diagnose()
    thirds = doc.get("third_rails") or {}
    return any(
        isinstance(row, dict) and row.get("present") for row in thirds.values()
    )


def diagnose() -> dict[str, Any]:
    before = snapshot_env()
    pair = {k: env_presence(v) for k, v in PAIR_RAILS.items()}
    third = {k: env_presence(v) for k, v in THIRD_RAILS.items()}
    session = {k: env_presence(v) for k, v in SESSION_RAILS.items()}
    who = cursor_whoami()
    after = snapshot_env()
    mutated = not snapshots_equal(before, after)
    available = any(row.get("present") for row in third.values())
    missing = [
        name for name, row in third.items() if not row.get("present")
    ]
    return {
        "read_only": True,
        "credential_mutated": mutated,
        "credential_created": False,
        "credential_rotated": False,
        "credential_unset": False,
        "pair_rails": pair,
        "third_rails": third,
        "session_rails": session,
        "cursor_whoami": who,
        "third_rail_available": available,
        "missing_third_rails": missing,
        "missing_prerequisite": (
            None if available else "third-vendor-rail-unauthenticated"
        ),
        "note": (
            "Cursor session whoami may confirm THIS confirmer authenticates. "
            "Cursor is not an independent third vendor vs Anthropic/Codex."
        ),
    }
