#!/usr/bin/env python3
"""Signed provenance for A7 artifacts.

Uses a labeled test-vector context string mixed into SHA-256. That string is
not a credential: it is a domain separator so provenance bytes are stable and
not confused with live HMAC keys. Do not rotate; do not print as a secret.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

# Domain separator. Not a live key. Never treated as a credential.
TEST_VECTOR_CONTEXT = "ARC-0045-test-vector-not-a-credential"


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sign_artifact(body: Mapping[str, Any], producer: str) -> dict[str, Any]:
    payload = {"body": body, "producer": producer}
    body_digest = digest_bytes(canonical(body))
    material = TEST_VECTOR_CONTEXT.encode("utf-8") + b"\n" + canonical(payload)
    sig = hashlib.sha256(material).hexdigest()
    return {
        "alg": "sha256-domain-separated",
        "context": TEST_VECTOR_CONTEXT,
        "digest": body_digest,
        "ok": True,
        "producer": producer,
        "signature": sig,
    }


def verify_artifact(body: Mapping[str, Any], provenance: Mapping[str, Any]) -> dict[str, Any]:
    expected = sign_artifact(body, str(provenance.get("producer") or ""))
    ok = (
        provenance.get("digest") == expected["digest"]
        and provenance.get("signature") == expected["signature"]
        and provenance.get("context") == TEST_VECTOR_CONTEXT
        and provenance.get("alg") == "sha256-domain-separated"
    )
    return {
        "ok": bool(ok),
        "digest": expected["digest"],
        "reason": "match" if ok else "provenance-mismatch",
    }
