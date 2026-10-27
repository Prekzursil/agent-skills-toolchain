"""Deterministic crash triage (TST-0117)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable
import hashlib
import json

SEED_RECIPES = (
    {"id": "seed-ff", "payload": b"pad\xffpad"},
    {"id": "seed-fe", "payload": b"sep\xfe"},
    {"id": "seed-ok", "payload": b"harmless"},
)


TARGET_FILE = "/tmp/adv41-fuzz-target.bin"


@dataclass
class Outcome:
    ok: bool
    exception_func: str | None = None
    fingerprint: str | None = None
    payload: bytes = b""
    crashed: bool = False
    exception_type: str | None = None
    traceback_funcs: list = field(default_factory=list)


@dataclass
class Crash:
    outcome: Outcome
    payload: bytes
    count: int = 1
    exception_func: str | None = None
    fingerprint: str | None = None
    minimised: bytes = b""


@dataclass
class Campaign:
    triage: list
    kept_for_coverage: int
    crash_count: int
    campaign_seed: int = 0
    budget: int = 0
    coverage: list = None

    def __post_init__(self) -> None:
        if self.coverage is None:
            self.coverage = []


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def execute_tracked(data: bytes) -> Outcome:
    data = bytes(data)
    if b"\xff" in data:
        return Outcome(
            False,
            "_crash_a",
            "crash-a",
            data,
            True,
            exception_type="IndexError",
            traceback_funcs=["execute", "_crash_a"],
        )
    if b"\xfe" in data:
        return Outcome(
            False,
            "_crash_b",
            "crash-b",
            data,
            True,
            exception_type="ValueError",
            traceback_funcs=["execute", "_crash_b"],
        )
    return Outcome(True, None, None, data, False)


def crash_from_outcome(outcome: Outcome) -> Crash:
    mini = minimise(outcome.payload) if not outcome.ok else outcome.payload
    return Crash(outcome, outcome.payload, 1, outcome.exception_func, outcome.fingerprint, mini)


def payload_fingerprint(outcome: Outcome, data: bytes) -> str:
    return sha256_bytes(data)


def triage_crashes(crashes: Iterable[Crash], fingerprint: Callable | None = None, do_minimise: bool = True) -> list[Crash]:
    buckets: dict[str, Crash] = {}
    for c in crashes:
        fp = fingerprint(c.outcome, c.payload) if fingerprint else (c.fingerprint or c.exception_func or "x")
        if fp in buckets:
            buckets[fp].count += 1
        else:
            payload = minimise(c.payload) if do_minimise and not c.outcome.ok else c.payload
            buckets[fp] = Crash(c.outcome, payload, 1, c.exception_func, fp)
    return list(buckets.values())


def minimise(data: bytes, fingerprint: str | None = None) -> bytes:
    cur = bytes(data)
    changed = True
    while changed and len(cur) > 1:
        changed = False
        for i in range(len(cur)):
            cand = cur[:i] + cur[i + 1 :]
            o = execute_tracked(cand)
            if not o.ok and o.exception_func == execute_tracked(cur).exception_func:
                cur = cand
                changed = True
                break
    return cur


def minimise_identity(data: bytes, fingerprint: str | None = None) -> bytes:
    return bytes(data)


def materialise(recipe: dict[str, Any]) -> bytes:
    p = recipe.get("payload")
    if isinstance(p, str):
        return p.encode("utf-8")
    return bytes(p or b"")


def committed_corpus(path: str | Path | None = None) -> list[dict[str, Any]]:
    if path and Path(path).is_file():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return [{"id": r["id"], "sha256": sha256_bytes(r["payload"])} for r in SEED_RECIPES]


def run_campaign(*, campaign_seed: int = 0, budget: int = 32) -> Campaign:
    rng = (campaign_seed * 1103515245 + 12345) & 0x7FFFFFFF
    payloads = [materialise(r) for r in SEED_RECIPES]
    for i in range(max(0, budget - len(payloads))):
        rng = (rng * 1103515245 + 12345) & 0x7FFFFFFF
        if rng % 3 == 0:
            payloads.append(b"x" * (i % 5) + b"\xff")
        elif rng % 3 == 1:
            payloads.append(b"y" + b"\xfe")
        else:
            payloads.append(b"ok-%d" % i)
    outcomes = [execute_tracked(p) for p in payloads]
    crashes = [crash_from_outcome(o) for o in outcomes if not o.ok]
    tri = triage_crashes(crashes)
    kept = sum(1 for o in outcomes if o.ok)
    coverage = [p for p, o in zip(payloads, outcomes) if o.ok]
    return Campaign(tri, kept, len(crashes), campaign_seed=campaign_seed, budget=budget, coverage=coverage)
