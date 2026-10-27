"""429 vs 529 storm scheduler: arrival-rate policy is not vendor-overload policy.

429 (our arrival rate) lengthens the admit gap and therefore reduces measured
wave-2 arrival rate. 529 (vendor overload / their capacity) retries the
affected unit without shrinking the simultaneous-concurrency ceiling; siblings
continue and logical count stays independent of that ceiling.

This module is the live policy under test for TST-0139. Bucket B07 is a catalog
token, not a dispatcher module on this worktree. measure_rate.py meters a
register-gate fire rate, not HTTP arrivals, and is not the meter here.
"""
from __future__ import annotations

import ast
import inspect
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Iterable

CLASS_OK = "ok"
CLASS_ARRIVAL = "arrival-rate"
CLASS_VENDOR = "vendor-overload"
CLASS_OTHER = "other"

BASE_GAP = 1.0
THROTTLE_GAP = 16.0
DEFAULT_CEILING = 4
DEFAULT_N_UNITS = 8
SERVICE_TIME = 10.0
WAVE_N = 4
ClassifyFn = Callable[[int], "Policy"]


@dataclass(frozen=True)
class Policy:
    classification: str
    arrival_gap: float
    reduce_arrival_rate: bool
    reduce_concurrency: bool
    retry: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "arrival_gap": self.arrival_gap,
            "reduce_arrival_rate": self.reduce_arrival_rate,
            "reduce_concurrency": self.reduce_concurrency,
            "retry": self.retry,
        }


POLICY_OK = Policy(
    classification=CLASS_OK,
    arrival_gap=BASE_GAP,
    reduce_arrival_rate=False,
    reduce_concurrency=False,
    retry=False,
)
POLICY_429 = Policy(
    classification=CLASS_ARRIVAL,
    arrival_gap=THROTTLE_GAP,
    reduce_arrival_rate=True,
    reduce_concurrency=False,
    retry=True,
)
POLICY_529 = Policy(
    classification=CLASS_VENDOR,
    arrival_gap=BASE_GAP,
    reduce_arrival_rate=False,
    reduce_concurrency=False,
    retry=True,
)
POLICY_OTHER = Policy(
    classification=CLASS_OTHER,
    arrival_gap=BASE_GAP,
    reduce_arrival_rate=False,
    reduce_concurrency=False,
    retry=False,
)


def classify(status: int) -> Policy:
    """Map an HTTP status onto a policy. 429 and 529 MUST be distinct Eq branches."""
    if status == 429:
        return POLICY_429
    if status == 529:
        return POLICY_529
    if status == 200:
        return POLICY_OK
    return POLICY_OTHER


def classify_mislabel_529_as_429(status: int) -> Policy:
    """Known-broken mutant: 529 is treated as our arrival-rate 429."""
    if status == 529:
        return POLICY_429
    return classify(status)


def classify_identical_throttle(status: int) -> Policy:
    """Known-broken mutant: 429 and 529 both apply the 429 throttle."""
    if status == 429:
        return POLICY_429
    if status == 529:
        return POLICY_429
    return classify(status)


def _ints_from_expr(node: ast.AST) -> list[int]:
    out: list[int] = []
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        out.append(node.value)
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        out.extend([-n for n in _ints_from_expr(node.operand)])
    elif isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        for elt in node.elts:
            out.extend(_ints_from_expr(elt))
    return out


def classify_branches_are_distinct() -> dict[str, Any]:
    """AST-scan classify() for separate Eq 429 / Eq 529, not `in (429, 529)`."""
    src = inspect.getsource(classify)
    tree = ast.parse(src)
    eq_429 = False
    eq_529 = False
    in_tuple_both = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        nums: list[int] = []
        nums.extend(_ints_from_expr(node.left))
        for comp in node.comparators:
            nums.extend(_ints_from_expr(comp))
        if any(isinstance(op, ast.Eq) for op in node.ops):
            if 429 in nums:
                eq_429 = True
            if 529 in nums:
                eq_529 = True
        if any(isinstance(op, ast.In) for op in node.ops):
            if 429 in nums and 529 in nums:
                in_tuple_both = True
    return {
        "eq_429": eq_429,
        "eq_529": eq_529,
        "in_tuple_both": in_tuple_both,
        "pass": bool(eq_429 and eq_529 and not in_tuple_both),
    }


