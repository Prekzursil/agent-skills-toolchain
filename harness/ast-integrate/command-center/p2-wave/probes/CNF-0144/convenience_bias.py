#!/usr/bin/env python3
"""Convenience-bias probe for CNF-0144.

Correlate event-log confirmation cost against P(drawn and completed).
Re-weight stratum rates when the correlation is material.
A sample that quietly skips expensive claims measures the easy half.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from event_costs import (
    extract_costs,
    record_self_report_seconds,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
FRAME_PATH = FIXTURES / "sampling-frame.json"
EVENTS_PATH = FIXTURES / "EVENTS.jsonl"
RECORDS_PATH = FIXTURES / "confirmation-records.json"
THRESHOLD_PATH = HERE / "pre_registered.json"

LIVE_FRAME = REPO / "command-center" / "receipts" / "CNF-0137.json"
LIVE_EVENTS = REPO / "command-center" / "events" / "EVENTS.jsonl"

N_CLAIMS = 60
PLANTED_DROP_FRACTION = 0.20
ALPHA = 0.05
MATERIAL_ABS_R = 0.30
PERMUTATIONS = 4000
PERM_SEED = 144
FRAME_SEED = 144
Z95 = 1.959963984540054

STRATA = (
    "P2|alpha|anthropic|invariant",
    "P2|beta|anthropic|invariant",
    "P3|alpha|anthropic|invariant",
)


@dataclass
class ClaimRow:
    claim_id: str
    stratum_id: str
    draw_probability: float
    drawn: bool
    completed: bool
    wall_clock_seconds: float | None
    substrate: str | None
    tool_count: int
    verdict: str | None
    inclusion: float
    self_reported_seconds: float | None = None
    cost_source: str = "event-log"


@dataclass
class Correlation:
    method: str
    r: float | None
    n: int
    p_value: float | None
    ci95: tuple[float | None, float | None]
    undefined_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        lo, hi = self.ci95
        return {
            "method": self.method,
            "r": self.r,
            "n": self.n,
            "p_value": self.p_value,
            "ci95": {"low": lo, "high": hi},
            "undefined_reason": self.undefined_reason,
        }


def pearson_r(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n != len(ys) or n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = 0.0
    dx = 0.0
    dy = 0.0
    for x, y in zip(xs, ys):
        vx = x - mx
        vy = y - my
        num += vx * vy
        dx += vx * vx
        dy += vy * vy
    if dx <= 0.0 or dy <= 0.0:
        return None
    return num / math.sqrt(dx * dy)


def ranks(values: list[float]) -> list[float]:
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    out = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def fisher_ci(r: float, n: int) -> tuple[float | None, float | None]:
    if n < 4 or abs(r) >= 1.0:
        return None, None
    z = math.atanh(max(min(r, 0.999999), -0.999999))
    se = 1.0 / math.sqrt(n - 3)
    return math.tanh(z - Z95 * se), math.tanh(z + Z95 * se)


def permutation_p(
    xs: list[float], ys: list[float], r_obs: float, n_perm: int, seed: int
) -> float:
    rng = random.Random(seed)
    y = list(ys)
    hits = 0
    abs_obs = abs(r_obs)
    for _ in range(n_perm):
        rng.shuffle(y)
        r = pearson_r(xs, y)
        if r is None:
            continue
        if abs(r) + 1e-15 >= abs_obs:
            hits += 1
    return (hits + 1) / (n_perm + 1)


def correlate(xs: list[float], ys: list[float], method: str = "pearson") -> Correlation:
    n = len(xs)
    if method == "spearman":
        if n < 3:
            return Correlation(method, None, n, None, (None, None), "n<3")
        r = pearson_r(ranks(xs), ranks(ys))
    else:
        r = pearson_r(xs, ys)
    if r is None:
        return Correlation(
            method,
            None,
            n,
            None,
            (None, None),
            "zero variance in cost or inclusion (correlation undefined)",
        )
    p = permutation_p(xs, ys, r, PERMUTATIONS, PERM_SEED)
    return Correlation(method, r, n, p, fisher_ci(r, n), None)


def convenience_bias_fires(corr: Correlation) -> bool:
    """Material cheap-overrepresentation: negative r, CI excludes 0, |r|>=threshold."""
    if corr.r is None or corr.p_value is None:
        return False
    lo, hi = corr.ci95
    if lo is None or hi is None:
        return False
    return (
        corr.r <= -MATERIAL_ABS_R
        and corr.p_value < ALPHA
        and hi < 0.0
    )


def cost_distribution(rows: list[ClaimRow], predicate) -> dict[str, float | int | None]:
    vals = [
        r.wall_clock_seconds
        for r in rows
        if predicate(r) and r.wall_clock_seconds is not None
    ]
    if not vals:
        return {"n": 0, "min": None, "p50": None, "mean": None, "p90": None, "max": None}
    s = sorted(vals)

    def pct(p: float) -> float:
        if len(s) == 1:
            return s[0]
        idx = min(len(s) - 1, max(0, int(round(p * (len(s) - 1)))))
        return s[idx]

    return {
        "n": len(s),
        "min": s[0],
        "p50": pct(0.5),
        "mean": sum(s) / len(s),
        "p90": pct(0.9),
        "max": s[-1],
    }


def drop_expensive_completions(
    rows: list[ClaimRow], fraction: float = PLANTED_DROP_FRACTION
) -> list[ClaimRow]:
    completed = [r for r in rows if r.completed and r.wall_clock_seconds is not None]
    k = max(1, int(len(completed) * fraction))
    drop_ids = {
        r.claim_id
        for r in sorted(
            completed, key=lambda r: r.wall_clock_seconds or 0.0, reverse=True
        )[:k]
    }
    out: list[ClaimRow] = []
    for r in rows:
        if r.claim_id not in drop_ids:
            out.append(r)
            continue
        out.append(
            ClaimRow(
                claim_id=r.claim_id,
                stratum_id=r.stratum_id,
                draw_probability=r.draw_probability,
                drawn=r.drawn,
                completed=False,
                wall_clock_seconds=r.wall_clock_seconds,
                substrate=r.substrate,
                tool_count=r.tool_count,
                verdict=None,
                inclusion=0.0,
                self_reported_seconds=r.self_reported_seconds,
                cost_source=r.cost_source,
            )
        )
    return out


def tercile_index(value: float, cuts: tuple[float, float]) -> int:
    if value <= cuts[0]:
        return 0
    if value <= cuts[1]:
        return 1
    return 2


def population_tercile_cuts(values: list[float]) -> tuple[float, float]:
    s = sorted(values)
    n = len(s)
    if n < 3:
        mid = s[n // 2]
        return mid, mid
    return s[max(0, n // 3 - 1)], s[max(0, (2 * n) // 3 - 1)]


def stratum_rates(
    rows: list[ClaimRow], weights: dict[str, float] | None = None
) -> dict[str, float | None]:
    num: dict[str, float] = {}
    den: dict[str, float] = {}
    for r in rows:
        if not r.completed:
            continue
        w = 1.0 if weights is None else float(weights.get(r.claim_id, 0.0))
        den[r.stratum_id] = den.get(r.stratum_id, 0.0) + w
        if r.verdict == "CONFIRMED":
            num[r.stratum_id] = num.get(r.stratum_id, 0.0) + w
    out: dict[str, float | None] = {}
    for sid in sorted(set(num) | set(den)):
        d = den.get(sid, 0.0)
        out[sid] = (num.get(sid, 0.0) / d) if d > 0.0 else None
    return out


def inverse_tercile_weights(rows: list[ClaimRow]) -> dict[str, float]:
    """Horvitz–Thompson-style weights from completion rate within cost tercile."""
    drawn_costs = [
        r.wall_clock_seconds
        for r in rows
        if r.drawn and r.wall_clock_seconds is not None
    ]
    if len(drawn_costs) < 3:
        return {r.claim_id: 1.0 for r in rows if r.completed}
    cuts = population_tercile_cuts(drawn_costs)
    drawn_n = [0, 0, 0]
    done_n = [0, 0, 0]
    idx_of: dict[str, int] = {}
    for r in rows:
        if not r.drawn or r.wall_clock_seconds is None:
            continue
        t = tercile_index(r.wall_clock_seconds, cuts)
        idx_of[r.claim_id] = t
        drawn_n[t] += 1
        if r.completed:
            done_n[t] += 1
    pi = []
    for t in range(3):
        pi.append((done_n[t] / drawn_n[t]) if drawn_n[t] else 0.0)
    weights: dict[str, float] = {}
    for r in rows:
        if not r.completed:
            continue
        t = idx_of.get(r.claim_id)
        if t is None or pi[t] <= 0.0:
            weights[r.claim_id] = 1.0
        else:
            weights[r.claim_id] = 1.0 / pi[t]
    return weights


def reweighting_moves_a_stratum(rows: list[ClaimRow], min_abs: float = 1e-6) -> dict[str, Any]:
    unweighted = stratum_rates(rows, None)
    weights = inverse_tercile_weights(rows)
    weighted = stratum_rates(rows, weights)
    moved: list[dict[str, Any]] = []
    for sid in sorted(set(unweighted) | set(weighted)):
        a = unweighted.get(sid)
        b = weighted.get(sid)
        if a is None or b is None:
            continue
        delta = b - a
        if abs(delta) > min_abs:
            moved.append(
                {
                    "stratum_id": sid,
                    "unweighted": a,
                    "weighted": b,
                    "delta": delta,
                }
            )
    return {
        "unweighted": unweighted,
        "weighted": weighted,
        "moved": moved,
        "inert": len(moved) == 0,
    }


def analyze(rows: list[ClaimRow]) -> dict[str, Any]:
    usable = [
        r
        for r in rows
        if r.drawn and r.wall_clock_seconds is not None
    ]
    xs = [float(r.wall_clock_seconds or 0.0) for r in usable]
    ys = [float(r.inclusion) for r in usable]
    pearson = correlate(xs, ys, "pearson")
    spearman = correlate(xs, ys, "spearman")
    fires = convenience_bias_fires(pearson)
    return {
        "n": len(usable),
        "pearson": pearson.as_dict(),
        "spearman": spearman.as_dict(),
        "fires": fires,
        "silent": not fires,
        "cost_distribution": {
            "drawn": cost_distribution(rows, lambda r: r.drawn),
            "completed": cost_distribution(rows, lambda r: r.completed),
            "incomplete": cost_distribution(
                rows, lambda r: r.drawn and not r.completed
            ),
        },
        "duration_table": [
            {
                "claim_id": r.claim_id,
                "stratum_id": r.stratum_id,
                "draw_probability": r.draw_probability,
                "completed": r.completed,
                "inclusion": r.inclusion,
                "wall_clock_seconds": r.wall_clock_seconds,
                "substrate": r.substrate,
                "tool_count": r.tool_count,
                "verdict": r.verdict,
                "cost_source": r.cost_source,
            }
            for r in usable
        ],
    }


def pre_registered() -> dict[str, Any]:
    return {
        "alpha": ALPHA,
        "material_abs_r": MATERIAL_ABS_R,
        "convenience_bias_sign": "negative_cost_vs_inclusion",
        "planted_drop_fraction": PLANTED_DROP_FRACTION,
        "permutations": PERMUTATIONS,
        "permutation_seed": PERM_SEED,
        "frame_seed": FRAME_SEED,
        "recorded_before_measurement": True,
        "no_retry": (
            "No redraw until the correlation looks acceptable. "
            "If the computation errors, fix it and re-derive from this frozen frame."
        ),
    }


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_unbiased_world() -> dict[str, Any]:
    """Balanced draw-probability vs cost so unbiased correlation stays near 0."""
    base = datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
    claims: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    # Even/odd cost ranks split across high and low draw groups equally.
    high_draw_slots = [i for i in range(N_CLAIMS) if (i // 3) % 2 == 0]
    low_draw_slots = [i for i in range(N_CLAIMS) if (i // 3) % 2 == 1]
    cost_ranks = list(range(N_CLAIMS))
    high_costs = cost_ranks[0::2]
    low_costs = cost_ranks[1::2]
    slot_cost: dict[int, int] = {}
    for slot, rank in zip(high_draw_slots, high_costs):
        slot_cost[slot] = rank
    for slot, rank in zip(low_draw_slots, low_costs):
        slot_cost[slot] = rank
    for i in range(N_CLAIMS):
        claim_id = f"CLM-{i:04d}"
        stratum = STRATA[i % 3]
        draw_p = 1.0 if (i // 3) % 2 == 0 else 0.40
        rank = slot_cost[i]
        wall = 40.0 + 14.0 * rank
        tools = 1 + rank // 10
        substrate = "local-parallel" if rank < 30 else "worktree-isolated"
        verdict = "CONFIRMED" if wall < 400.0 else "REFUTED"
        dispatch = base + timedelta(seconds=i * 3600)
        completion = dispatch + timedelta(seconds=wall)
        inverted = 2000.0 - wall
        claims.append(
            {
                "claim_id": claim_id,
                "stratum_id": stratum,
                "severity": stratum.split("|", 1)[0],
                "draw_probability": draw_p,
                "drawn": True,
            }
        )
        events.append(
            {
                "event": "dispatch",
                "claim_id": claim_id,
                "ts": _iso(dispatch),
                "substrate": substrate,
                "record_id": f"rec-{i:04d}",
            }
        )
        for t in range(tools):
            events.append(
                {
                    "event": "tool_call",
                    "claim_id": claim_id,
                    "ts": _iso(dispatch + timedelta(seconds=t + 1)),
                    "tool": "Read" if t % 2 == 0 else "Grep",
                }
            )
        events.append(
            {
                "event": "completion",
                "claim_id": claim_id,
                "ts": _iso(completion),
                "record_id": f"rec-{i:04d}",
            }
        )
        records.append(
            {
                "claim_id": claim_id,
                "record_id": f"rec-{i:04d}",
                "stratum_id": stratum,
                "verdict": verdict,
                "self_reported_seconds": inverted,
                "self_reported_tool_count": 0,
                "duration_seconds": inverted,
                "note": (
                    "self_reported_seconds is inverted wall-clock. "
                    "CNF-0144 must ignore it."
                ),
            }
        )
    frame = {
        "unit_id": "CNF-0144",
        "role": "frozen-fixture-sampling-frame",
        "n_claims": N_CLAIMS,
        "partition_note": (
            "Fixture frame used because CNF-0137 live frame is absent. "
            "Every fixture claim is drawn; draw_probability still varies."
        ),
        "strata": [
            {
                "stratum_id": s,
                "population": N_CLAIMS // 3,
                "drawn": N_CLAIMS // 3,
            }
            for s in STRATA
        ],
        "claims": claims,
    }
    return {"frame": frame, "events": events, "records": records}


def write_fixtures() -> dict[str, str]:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    world = build_unbiased_world()
    FRAME_PATH.write_text(
        json.dumps(world["frame"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    EVENTS_PATH.write_text(
        "".join(json.dumps(e, sort_keys=True) + "\n" for e in world["events"]),
        encoding="utf-8",
    )
    RECORDS_PATH.write_text(
        json.dumps(world["records"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    THRESHOLD_PATH.write_text(
        json.dumps(pre_registered(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "frame": sha256_file(FRAME_PATH),
        "events": sha256_file(EVENTS_PATH),
        "records": sha256_file(RECORDS_PATH),
        "threshold": sha256_file(THRESHOLD_PATH),
    }


def sha256_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def freeze_identity() -> str:
    payload = "|".join(
        [
            sha256_file(FRAME_PATH),
            sha256_file(EVENTS_PATH),
            sha256_file(RECORDS_PATH),
            sha256_file(THRESHOLD_PATH),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rows_from_disk(
    frame_path: Path = FRAME_PATH,
    events_path: Path = EVENTS_PATH,
    records_path: Path = RECORDS_PATH,
) -> list[ClaimRow]:
    frame = load_json(frame_path)
    records_raw = load_json(records_path)
    rec_by = {str(r["claim_id"]): r for r in records_raw}
    costs = extract_costs(events_path, records_raw)
    rows: list[ClaimRow] = []
    for c in frame["claims"]:
        cid = str(c["claim_id"])
        rec = rec_by.get(cid, {})
        cost = costs.get(cid)
        completed = (
            cost is not None
            and cost.wall_clock_seconds is not None
            and cost.dispatch_ts is not None
            and cost.completion_ts is not None
        )
        draw_p = float(c["draw_probability"])
        drawn = bool(c.get("drawn", True))
        inclusion = draw_p if (drawn and completed) else 0.0
        rows.append(
            ClaimRow(
                claim_id=cid,
                stratum_id=str(c["stratum_id"]),
                draw_probability=draw_p,
                drawn=drawn,
                completed=completed,
                wall_clock_seconds=cost.wall_clock_seconds if cost else None,
                substrate=cost.substrate if cost else None,
                tool_count=cost.tool_count if cost else 0,
                verdict=str(rec["verdict"]) if rec.get("verdict") else None,
                inclusion=inclusion,
                self_reported_seconds=record_self_report_seconds(rec),
                cost_source="event-log",
            )
        )
    return rows


def live_inputs_status() -> dict[str, Any]:
    return {
        "cnf_0137_sampling_frame": {
            "path": str(LIVE_FRAME.relative_to(REPO)).replace("\\", "/"),
            "present": LIVE_FRAME.is_file(),
        },
        "events_jsonl": {
            "path": str(LIVE_EVENTS.relative_to(REPO)).replace("\\", "/"),
            "present": LIVE_EVENTS.is_file(),
        },
        "status": "NOT-CHECKED"
        if not (LIVE_FRAME.is_file() and LIVE_EVENTS.is_file())
        else "CHECKED",
        "named_prerequisite": (
            "CNF-0137 sampling frame; command-center/events/EVENTS.jsonl"
        ),
        "note": (
            "Live confirmation campaign inputs are absent on this worktree. "
            "Published correlation is the frozen fixture sample, not a live "
            "program rate. Missing live inputs are NOT dropped from the "
            "denominator of any published program claim."
        ),
    }


def ensure_fixtures() -> list[ClaimRow]:
    write_fixtures()
    return rows_from_disk()
