"""In-process IR stage sequencer: the transferable retry+DAG subset.

This is this estate's control plane for the unit: a static DAG, a retry
policy, scripted failures. Same inputs → same stage sequence. It is NOT
Temporal history replay and does not write an event-log file.
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Callable

# Diamond: extract fans out to transform_a and transform_b, both join at load.
NODES = ("extract", "transform_a", "transform_b", "load")
EDGES = (
    ("extract", "transform_a"),
    ("extract", "transform_b"),
    ("transform_a", "load"),
    ("transform_b", "load"),
)

# transform_a fails twice then succeeds. Others succeed first try.
FAIL_UNTIL = {
    "extract": 0,
    "transform_a": 2,
    "transform_b": 0,
    "load": 0,
}

RETRY_POLICY = {
    "max_attempts": 3,
    "backoff_base_seconds": 1,
    "backoff_coefficient": 2.0,
    "jitter": False,
}

EXPECTED_GOOD = (
    "extract:1:ok",
    "transform_a:1:fail",
    "transform_a:2:fail",
    "transform_a:3:ok",
    "transform_b:1:ok",
    "load:1:ok",
)


def backoff_seconds(attempt: int, policy: dict | None = None) -> float:
    policy = policy or RETRY_POLICY
    if policy.get("jitter"):
        raise ValueError("jitter is non-deterministic; refuse")
    base = float(policy["backoff_base_seconds"])
    coef = float(policy["backoff_coefficient"])
    # attempt 1 is the first try (no wait); wait is before attempt n>1
    if attempt <= 1:
        return 0.0
    return base * (coef ** (attempt - 2))


def topo_order(
    nodes: tuple[str, ...] = NODES,
    edges: tuple[tuple[str, str], ...] = EDGES,
    ready_sort: Callable[[list[str]], list[str]] | None = None,
) -> list[str]:
    sort = ready_sort or (lambda xs: sorted(xs))
    incoming: dict[str, int] = {n: 0 for n in nodes}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for a, b in edges:
        outgoing[a].append(b)
        incoming[b] += 1
    ready = deque(sort([n for n, c in incoming.items() if c == 0]))
    order: list[str] = []
    while ready:
        n = ready.popleft()
        order.append(n)
        nxt = sort(outgoing[n])
        for m in nxt:
            incoming[m] -= 1
            if incoming[m] == 0:
                ready.append(m)
        ready = deque(sort(list(ready)))
    if len(order) != len(nodes):
        raise RuntimeError("cycle or missing node")
    return order


def expand_stage(stage_id: str, policy: dict | None = None) -> list[str]:
    policy = policy or RETRY_POLICY
    fail_until = FAIL_UNTIL[stage_id]
    max_attempts = int(policy["max_attempts"])
    seq: list[str] = []
    for attempt in range(1, max_attempts + 1):
        _ = backoff_seconds(attempt, policy)  # recorded, not slept
        if attempt <= fail_until:
            seq.append(f"{stage_id}:{attempt}:fail")
            if attempt == max_attempts:
                break
        else:
            seq.append(f"{stage_id}:{attempt}:ok")
            break
    return seq


def run_once(
    ready_sort: Callable[[list[str]], list[str]] | None = None,
    policy: dict | None = None,
) -> list[str]:
    seq: list[str] = []
    for stage_id in topo_order(ready_sort=ready_sort):
        chunk = expand_stage(stage_id, policy)
        seq.extend(chunk)
        if chunk and chunk[-1].endswith(":fail"):
            break
    return seq


def worked_case() -> dict:
    a = run_once()
    b = run_once()
    return {
        "expected": list(EXPECTED_GOOD),
        "identical": a == b,
        "matches_expected": a == list(EXPECTED_GOOD) and b == list(EXPECTED_GOOD),
        "run_1": a,
        "run_2": b,
    }


def broken_case_reverse_ready() -> dict:
    """BAD arm: reverse ready-set sort. Diamond children swap; sequences differ."""
    good = run_once(ready_sort=lambda xs: sorted(xs))
    bad = run_once(ready_sort=lambda xs: list(reversed(sorted(xs))))
    return {
        "differ": good != bad,
        "good": good,
        "bad": bad,
    }


def refuse_jitter_policy() -> dict:
    policy = dict(RETRY_POLICY)
    policy["jitter"] = True
    try:
        backoff_seconds(2, policy)
        return {"refused": False}
    except ValueError as exc:
        return {"refused": True, "reason": str(exc)}
