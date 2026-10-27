"""Per-round unlinkable pseudonyms."""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any


@dataclass
class AnonymityConfig:
    secret: bytes
    rounds: int = 1


def secret_from_text(text: str) -> bytes:
    return hashlib.sha256(text.encode("utf-8")).digest()


def publish_session(config: AnonymityConfig, real_id: str, round_id: int) -> str:
    msg = f"{round_id}:{real_id}".encode("utf-8")
    return hmac.new(config.secret, msg, hashlib.sha256).hexdigest()[:16]


def census_real_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(r.get("real_id") or r.get("id")) for r in rows}


def linkage_attack(published: list[str], real_ids: list[str], config: AnonymityConfig, round_id: int) -> dict[str, Any]:
    mapping = {rid: publish_session(config, rid, round_id) for rid in real_ids}
    hits = sum(1 for p in published if p in mapping.values())
    return {"hits": hits, "n": len(published)}


def score_linkage(attack: dict[str, Any]) -> float:
    n = max(1, int(attack.get("n") or 1))
    return float(attack.get("hits") or 0) / n


def truth_index_from_raw(raw: list[dict[str, Any]]) -> dict[str, str]:
    return {str(r.get("pseudo") or r.get("id")): str(r.get("real_id") or "") for r in raw}
