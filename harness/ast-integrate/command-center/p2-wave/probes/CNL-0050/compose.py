"""Compile protocol compositions from four primitives.

Primitives: sequence, splice, nest, repeat-until.
Phase rule: every converge event must pop a prior unmatched diverge.
A composition that emits converge before diverge is rejected at compile time.
"""
from __future__ import annotations

from typing import Any

PRIMITIVES = ("sequence", "splice", "nest", "repeat-until")
OPS = frozenset(("leaf",) + PRIMITIVES)
PHASES = frozenset(("neutral", "diverge", "converge"))


class CompileError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _as_obj(expr: Any) -> dict:
    if not isinstance(expr, dict):
        raise CompileError("not-object", f"expr is {type(expr).__name__}, not object")
    op = expr.get("op")
    if op not in OPS:
        raise CompileError("unknown-op", f"op={op!r} not in {sorted(OPS)}")
    return expr


def linearize(expr: Any) -> list[dict]:
    expr = _as_obj(expr)
    op = expr["op"]
    if op == "leaf":
        pid = expr.get("id")
        if not isinstance(pid, str) or not pid:
            raise CompileError("leaf-id", "leaf requires non-empty id")
        phase = expr.get("phase", "neutral")
        if phase not in PHASES:
            raise CompileError("leaf-phase", f"phase={phase!r}")
        return [{"kind": phase, "id": pid, "op": "leaf"}]
    if op == "sequence":
        steps = expr.get("steps")
        if not isinstance(steps, list) or not steps:
            raise CompileError("empty-sequence", "sequence.steps must be a non-empty list")
        out: list[dict] = []
        for step in steps:
            out.extend(linearize(step))
        return out
    if op == "nest":
        inners = expr.get("inners")
        if not isinstance(inners, list) or not inners:
            raise CompileError("empty-nest", "nest.inners must be a non-empty list")
        nid = expr.get("id") or "nest"
        out = [{"kind": "diverge", "id": nid, "op": "nest"}]
        for inner in inners:
            out.extend(linearize(inner))
        out.append({"kind": "converge", "id": nid, "op": "nest"})
        return out
    if op == "splice":
        if "base" not in expr or "insert" not in expr:
            raise CompileError("splice-shape", "splice requires base and insert")
        base = linearize(expr["base"])
        insert = linearize(expr["insert"])
        at = expr.get("at", len(base))
        if not isinstance(at, int) or at < 0 or at > len(base):
            raise CompileError("splice-at", f"at={at!r} out of range 0..{len(base)}")
        return base[:at] + insert + base[at:]
    if op == "repeat-until":
        if "body" not in expr:
            raise CompileError("repeat-until-body", "repeat-until requires body")
        until = expr.get("until")
        if not isinstance(until, str) or not until.strip():
            raise CompileError("repeat-until-pred", "repeat-until requires until predicate")
        body = linearize(expr["body"])
        return body + [
            {"kind": "neutral", "id": f"until:{until.strip()}", "op": "repeat-until"}
        ]
    raise CompileError("unknown-op", f"op={op!r}")


def check_order(events: list[dict]) -> tuple[bool, dict]:
    depth = 0
    for i, event in enumerate(events):
        kind = event.get("kind")
        if kind == "diverge":
            depth += 1
        elif kind == "converge":
            if depth == 0:
                return False, {
                    "code": "converge-before-diverge",
                    "index": i,
                    "event": event,
                }
            depth -= 1
    if depth != 0:
        return False, {"code": "unclosed-diverge", "depth": depth}
    return True, {"code": "ok", "depth": 0, "n_events": len(events)}


def compile_expr(expr: Any) -> dict:
    try:
        events = linearize(expr)
    except CompileError as exc:
        return {
            "accepted": False,
            "stage": "syntax",
            "code": exc.code,
            "message": exc.message,
            "events": [],
        }
    ok, info = check_order(events)
    if not ok:
        return {
            "accepted": False,
            "stage": "phase-order",
            "code": info["code"],
            "detail": info,
            "events": events,
        }
    return {
        "accepted": True,
        "stage": "ok",
        "code": "ok",
        "detail": info,
        "events": events,
    }


KNOWN_GOOD = {
    "id": "known-good-nest-diverge-then-converge",
    "expr": {
        "op": "nest",
        "id": "mirror-split",
        "inners": [
            {"op": "leaf", "id": "P07-copy-a", "phase": "neutral"},
            {"op": "leaf", "id": "P07-copy-b", "phase": "neutral"},
        ],
    },
}

PLANTED_BAD = {
    "id": "planted-converge-before-diverge",
    "expr": {
        "op": "sequence",
        "steps": [
            {"op": "leaf", "id": "join-early", "phase": "converge"},
            {"op": "leaf", "id": "split-late", "phase": "diverge"},
        ],
    },
}

PLANTED_BAD_SPLICE = {
    "id": "planted-splice-converge-at-head",
    "expr": {
        "op": "splice",
        "at": 0,
        "base": KNOWN_GOOD["expr"],
        "insert": {"op": "leaf", "id": "premature-join", "phase": "converge"},
    },
}


def negative_control_record() -> dict:
    result = compile_expr(PLANTED_BAD["expr"])
    return {
        "fixture_id": PLANTED_BAD["id"],
        "intended_reject": "converge-before-diverge",
        "accepted": result["accepted"],
        "stage": result["stage"],
        "code": result["code"],
        "verbatim": (
            f"compile({PLANTED_BAD['id']}) accepted={result['accepted']} "
            f"stage={result['stage']} code={result['code']}"
        ),
        "what_the_check_does_on_the_state_it_rejects": (
            "On a sequence whose first event is phase=converge and whose second "
            "event is phase=diverge, compile_expr returns accepted=false at "
            "stage=phase-order with code=converge-before-diverge and does not "
            "emit a runnable schedule."
        ),
    }
