#!/usr/bin/env python3
"""Independent recount of CNL-0016 draws (reviewer path).

Re-implements HMAC-SHA256 Fisher-Yates from the published domain strings
without calling sampler.fisher_yates_take. A disagreement with sampler.py
blocks the unit.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

DOMAIN_UNIFORM = b"CNL-0016|uniform"
DOMAIN_STRATUM_PREFIX = b"CNL-0016|stratum|"
DOMAIN_FRAME = b"CNL-0016|frame"

HERE = Path(__file__).resolve().parent


def _eligible_sorted(participants: list[dict]) -> list[dict]:
    out = [p for p in participants if p.get("eligible") is True]
    out.sort(key=lambda p: str(p["id"]))
    return out


def _fingerprint(frame: list[dict], stratum_key: str) -> str:
    rows = [{"id": p["id"], "stratum": p[stratum_key]} for p in frame]
    blob = json.dumps(rows, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hmac.new(DOMAIN_FRAME, blob, hashlib.sha256).hexdigest()


def _child_key(seed: bytes, domain: bytes) -> bytes:
    return hmac.new(seed, domain, hashlib.sha256).digest()


def _stream_u64(key: bytes, i: int) -> int:
    digest = hmac.new(key, i.to_bytes(8, "big"), hashlib.sha256).digest()
    return int.from_bytes(digest[:8], "big")


def _draw_without_replacement(ordered_ids: list[str], k: int, key: bytes) -> list[str]:
    """Same math as sampler.fisher_yates_take, different control flow."""
    if k > len(ordered_ids):
        raise ValueError("quota exceeds stratum")
    seats = list(ordered_ids)
    stream = 0
    chosen: list[str] = []
    remaining_n = len(seats)
    cursor = 0
    while len(chosen) < k:
        modulus = remaining_n
        cap = (2**64 // modulus) * modulus
        while True:
            stream += 1
            sample = _stream_u64(key, stream)
            if sample < cap:
                offset = sample % modulus
                break
        pick_at = cursor + offset
        seats[cursor], seats[pick_at] = seats[pick_at], seats[cursor]
        chosen.append(seats[cursor])
        cursor += 1
        remaining_n -= 1
    return chosen


def recount_uniform(participants: list[dict], k: int, seed: bytes) -> dict:
    frame = _eligible_sorted(participants)
    key = _child_key(seed, DOMAIN_UNIFORM)
    roster = _draw_without_replacement([p["id"] for p in frame], k, key)
    return {
        "roster": roster,
        "frame_ids": [p["id"] for p in frame],
        "frame_fingerprint": _fingerprint(frame, "vendor"),
        "mode": "uniform",
    }


def recount_stratified(
    participants: list[dict], quotas: dict[str, int], seed: bytes
) -> dict:
    frame = _eligible_sorted(participants)
    grouped: dict[str, list[str]] = {}
    for person in frame:
        grouped.setdefault(person["vendor"], []).append(person["id"])
    roster: list[str] = []
    for name in sorted(quotas):
        key = _child_key(seed, DOMAIN_STRATUM_PREFIX + name.encode("utf-8"))
        roster.extend(
            _draw_without_replacement(grouped.get(name, []), int(quotas[name]), key)
        )
    return {
        "roster": roster,
        "frame_ids": [p["id"] for p in frame],
        "frame_fingerprint": _fingerprint(frame, "vendor"),
        "mode": "stratified",
    }


def load_fixtures() -> tuple[list[dict], dict]:
    pool = json.loads((HERE / "fixtures" / "pool.json").read_text(encoding="utf-8"))
    spec = json.loads((HERE / "fixtures" / "draw_spec.json").read_text(encoding="utf-8"))
    return pool["participants"], spec
