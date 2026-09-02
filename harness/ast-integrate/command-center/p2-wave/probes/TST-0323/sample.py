#!/usr/bin/env python3
"""Seeded stratified draw. Same (seed, population, stratum) => identical ids."""
from __future__ import annotations

import hashlib
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import adjudicate as A  # noqa: E402
import strata as S  # noqa: E402
import wilson as W  # noqa: E402


def stratum_seed(frame_seed: int, stratum_id: str) -> int:
    blob = f"{frame_seed}|{stratum_id}".encode("utf-8")
    return int(hashlib.sha256(blob).hexdigest()[:16], 16)


def draw_ids(population_ids: list[str], n: int, frame_seed: int, stratum_id: str) -> list[str]:
    ordered = sorted(population_ids)
    if n > len(ordered):
        raise ValueError(f"n={n} exceeds population {len(ordered)} in {stratum_id}")
    rng = random.Random(stratum_seed(frame_seed, stratum_id))
    shuffled = list(ordered)
    rng.shuffle(shuffled)
    return shuffled[:n]


def draw_frame(rows: list[dict], n_per_stratum: int, frame_seed: int) -> dict:
    part = S.partition(rows)
    if not part["ok"]:
        raise ValueError(f"population is not a 2x2 partition: {part}")
    sampled_ids_by: dict[str, list[str]] = {}
    sampled_rows: list[dict] = []
    by_id = {str(r["case_id"]): r for r in rows}
    for sid in S.STRATA:
        pop_ids = [str(r["case_id"]) for r in part["buckets"][sid]]
        take = draw_ids(pop_ids, n_per_stratum, frame_seed, sid)
        sampled_ids_by[sid] = take
        sampled_rows.extend(by_id[i] for i in take)
    return {
        "n_per_stratum": n_per_stratum,
        "partition": {
            "ok": part["ok"],
            "counts": part["counts"],
            "n": part["n"],
            "sum_equals_n": part["sum_equals_n"],
        },
        "sampled_ids_by_stratum": sampled_ids_by,
        "sampled_rows": sampled_rows,
        "seed": frame_seed,
        "strata": list(S.STRATA),
    }


def stratum_rates(sampled_ids_by: dict[str, list[str]], by_id: dict[str, dict]) -> list[dict]:
    out = []
    for sid in S.STRATA:
        ids = sampled_ids_by[sid]
        rows = [by_id[i] for i in ids]
        counts = A.error_counts(rows)
        interval = W.wilson_interval(counts["k"], counts["n"]) if counts["defined"] else W.wilson_interval(0, 0)
        out.append(
            {
                "stratum_id": sid,
                "sampled_case_ids": ids,
                "k": counts["k"],
                "n": counts["n"],
                "n_blocked": counts["n_blocked"],
                "rate": counts["rate"],
                "defined": counts["defined"],
                "interval": interval,
            }
        )
    return out