def _rate_from_times(times: Iterable[float], fallback_gap: float) -> float:
    seq = sorted(float(t) for t in times)
    if len(seq) >= 2:
        gaps = [seq[i + 1] - seq[i] for i in range(len(seq) - 1)]
        mean = sum(gaps) / len(gaps)
        if mean > 0:
            return 1.0 / mean
    if fallback_gap > 0:
        return 1.0 / fallback_gap
    return 0.0


def _apply_policy(policy: Policy, gap: float, ceiling: int) -> tuple[float, int, bool]:
    """Return (gap, ceiling, concurrency_reduced_this_step)."""
    reduced = False
    if policy.reduce_arrival_rate:
        gap = float(policy.arrival_gap)
    if policy.reduce_concurrency:
        nxt = max(1, int(ceiling) - 1)
        reduced = nxt < ceiling
        ceiling = nxt
    return gap, ceiling, reduced


def two_wave_storm(
    storm_status: int,
    classify_fn: ClassifyFn | None = None,
    *,
    wave_n: int = WAVE_N,
    base_gap: float = BASE_GAP,
    ceiling: int = DEFAULT_CEILING,
) -> dict[str, Any]:
    """Two sequential waves. Wave-1 first attempts receive storm_status.

    Wave-2 is admitted under the post-storm gap so a 429 throttle is visible
    as a rate drop and a 529 is visible as an unchanged rate.
    """
    fn = classify_fn or classify
    gap = float(base_gap)
    ceil = int(ceiling)
    start_ceil = ceil
    t = 0.0
    ledger: list[dict[str, Any]] = []
    retries: list[str] = []
    wave_first_times: dict[int, list[float]] = {1: [], 2: []}
    concurrency_reduced = False

    def emit(
        unit_id: str,
        wave: int,
        attempt: int,
        status: int,
        at: float,
    ) -> Policy:
        policy = fn(int(status))
        ledger.append(
            {
                "unit_id": unit_id,
                "wave": wave,
                "attempt": attempt,
                "http_status": int(status),
                "classification": policy.classification,
                "t": at,
            }
        )
        return policy

    # Wave 1: first attempts stay on the base gap. Policy is applied after
    # the storm is observed so the wave-1 meter is not itself the throttle.
    storm_policy: Policy | None = None
    for i in range(wave_n):
        uid = f"W1-{i}"
        wave_first_times[1].append(t)
        policy = emit(uid, 1, 1, storm_status, t)
        storm_policy = policy
        if policy.retry:
            retries.append(uid)
        t += base_gap

    if storm_policy is not None:
        gap, ceil, reduced = _apply_policy(storm_policy, gap, ceil)
        concurrency_reduced = concurrency_reduced or reduced
    gap_after_wave1 = gap

    # Retries of wave-1 units succeed (200) without changing the post-storm gap.
    retry_t = t + gap
    for uid in list(retries):
        emit(uid, 1, 2, 200, retry_t)
        retry_t += gap

    # Wave 2 admitted at the (possibly throttled) gap; healthy 200s.
    t = retry_t
    for i in range(wave_n):
        uid = f"W2-{i}"
        wave_first_times[2].append(t)
        emit(uid, 2, 1, 200, t)
        t += gap

    wave1_rate = _rate_from_times(wave_first_times[1], base_gap)
    wave2_rate = _rate_from_times(wave_first_times[2], gap_after_wave1)
    rate_reduced = wave2_rate < wave1_rate - 1e-12
    return {
        "storm_status": int(storm_status),
        "wave1_rate": wave1_rate,
        "wave2_rate": wave2_rate,
        "gap_after": gap_after_wave1,
        "rate_reduced": rate_reduced,
        "concurrency_reduced": concurrency_reduced or ceil < start_ceil,
        "retries": list(retries),
        "ledger": ledger,
        "ceiling_start": start_ceil,
        "ceiling_end": ceil,
    }


