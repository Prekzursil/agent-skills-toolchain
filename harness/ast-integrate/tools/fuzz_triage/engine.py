"""Deterministic crash triage (TST-0117).

Seed corpus with per-seed recipes, a seeded havoc campaign, stack-fingerprint
dedup and byte-granularity minimisation. Every function is deterministic for a
given input so a receipt can be replayed byte-for-byte.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable
import hashlib
import json
import random

# Committed seed recipes. Bytes are DERIVED from the recipe (never hand-edited):
# "ascii" seeds are random.Random(rng_seed).randrange(32, 127) streams of the
# stated length; "literal" seeds carry their bytes as hex. None contains the
# planted crash tokens 0xFF / 0xFE.
SEED_RECIPES = (
    {"id": "seed-0001", "kind": "ascii", "length": 20, "origin": "author-planted", "rng_seed": 117001},
    {"id": "seed-0002", "kind": "ascii", "length": 32, "origin": "author-planted", "rng_seed": 117002},
    {"id": "seed-0003", "kind": "ascii", "length": 8, "origin": "author-planted", "rng_seed": 117003},
    {"id": "seed-0004", "kind": "literal", "hex": "4845414445520a626f64792d6f6b", "origin": "author-planted"},
    {"id": "seed-0005", "kind": "literal", "hex": "804142434445464748494a4b4c4d4e4f", "origin": "author-planted"},
)

CRASH_TOKEN_A = b"\xff"  # -> _crash_a (IndexError)
CRASH_TOKEN_B = b"\xfe"  # -> _crash_b (KeyError)

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

    @property
    def exception_type(self) -> str | None:
        return self.outcome.exception_type

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "example_hex": bytes(self.payload).hex(),
            "exception_func": self.exception_func,
            "exception_type": self.outcome.exception_type,
            "fingerprint": self.fingerprint,
            "minimised_hex": bytes(self.minimised).hex(),
            "minimised_nbytes": len(self.minimised),
        }


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "budget": self.budget,
            "campaign_seed": self.campaign_seed,
            "coverage_size": len(self.coverage),
            "crash_count": self.crash_count,
            "kept_for_coverage": self.kept_for_coverage,
            "triage": [e.to_dict() for e in self.triage],
            "triage_count": len(self.triage),
        }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(bytes(data)).hexdigest()


def stack_fingerprint(exception_type: str | None, crash_function: str | None) -> str:
    """Dedup key: sha256(exception_type|crash_function) - payload-independent."""
    return hashlib.sha256(f"{exception_type}|{crash_function}".encode("utf-8")).hexdigest()


def _crash_a(data: bytes) -> None:
    # Planted defect: indexes past the end once the 0xFF marker is present.
    idx = data.index(CRASH_TOKEN_A)
    raise IndexError(f"marker at offset {idx} addresses beyond the buffer")


def _crash_b(data: bytes) -> None:
    # Planted defect: looks up a field that the 0xFE marker never defines.
    raise KeyError("field-after-0xFE")


def _target(data: bytes) -> None:
    if CRASH_TOKEN_A in data:
        _crash_a(data)
    if CRASH_TOKEN_B in data:
        _crash_b(data)


def execute_tracked(data: bytes) -> Outcome:
    data = bytes(data)
    try:
        _target(data)
    except (IndexError, KeyError) as exc:
        tb = exc.__traceback__
        funcs: list[str] = []
        while tb is not None:
            funcs.append(tb.tb_frame.f_code.co_name)
            tb = tb.tb_next
        func = funcs[-1] if funcs else None
        etype = type(exc).__name__
        return Outcome(
            False,
            func,
            stack_fingerprint(etype, func),
            data,
            True,
            exception_type=etype,
            traceback_funcs=funcs,
        )
    return Outcome(True, None, None, data, False)


def crash_from_outcome(outcome: Outcome) -> Crash:
    mini = minimise(outcome.payload) if not outcome.ok else outcome.payload
    return Crash(outcome, outcome.payload, 1, outcome.exception_func, outcome.fingerprint, mini)


def payload_fingerprint(outcome: Outcome, data: bytes) -> str:
    """Negative-control fingerprint: hashes the payload, so padding splits buckets."""
    return sha256_bytes(data)


def triage_crashes(
    crashes: Iterable[Crash],
    fingerprint: Callable | None = None,
    do_minimise: bool = True,
) -> list[Crash]:
    buckets: dict[str, Crash] = {}
    for c in crashes:
        fp = fingerprint(c.outcome, c.payload) if fingerprint else (c.fingerprint or c.exception_func or "x")
        if fp in buckets:
            buckets[fp].count += 1
        else:
            mini = minimise(c.payload, fp) if do_minimise and not c.outcome.ok else bytes(c.payload)
            buckets[fp] = Crash(c.outcome, c.payload, 1, c.exception_func, fp, mini)
    return list(buckets.values())


def minimise(data: bytes, fingerprint: str | None = None) -> bytes:
    """Byte-granularity delete: drop any byte whose removal keeps the fingerprint."""
    cur = bytes(data)
    base = execute_tracked(cur)
    if base.ok:
        return cur
    target_fp = base.fingerprint
    changed = True
    while changed and len(cur) > 1:
        changed = False
        for i in range(len(cur)):
            cand = cur[:i] + cur[i + 1 :]
            o = execute_tracked(cand)
            if not o.ok and o.fingerprint == target_fp:
                cur = cand
                changed = True
                break
    return cur


def minimise_identity(data: bytes, fingerprint: str | None = None) -> bytes:
    """Negative-control minimiser: returns the padded input unchanged."""
    return bytes(data)


def materialise(recipe: dict[str, Any]) -> bytes:
    kind = recipe.get("kind")
    if kind == "ascii":
        rng = random.Random(int(recipe["rng_seed"]))
        return bytes(rng.randrange(32, 127) for _ in range(int(recipe["length"])))
    if kind == "literal":
        return bytes.fromhex(str(recipe["hex"]))
    p = recipe.get("payload")
    if isinstance(p, str):
        return p.encode("utf-8")
    return bytes(p or b"")


def _record(recipe: dict[str, Any], parent_id: str | None = None) -> dict[str, Any]:
    data = materialise(recipe)
    return {
        "id": recipe["id"],
        "origin": recipe.get("origin", "author-planted"),
        "parent_id": parent_id,
        "recipe": dict(recipe),
        "nbytes": len(data),
        "bytes_hex": data.hex(),
        "sha256": sha256_bytes(data),
    }


def committed_corpus(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Seed records (id/sha256/bytes_hex/recipe) derived from SEED_RECIPES.

    With ``path`` naming an existing seeds.json, its rows are re-derived from
    their recipes so a hand-edited bytes_hex can never survive a reload.
    """
    if path and Path(path).is_file():
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        rows = doc.get("seeds") if isinstance(doc, dict) else doc
        return [_record(r["recipe"], r.get("parent_id")) for r in rows]
    return [_record(r) for r in SEED_RECIPES]


