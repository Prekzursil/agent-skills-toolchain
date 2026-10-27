"""Seat partitions: delivered context mapping and leak scan."""
from __future__ import annotations

A16_ALLOWED_CANARY = "A16-ALLOWED-CANARY"
A16_CANARY = A16_ALLOWED_CANARY

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Fact:
    fact_id: str
    partitions: list[str]
    token: str
    body: str


@dataclass
class DeliveredContext:
    seat_id: str
    partition_id: str
    fact_ids: list[str]
    tokens: list[str]
    prompt: str


def load_spec(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _visible_facts(spec: dict[str, Any], seat_id: str) -> list[Fact]:
    seats = {s["seat_id"]: s for s in spec.get("seats") or []}
    part = seats[seat_id]["partition_id"]
    out: list[Fact] = []
    for raw in spec.get("facts") or []:
        parts = list(raw.get("partitions") or [])
        if "*" in parts or part in parts:
            out.append(
                Fact(
                    fact_id=raw["fact_id"],
                    partitions=parts,
                    token=raw.get("token") or "",
                    body=raw.get("body") or "",
                )
            )
    return out


def facts_visible(spec: dict[str, Any], seat_id: str) -> list[Fact]:
    return _visible_facts(spec, seat_id)


def tokens_withheld(spec: dict[str, Any], seat_id: str) -> list[str]:
    visible = {f.fact_id for f in _visible_facts(spec, seat_id)}
    out = []
    for raw in spec.get("facts") or []:
        if raw["fact_id"] not in visible:
            tok = raw.get("token")
            if tok:
                out.append(tok)
    return out


def deliver_all(spec: dict[str, Any]) -> dict[str, DeliveredContext]:
    delivered: dict[str, DeliveredContext] = {}
    for seat in spec.get("seats") or []:
        sid = seat["seat_id"]
        facts = _visible_facts(spec, sid)
        prompt = "\n".join(f.body for f in facts)
        delivered[sid] = DeliveredContext(
            seat_id=sid,
            partition_id=seat["partition_id"],
            fact_ids=[f.fact_id for f in facts],
            tokens=[f.token for f in facts if f.token],
            prompt=prompt,
        )
    return delivered


def partitions_differ(delivered: dict[str, DeliveredContext]) -> bool:
    prompts = [c.prompt for c in delivered.values()]
    return len(set(prompts)) == len(prompts)


def scan_text(text: str, tokens: list[str]) -> list[str]:
    return [t for t in tokens if t and t in text]


def scan_delivered(spec: dict[str, Any], delivered: dict[str, DeliveredContext]) -> list[dict[str, Any]]:
    hits = []
    for sid, ctx in delivered.items():
        leaked = [t for t in tokens_withheld(spec, sid) if t in ctx.prompt]
        for tok in leaked:
            hits.append({"seat_id": sid, "token": tok})
    return hits


def detector_control(prompt: str, token: str) -> bool:
    return token in prompt