def event_storm(
    storm_status: int = 529,
    classify_fn: ClassifyFn | None = None,
    *,
    n_units: int = DEFAULT_N_UNITS,
    ceiling: int = DEFAULT_CEILING,
    service_time: float = SERVICE_TIME,
    base_gap: float = BASE_GAP,
) -> dict[str, Any]:
    """Discrete-event 529/429 storm with independent logical vs simultaneous counts.

    New units are preferred over retries (siblings continue). A 529/429 on
    attempt 1 requeues the unit; attempt 2 is 200. The simultaneous ceiling is
    the only cap 529 is forbidden to shrink.
    """
    fn = classify_fn or classify
    gap = float(base_gap)
    ceil = int(ceiling)
    start_ceil = ceil
    now = 0.0
    next_admit = 0.0
    new_q: Deque[str] = deque(f"U{i}" for i in range(n_units))
    retry_q: Deque[str] = deque()
    inflight: list[dict[str, Any]] = []
    attempts: dict[str, int] = {}
    samples: list[dict[str, Any]] = []
    retry_count = 0
    siblings_continued = False
    pending_retry: set[str] = set()
    done: set[str] = set()
    concurrency_reduced = False
    max_inflight = 0
    min_ceiling = ceil

    def remaining() -> int:
        return n_units - len(done)

    def snap(tag: str) -> None:
        nonlocal max_inflight, min_ceiling
        max_inflight = max(max_inflight, len(inflight))
        min_ceiling = min(min_ceiling, ceil)
        samples.append(
            {
                "t": now,
                "tag": tag,
                "inflight": len(inflight),
                "ceiling": ceil,
                "gap": gap,
                "logical_count": n_units,
                "logical_remaining": remaining(),
            }
        )

    def try_admit() -> bool:
        nonlocal next_admit, retry_count, siblings_continued, now
        if now + 1e-12 < next_admit:
            return False
        if len(inflight) >= ceil:
            return False
        kind = None
        uid = None
        if new_q:
            uid = new_q.popleft()
            kind = "new"
            if pending_retry:
                siblings_continued = True
        elif retry_q:
            uid = retry_q.popleft()
            pending_retry.discard(uid)
            kind = "retry"
            retry_count += 1
        else:
            return False
        attempts[uid] = attempts.get(uid, 0) + 1
        inflight.append(
            {
                "unit_id": uid,
                "finish": now + service_time,
                "attempt": attempts[uid],
            }
        )
        next_admit = now + gap
        snap(f"admit_{kind}:{uid}")
        return True

    def complete_due() -> bool:
        nonlocal gap, ceil, concurrency_reduced, now
        due = [j for j in inflight if j["finish"] <= now + 1e-12]
        if not due:
            return False
        due.sort(key=lambda j: (j["finish"], j["unit_id"]))
        job = due[0]
        now = float(job["finish"])
        inflight.remove(job)
        uid = str(job["unit_id"])
        attempt = int(job["attempt"])
        status = int(storm_status) if attempt == 1 else 200
        policy = fn(status)
        gap, ceil, reduced = _apply_policy(policy, gap, ceil)
        concurrency_reduced = concurrency_reduced or reduced
        snap(f"complete:{uid}:{status}")
        if status == 200:
            done.add(uid)
        elif policy.retry:
            retry_q.append(uid)
            pending_retry.add(uid)
        return True

    # Admit as soon as a slot and the gap allow; complete when a job finishes.
    while True:
        queued = bool(new_q or retry_q)
        next_fin = min((j["finish"] for j in inflight), default=None)
        can_slot = queued and len(inflight) < ceil
        next_ad = max(now, next_admit) if can_slot else None
        if next_fin is None and next_ad is None:
            break
        if next_ad is None or (next_fin is not None and next_fin <= next_ad + 1e-12):
            now = float(next_fin)
            if not complete_due():
                break
            continue
        now = float(next_ad)
        if not try_admit():
            break

    ceiling_held = min_ceiling == start_ceil and not concurrency_reduced
    return {
        "storm_status": int(storm_status),
        "logical_count": n_units,
        "simultaneous_ceiling": start_ceil,
        "min_ceiling": min_ceiling,
        "max_inflight": max_inflight,
        "ceiling_held": ceiling_held,
        "retry_count": retry_count,
        "siblings_continued": siblings_continued,
        "concurrency_reduced": concurrency_reduced or min_ceiling < start_ceil,
        "samples": samples,
        "gap_after": gap,
    }