def run_campaign(*, campaign_seed: int = 0, budget: int = 32) -> Campaign:
    rng = random.Random(int(campaign_seed))
    seeds = [materialise(r) for r in SEED_RECIPES]
    payloads = list(seeds)
    tokens = (CRASH_TOKEN_A, CRASH_TOKEN_B)
    for _ in range(max(0, budget - len(seeds))):
        base = bytearray(rng.choice(seeds))
        op = rng.randrange(4)
        pos = rng.randrange(len(base) + 1)
        if op == 0:
            # havoc: overwrite one byte with a planted token
            base[min(pos, len(base) - 1)] = tokens[rng.randrange(2)][0]
        elif op == 1:
            # havoc: insert a planted token
            base[pos:pos] = tokens[rng.randrange(2)]
        elif op == 2:
            # havoc: printable byte flip (usually survives -> coverage)
            base[min(pos, len(base) - 1)] = rng.randrange(32, 127)
        else:
            # havoc: splice two seeds
            other = rng.choice(seeds)
            base = bytearray(bytes(base[:pos]) + other[pos:])
        payloads.append(bytes(base))
    outcomes = [execute_tracked(p) for p in payloads]
    crashes = [crash_from_outcome(o) for o in outcomes if not o.ok]
    tri = triage_crashes(crashes)
    coverage: list[bytes] = []
    seen: set[bytes] = set()
    for p, o in zip(payloads, outcomes):
        if o.ok and p not in seen:
            seen.add(p)
            coverage.append(p)
    kept = len(coverage)
    return Campaign(tri, kept, len(crashes), campaign_seed=campaign_seed, budget=budget, coverage=coverage)
