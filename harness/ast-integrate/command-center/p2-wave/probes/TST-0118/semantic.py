"""Semantic checker for grammar-valid workflow libraries and manifests.

Hostile but syntactically valid documents must produce a typed rejection.
Expansion is bounded: a cyclic subworkflow cannot hang or crash this path.
"""
from __future__ import annotations

import time
from typing import Any

# Production bounds. A 2-cycle must be named CYCLIC_SUBWORKFLOW well before
# these fire; they exist so a missed cycle cannot become a hang.
MAX_NESTING = 8
MAX_VISITS = 4096
HANG_MS = 1500.0

CYCLIC_SUBWORKFLOW = "CYCLIC_SUBWORKFLOW"
BARRIER_ZERO_PRODUCERS = "BARRIER_ZERO_PRODUCERS"
LOOP_NO_CONVERGENCE = "LOOP_NO_CONVERGENCE"
DEEP_NESTING = "DEEP_NESTING"
UNKNOWN_SUBWORKFLOW_REF = "UNKNOWN_SUBWORKFLOW_REF"
DUPLICATE_WORKFLOW_ID = "DUPLICATE_WORKFLOW_ID"
DUPLICATE_NODE_ID = "DUPLICATE_NODE_ID"
HANG_BOUND_EXCEEDED = "HANG_BOUND_EXCEEDED"
INTERNAL_CRASH = "INTERNAL_CRASH"
UNKNOWN_KIND = "UNKNOWN_KIND"


def _codes_for_workflow(wf: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> list[str]:
    codes: list[str] = []
    nodes = [n for n in (wf.get("nodes") or []) if isinstance(n, dict)]
    seen_nodes: set[str] = set()
    producer_ids: set[str] = set()
    for node in nodes:
        nid = node.get("id")
        if isinstance(nid, str):
            if nid in seen_nodes:
                codes.append(DUPLICATE_NODE_ID)
            seen_nodes.add(nid)
            if node.get("type") != "barrier":
                producer_ids.add(nid)
        ntype = node.get("type")
        if ntype == "subworkflow" and node.get("ref") not in by_id:
            codes.append(UNKNOWN_SUBWORKFLOW_REF)
        if ntype == "loop":
            conv = node.get("convergence")
            if not isinstance(conv, dict) or "rule" not in conv:
                codes.append(LOOP_NO_CONVERGENCE)
    for node in nodes:
        if node.get("type") != "barrier":
            continue
        awaits = node.get("awaits")
        if not isinstance(awaits, list) or len(awaits) == 0:
            codes.append(BARRIER_ZERO_PRODUCERS)
            continue
        # A producer is a non-barrier node in this workflow. Awaiting only
        # missing names (or nothing that can produce) is the same defect.
        if not any(a in producer_ids for a in awaits):
            codes.append(BARRIER_ZERO_PRODUCERS)
    return codes


def _expand_cycles(
    start: str,
    by_id: dict[str, dict[str, Any]],
    *,
    detect_cycle: bool,
    max_nesting: int,
    max_visits: int,
) -> tuple[list[str], int]:
    """Walk subworkflow refs iteratively. Production sets detect_cycle=True.

    The naive path omits the seen-stack and relies only on max_visits, which
    is the hang-watchdog: a 2-cycle without a seen-set burns visits until the
    bound, proving the missing cycle check would not terminate.
    """
    codes: list[str] = []
    visits = 0
    stack: list[tuple[str, tuple[str, ...]]] = [(start, ())]
    while stack:
        wid, path = stack.pop()
        visits += 1
        if visits > max_visits:
            codes.append(HANG_BOUND_EXCEEDED)
            break
        if detect_cycle and wid in path:
            codes.append(CYCLIC_SUBWORKFLOW)
            continue
        if len(path) >= max_nesting:
            codes.append(DEEP_NESTING)
            continue
        wf = by_id.get(wid)
        if wf is None:
            codes.append(UNKNOWN_SUBWORKFLOW_REF)
            continue
        nxt = path + (wid,)
        nodes = wf.get("nodes") or []
        for node in reversed(nodes):
            if isinstance(node, dict) and node.get("type") == "subworkflow":
                ref = node.get("ref")
                if isinstance(ref, str):
                    stack.append((ref, nxt))
    seen: set[str] = set()
    ordered: list[str] = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered, visits


def analyze(
    doc: Any,
    *,
    mode: str = "safe",
    max_nesting: int = MAX_NESTING,
    max_visits: int = MAX_VISITS,
) -> dict[str, Any]:
    """Return a typed verdict. Never raises; never unbounded-recurses."""
    t0 = time.perf_counter()
    try:
        if not isinstance(doc, dict):
            elapsed = (time.perf_counter() - t0) * 1000.0
            return _verdict(False, [UNKNOWN_KIND], elapsed, 0, mode)
        kind = doc.get("kind")
        if kind == "component-manifest":
            elapsed = (time.perf_counter() - t0) * 1000.0
            return _verdict(True, [], elapsed, 0, mode)
        if kind != "workflow-library":
            elapsed = (time.perf_counter() - t0) * 1000.0
            return _verdict(False, [UNKNOWN_KIND], elapsed, 0, mode)

        workflows = doc.get("workflows") if isinstance(doc.get("workflows"), list) else []
        by_id: dict[str, dict[str, Any]] = {}
        codes: list[str] = []
        for wf in workflows:
            if not isinstance(wf, dict):
                continue
            wid = wf.get("id")
            if not isinstance(wid, str):
                continue
            if wid in by_id:
                codes.append(DUPLICATE_WORKFLOW_ID)
                continue
            by_id[wid] = wf

        for wf in by_id.values():
            codes.extend(_codes_for_workflow(wf, by_id))

        visits_total = 0
        detect = mode != "naive"
        naive_visits = max_visits if detect else max_visits
        for wid in by_id:
            more, visits = _expand_cycles(
                wid,
                by_id,
                detect_cycle=detect,
                max_nesting=max_nesting if detect else max_nesting * 64,
                max_visits=naive_visits,
            )
            visits_total += visits
            codes.extend(more)
            if HANG_BOUND_EXCEEDED in more:
                break

        seen: set[str] = set()
        ordered: list[str] = []
        for c in codes:
            if c not in seen:
                seen.add(c)
                ordered.append(c)
        accepted = len(ordered) == 0
        elapsed = (time.perf_counter() - t0) * 1000.0
        return _verdict(accepted, ordered, elapsed, visits_total, mode)
    except RecursionError:
        elapsed = (time.perf_counter() - t0) * 1000.0
        return _verdict(False, [HANG_BOUND_EXCEEDED], elapsed, MAX_VISITS, mode)
    except Exception as exc:  # noqa: BLE001 — typed crash is the claim
        elapsed = (time.perf_counter() - t0) * 1000.0
        return _verdict(False, [INTERNAL_CRASH, type(exc).__name__], elapsed, 0, mode)


def _verdict(
    accepted: bool, codes: list[str], elapsed_ms: float, visits: int, mode: str
) -> dict[str, Any]:
    hung = HANG_BOUND_EXCEEDED in codes or elapsed_ms > HANG_MS
    crashed = INTERNAL_CRASH in codes
    return {
        "accepted": accepted,
        "codes": codes,
        "elapsed_ms": round(elapsed_ms, 3),
        "visits": visits,
        "mode": mode,
        "hung": hung,
        "crashed": crashed,
        "typed_rejection": (not accepted) and (not hung) and (not crashed) and bool(codes),
    }
