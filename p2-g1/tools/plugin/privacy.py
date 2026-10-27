"""IMP-0057 privacy posture: local-only by default, opt-in owner-gated.

Enabling egress changes privacy posture. This module never flips that bit
without a version-specific consent record. File contents, prompts, and paths
are stripped even from the local sink so a later transport cannot leak them.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

_LIB = Path(__file__).resolve().parent.parent / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import net_allowlist as na  # noqa: E402

POSTURE_LOCAL_ONLY = "LOCAL_ONLY"
POSTURE_OWNER_GATED_EGRESS = "OWNER_GATED_EGRESS"
CONSENT_SCHEMA = "plugin.consent/v1"


class PrivacyError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ConsentRecord:
    schema: str
    version: str
    owner_id: str
    granted_at: str
    destinations: tuple[str, ...]
    fields: tuple[str, ...]
    owner_gated: bool
    purpose: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "version": self.version,
            "owner_id": self.owner_id,
            "granted_at": self.granted_at,
            "destinations": list(self.destinations),
            "fields": list(self.fields),
            "owner_gated": self.owner_gated,
            "purpose": self.purpose,
        }


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_consent(doc: Mapping[str, Any]) -> ConsentRecord:
    if doc.get("schema") != CONSENT_SCHEMA:
        raise PrivacyError("CONSENT_SCHEMA", "consent schema must be plugin.consent/v1")
    version = str(doc.get("version") or "").strip()
    if not version or version.lower() in {"*", "all", "any", "blanket"}:
        raise PrivacyError("CONSENT_NOT_VERSIONED", "consent must name a concrete version")
    if doc.get("owner_gated") is not True:
        raise PrivacyError("CONSENT_NOT_OWNER_GATED", "consent.owner_gated must be true")
    owner = str(doc.get("owner_id") or "").strip()
    if not owner:
        raise PrivacyError("CONSENT_NO_OWNER", "consent.owner_id required")
    dests = doc.get("destinations")
    if not isinstance(dests, list):
        raise PrivacyError("CONSENT_DESTINATIONS", "consent.destinations must be a list")
    fields = doc.get("fields") if isinstance(doc.get("fields"), list) else []
    return ConsentRecord(
        schema=CONSENT_SCHEMA,
        version=version,
        owner_id=owner,
        granted_at=str(doc.get("granted_at") or _utc()),
        destinations=tuple(str(d) for d in dests),
        fields=tuple(str(f) for f in fields),
        owner_gated=True,
        purpose=str(doc.get("purpose") or ""),
    )


def load_consent(path: Path | None) -> ConsentRecord | None:
    if path is None or not path.is_file():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise PrivacyError("CONSENT_NOT_OBJECT", "consent file must be a JSON object")
    return parse_consent(doc)


def default_posture() -> str:
    return POSTURE_LOCAL_ONLY


def posture_for(consent: ConsentRecord | None) -> str:
    if consent is None:
        return POSTURE_LOCAL_ONLY
    return POSTURE_OWNER_GATED_EGRESS


def sanitize_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Drop forbidden fields. Used for local sink AND any future egress."""
    clean: dict[str, Any] = {}
    for key, value in event.items():
        if str(key).lower() in na.FORBIDDEN_PAYLOAD_FIELDS:
            continue
        if isinstance(value, str) and _looks_like_path(value):
            continue
        clean[str(key)] = value
    return clean


def _looks_like_path(value: str) -> bool:
    if value.startswith("/") and "/" in value[1:]:
        return True
    if len(value) >= 3 and value[1:3] in {":\\", ":/"}:
        return True
    return False


def try_egress(url: str, event: Mapping[str, Any], consent: ConsentRecord | None) -> None:
    """The only production call into the allowlist gate. Default: always denies."""
    payload = sanitize_event(event)
    ctx = {"consent": consent.as_dict() if consent else None}
    na.gated_request(url, payload, ctx)
