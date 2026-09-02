"""Publisher identity model and key custody (IMP-0075)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

REASON_ACCEPTED = "accepted"
REASON_EXPIRED = "expired"
REASON_NOT_YET = "not-yet-valid"
REASON_UNKNOWN_PUBLISHER = "unknown-publisher"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class KeyRecord:
    key_id: str
    valid_from: datetime | None = None
    valid_to: datetime | None = None

    def status_at(self, at: datetime) -> str:
        if self.valid_from and at < self.valid_from:
            return REASON_NOT_YET
        if self.valid_to and at >= self.valid_to:
            return REASON_EXPIRED
        return REASON_ACCEPTED


@dataclass
class Publisher:
    publisher_id: str
    keys: list[KeyRecord] = field(default_factory=list)

    def usable_keys(self, at: datetime) -> list[KeyRecord]:
        return [k for k in self.keys if k.status_at(at) == REASON_ACCEPTED]


@dataclass
class VerifyResult:
    accepted: bool
    reason: str
    publisher_id: str = ""
    key_id: str = ""


class Registry(dict):
    pass


def load_registry(path: str | Path) -> Registry:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = doc.get("publishers") if isinstance(doc, dict) else doc
    reg = Registry()
    if isinstance(rows, dict) and "publisher_id" not in rows:
        iterable = []
        for pid, body in rows.items():
            item = dict(body)
            item.setdefault("publisher_id", pid)
            iterable.append(item)
        rows = iterable
    for item in rows or []:
        pid = str(item.get("publisher_id") or item.get("id") or "")
        keys = []
        for k in item.get("keys") or []:
            keys.append(
                KeyRecord(
                    key_id=str(k.get("key_id") or k.get("id") or ""),
                    valid_from=_parse_dt(k.get("valid_from") or k.get("not_before")),
                    valid_to=_parse_dt(k.get("valid_to") or k.get("not_after")),
                )
            )
        reg[pid] = Publisher(publisher_id=pid, keys=keys)
    return reg


def verify_publisher_key(reg: Registry, publisher_id: str, key_id: str, at: datetime) -> VerifyResult:
    pub = reg.get(publisher_id)
    if pub is None:
        return VerifyResult(False, REASON_UNKNOWN_PUBLISHER, publisher_id, key_id)
    for key in pub.keys:
        if key.key_id == key_id:
            reason = key.status_at(at)
            return VerifyResult(reason == REASON_ACCEPTED, reason, publisher_id, key_id)
    return VerifyResult(False, REASON_UNKNOWN_PUBLISHER, publisher_id, key_id)