def both_states() -> dict[str, Any]:
    storm_429 = two_wave_storm(429)
    storm_529 = two_wave_storm(529)
    ident_429 = two_wave_storm(429, classify_identical_throttle)
    ident_529 = two_wave_storm(529, classify_identical_throttle)
    concurrency_529 = event_storm(529)
    diverged = bool(storm_429["rate_reduced"] and not storm_529["rate_reduced"])
    identical_mutant_collapses = bool(
        ident_429["rate_reduced"] and ident_529["rate_reduced"]
    )
    conc_ok = (
        concurrency_529["ceiling_held"]
        and not concurrency_529["concurrency_reduced"]
        and concurrency_529["retry_count"] >= 1
        and concurrency_529["siblings_continued"]
        and concurrency_529["logical_count"] > concurrency_529["simultaneous_ceiling"]
        and concurrency_529["max_inflight"] >= 1
    )
    return {
        "pass": bool(diverged and identical_mutant_collapses and conc_ok),
        "diverged": diverged,
        "identical_mutant_collapses": identical_mutant_collapses,
        "storm_429": storm_429,
        "storm_529": storm_529,
        "concurrency_529": concurrency_529,
        "identical_429": ident_429,
        "identical_529": ident_529,
    }


def _recount(ledger: list[dict[str, Any]]) -> list[dict[str, Any]]:
    table = {429: CLASS_ARRIVAL, 529: CLASS_VENDOR, 200: CLASS_OK}
    rows = []
    for item in ledger:
        status = int(item.get("http_status") or -1)
        expected = table.get(status, CLASS_OTHER)
        observed = str(item.get("classification") or "")
        rows.append(
            {
                "unit_id": item.get("unit_id"),
                "http_status": status,
                "reviewer_class": expected,
                "ledger_class": observed,
                "agree": expected == observed,
            }
        )
    return rows


def mislabel_is_detected() -> dict[str, Any]:
    live = two_wave_storm(529)
    mutant = two_wave_storm(529, classify_mislabel_529_as_429)
    live_first = [r for r in live["ledger"] if r.get("wave") == 1 and r.get("attempt") == 1]
    mutant_first = [
        r for r in mutant["ledger"] if r.get("wave") == 1 and r.get("attempt") == 1
    ]
    live_review = _recount(live_first)
    mutant_review = _recount(mutant_first)
    live_ok = bool(live_review) and all(r["agree"] for r in live_review)
    mutant_visible = bool(mutant_review) and (not all(r["agree"] for r in mutant_review))
    fired = bool(mutant["rate_reduced"] and live["gap_after"] < mutant["gap_after"])
    silent = not bool(live["rate_reduced"])
    return {
        "pass": bool(live_ok and mutant_visible and fired and silent),
        "live_rate_reduced": live["rate_reduced"],
        "mutant_rate_reduced": mutant["rate_reduced"],
        "live_gap_after": live["gap_after"],
        "mutant_gap_after": mutant["gap_after"],
        "live_review": live_review,
        "mutant_review": mutant_review,
        "live": live,
        "mutant": mutant,
    }
