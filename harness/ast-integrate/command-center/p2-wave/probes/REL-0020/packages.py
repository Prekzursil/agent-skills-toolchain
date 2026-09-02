"""Old vs new package payloads for REL-0020.

Behaviour tokens are the distinguisher. Version strings are deliberately
different strings and MUST NOT be used as the execute() observation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

PACKAGE_NAME = "rel0020-canary-plugin"

# Behavioural output that distinguishes old bytes from new bytes.
# These are not version strings.
OLD_BEHAVIOUR = "BEHAVE-POISON-v1-old-bytes"
NEW_BEHAVIOUR = "BEHAVE-FIXED-v2-new-bytes"

OLD_VERSION = "1.0.0"
NEW_VERSION = "1.0.1"


@dataclass(frozen=True)
class Package:
    name: str
    version: str
    behaviour: str

    def payload(self) -> bytes:
        body = {
            "behaviour": self.behaviour,
            "name": self.name,
            "payload_kind": "plugin-bytes",
        }
        return (
            json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            + "\n"
        ).encode("utf-8")

    def digest(self) -> str:
        return hashlib.sha256(self.payload()).hexdigest()


OLD = Package(PACKAGE_NAME, OLD_VERSION, OLD_BEHAVIOUR)
NEW = Package(PACKAGE_NAME, NEW_VERSION, NEW_BEHAVIOUR)


def behaviour_from_bytes(raw: bytes | None) -> str | None:
    if not raw:
        return None
    if raw.startswith(b"PYC\0"):
        raw = raw[4:]
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(doc, dict):
        return None
    b = doc.get("behaviour")
    return str(b) if isinstance(b, str) and b.startswith("BEHAVE-") else None


def assert_tokens_distinct() -> None:
    if OLD_BEHAVIOUR == NEW_BEHAVIOUR:
        raise RuntimeError("behaviour tokens collided")
    if OLD_VERSION == NEW_VERSION:
        raise RuntimeError("version strings collided")
    if OLD_BEHAVIOUR in {OLD_VERSION, NEW_VERSION}:
        raise RuntimeError("old behaviour token equals a version string")
    if NEW_BEHAVIOUR in {OLD_VERSION, NEW_VERSION}:
        raise RuntimeError("new behaviour token equals a version string")
    if OLD.digest() == NEW.digest():
        raise RuntimeError("old and new payloads hashed equal")
