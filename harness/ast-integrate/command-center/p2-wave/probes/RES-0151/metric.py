#!/usr/bin/env python3
"""Evidence-saturation stopping metric: rolling mean of new distinct keys/source."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mechanism import mechanism_key

HERE = Path(__file__).resolve().parent
PREREG_PATH = HERE / "threshold_prereg.json"


def load_prereg() -> dict[str, Any]:
    doc = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    if doc.get("recorded_before_any_replay_or_control") is not True:
        raise RuntimeError("preregistration was not frozen before scoring")
    for key in ("window", "floor", "min_sources", "early_max_index"):
        if key not in doc:
            raise RuntimeError(f"prereg missing {key}")
    return doc


def fire_index_from_yields(
    yields: list[int],
    window: int,
    floor: float,
    min_sources: int,
) -> int | None:
    """Return 1-based fire index, or None if the detector stays silent."""
    n = len(yields)
    start = max(int(min_sources), int(window))
    for t in range(start, n + 1):
        chunk = yields[t - window : t]
        if len(chunk) < window:
            continue
        mean = sum(chunk) / float(window)
        if mean <= float(floor) + 1e-12:
            return t
    return None


def score_run_string_equality(
    sources: list[dict[str, Any]], prereg: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Foil: treat stripped claim text as the identity (string equality)."""
    if prereg is None:
        prereg = load_prereg()
    seen: set[str] = set()
    yields: list[int] = []
    for src in sources:
        new = 0
        for claim in src.get("claims") or []:
            key = str(claim.get("text") or "").strip()
            if not key:
                continue
            if key not in seen:
                seen.add(key)
                new += 1
        yields.append(new)
    fire = fire_index_from_yields(
        yields,
        int(prereg["window"]),
        float(prereg["floor"]),
        int(prereg["min_sources"]),
    )
    return {
        "yields": yields,
        "fire_index": fire,
        "fired": fire is not None,
        "total_distinct": len(seen),
        "distinctness": "string-equality",
    }


def score_run(sources: list[dict[str, Any]], prereg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Score an ordered source list. Each source has claims: [{text, ...}]."""
    if prereg is None:
        prereg = load_prereg()
    window = int(prereg["window"])
    floor = float(prereg["floor"])
    min_sources = int(prereg["min_sources"])
    early_max = int(prereg["early_max_index"])

    seen: set[str] = set()
    first_seen_at: dict[str, int] = {}
    yields: list[int] = []
    per_source: list[dict[str, Any]] = []

    for i, src in enumerate(sources, 1):
        new_keys: list[str] = []
        keys_here: list[str] = []
        for claim in src.get("claims") or []:
            text = str(claim.get("text") or "").strip()
            if not text:
                continue
            key = mechanism_key(text)
            keys_here.append(key)
            if key not in seen:
                seen.add(key)
                first_seen_at[key] = i
                new_keys.append(key)
        yields.append(len(new_keys))
        row = {
            "index": i,
            "source_id": src.get("source_id"),
            "heading": src.get("heading"),
            "n_claims": len(src.get("claims") or []),
            "n_new": len(new_keys),
            "new_keys": new_keys,
            "keys": keys_here,
        }
        for field in (
            "resolved_url",
            "fetch_timestamp",
            "sha256",
            "path",
            "sherman_kent_band",
        ):
            if field in src:
                row[field] = src[field]
        per_source.append(row)

    fire = fire_index_from_yields(yields, window, floor, min_sources)
    total = len(seen)
    if fire is None:
        miss_keys: list[str] | None = None
        miss_count: int | None = None
        miss_rate: float | None = None
    else:
        miss_keys = [k for k, t in first_seen_at.items() if t > fire]
        miss_count = len(miss_keys)
        miss_rate = (miss_count / float(total)) if total else 0.0

    rolling: list[float | None] = []
    for t in range(1, len(yields) + 1):
        if t < window:
            rolling.append(None)
        else:
            chunk = yields[t - window : t]
            rolling.append(sum(chunk) / float(window))

    return {
        "n_sources": len(sources),
        "yields": yields,
        "rolling_mean": rolling,
        "fire_index": fire,
        "fired": fire is not None,
        "early": fire is not None and fire <= early_max,
        "total_distinct": total,
        "miss_count": miss_count,
        "miss_rate": miss_rate,
        "miss_keys": miss_keys,
        "first_seen_at": first_seen_at,
        "per_source": per_source,
        "window": window,
        "floor": floor,
        "min_sources": min_sources,
    }


def token_counter_fire(sources: list[dict[str, Any]], budget: int) -> int | None:
    """Foil: stop when cumulative claim tokens reach a budget (ignores distinctness)."""
    total = 0
    for i, src in enumerate(sources, 1):
        for claim in src.get("claims") or []:
            total += len(str(claim.get("text") or "").split())
        if total >= int(budget):
            return i
    return None
