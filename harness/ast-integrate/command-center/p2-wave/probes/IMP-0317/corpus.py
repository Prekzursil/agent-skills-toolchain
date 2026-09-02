"""Synthetic planted-secret corpus for IMP-0317.

Bodies are obviously fake (SYNTHETIC-NOT-A-LIVE-SECRET). They are never live
credentials. Callers must not print a body; use encodings_present() / digests.
"""
from __future__ import annotations

import base64
import hashlib
from typing import Any

# Four encodings the catalog names. Distinct bodies so a leak is attributable.
BODIES: dict[str, str] = {
    "env": "imp0317-env-body-SYNTHETIC-NOT-A-LIVE-SECRET-9f3c2a1b",
    "json": "imp0317-json-body-SYNTHETIC-NOT-A-LIVE-SECRET-7e4d8c2f",
    "camelCase": "imp0317-camel-body-SYNTHETIC-NOT-A-LIVE-SECRET-1a2b3c4d",
    "base64": "imp0317-b64-body-SYNTHETIC-NOT-A-LIVE-SECRET-5e6f7a8b",
}

ENCODINGS = ("env", "json", "camelCase", "base64")


def b64_blob() -> str:
    return base64.b64encode(BODIES["base64"].encode("utf-8")).decode("ascii")


def body_digest(kind: str) -> str:
    return hashlib.sha256(BODIES[kind].encode("utf-8")).hexdigest()


def transcript() -> dict[str, Any]:
    """A council transcript with one planted secret per encoding."""
    return {
        "schema": "council-transcript/v1",
        "council_id": "IMP-0317-planted-corpus",
        "turns": [
            {
                "participant": "p-env",
                "text": f"export IMP0317_PLANTED_API_KEY={BODIES['env']}",
            },
            {
                "participant": "p-json",
                "text": 'pasted {"password": "' + BODIES["json"] + '"}',
            },
            {
                "participant": "p-camel",
                "provider": {"apiKey": BODIES["camelCase"]},
            },
            {
                "participant": "p-b64",
                "text": f"legacy_credential={b64_blob()}",
            },
        ],
    }


def encodings_present(data: bytes | str) -> dict[str, bool]:
    """Which planted bodies (or the base64 encoding of the b64 body) survive."""
    text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data
    return {
        "env": BODIES["env"] in text,
        "json": BODIES["json"] in text,
        "camelCase": BODIES["camelCase"] in text,
        "base64": BODIES["base64"] in text or b64_blob() in text,
    }


def survivor_kinds(data: bytes | str) -> list[str]:
    present = encodings_present(data)
    return [k for k in ENCODINGS if present[k]]
