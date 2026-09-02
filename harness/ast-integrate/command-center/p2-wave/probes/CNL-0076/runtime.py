#!/usr/bin/env python3
"""CNL-0076 stopping-expression runtime evaluation semantics.

Pinned answers (executable, not prose-only):
  cadence        : end-of-round only
  mid-turn       : FORBIDDEN as an evaluation point
  end-of-turn    : snapshot may update; halt decision MUST NOT run
  purity         : side effects REJECTED at bind time (enforced, not assumed)
  intra-round flap: ignored; only the frozen end-of-round snapshot is visible

Two evaluation mechanisms that must agree:
  eval_ast  — recursive Kleene walk
  eval_rpn  — postfix compilation then stack walk
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

CADENCE = "end-of-round"
ALLOWED_EVAL_POINTS = frozenset({"end-of-round"})
FORBIDDEN_EVAL_POINTS = frozenset({"mid-turn", "end-of-turn"})

TRUE = True
FALSE = False
UNKNOWN = "unknown"

PURE_OPS = frozenset({"const", "var", "cmp", "and", "or", "not"})
IMPURE_OPS = frozenset({"assign", "call", "mutate", "write", "inc", "effect"})
CMP_RELS = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


class FrozenSnapshot(Mapping):
    """Immutable metric snapshot. Writes raise; evaluation cannot mutate state."""

    def __init__(self, data: Mapping[str, Any]):
        self._d = deepcopy(dict(data))

    def __getitem__(self, key: str) -> Any:
        return self._d[key]

    def __iter__(self):
        return iter(self._d)

    def __len__(self) -> int:
        return len(self._d)

    def __setitem__(self, key: str, value: Any) -> None:  # pragma: no cover
        raise TypeError("snapshot is frozen; stopping evaluation is side-effect free")

    def as_dict(self) -> dict[str, Any]:
        return deepcopy(self._d)


class PurityError(ValueError):
    pass


class CadenceError(ValueError):
    pass


def check_purity(expr: Any) -> dict[str, Any]:
    """Reject any AST node that can write, call, or otherwise cause an effect."""
    found: list[str] = []

    def walk(node: Any, path: str) -> None:
        if not isinstance(node, dict) or "op" not in node:
            found.append(f"{path}:not-an-expr-node")
            return
        op = str(node.get("op"))
        if op in IMPURE_OPS or node.get("effect") is True:
            found.append(f"{path}:impure-op:{op}")
            return
        if op not in PURE_OPS:
            found.append(f"{path}:unknown-op:{op}")
            return
        if op == "const":
            return
        if op == "var":
            if not isinstance(node.get("name"), str) or not node["name"]:
                found.append(f"{path}:unbound-var")
            return
        if op == "cmp":
            walk(node.get("left"), path + ".left")
            walk(node.get("right"), path + ".right")
            return
        if op in {"and", "or"}:
            args = node.get("args")
            if not isinstance(args, list) or len(args) < 2:
                found.append(f"{path}:{op}-arity")
                return
            for i, a in enumerate(args):
                walk(a, f"{path}.args[{i}]")
            return
        if op == "not":
            walk(node.get("arg"), path + ".arg")

    walk(expr, "$")
    if found:
        return {
            "accepted": False,
            "rejected": True,
            "reasons": found,
            "verdict": "REJECTED",
        }
    return {
        "accepted": True,
        "rejected": False,
        "reasons": [],
        "verdict": "ACCEPTED",
    }


def _kleene_and(vals: list[Any]) -> Any:
    if any(v is FALSE for v in vals):
        return FALSE
    if any(v == UNKNOWN for v in vals):
        return UNKNOWN
    return TRUE


def _kleene_or(vals: list[Any]) -> Any:
    if any(v is TRUE for v in vals):
        return TRUE
    if any(v == UNKNOWN for v in vals):
        return UNKNOWN
    return FALSE


def _kleene_not(v: Any) -> Any:
    if v is TRUE:
        return FALSE
    if v is FALSE:
        return TRUE
    return UNKNOWN


def _eval_const(node: dict) -> Any:
    v = node.get("value")
    if v is TRUE or v is FALSE:
        return v
    if v == UNKNOWN:
        return UNKNOWN
    return v


def eval_ast(expr: dict, snapshot: Mapping[str, Any]) -> Any:
    """Recursive Kleene evaluation over a frozen snapshot. No short-circuit skip
    of sibling terms: terms are pure, so order cannot change the result, and
    Unknown is not hidden behind a True/False sibling without being combined.
    """
    op = expr["op"]
    if op == "const":
        return _eval_const(expr)
    if op == "var":
        name = expr["name"]
        if name not in snapshot:
            return UNKNOWN
        return snapshot[name]
    if op == "cmp":
        left = eval_ast(expr["left"], snapshot)
        right = eval_ast(expr["right"], snapshot)
        if left == UNKNOWN or right == UNKNOWN:
            return UNKNOWN
        rel = CMP_RELS[expr["rel"]]
        return bool(rel(left, right))
    if op == "and":
        return _kleene_and([eval_ast(a, snapshot) for a in expr["args"]])
    if op == "or":
        return _kleene_or([eval_ast(a, snapshot) for a in expr["args"]])
    if op == "not":
        return _kleene_not(eval_ast(expr["arg"], snapshot))
    raise PurityError(f"impure-or-unknown-op:{op}")


def compile_rpn(expr: dict) -> list[dict]:
    out: list[dict] = []

    def walk(node: dict) -> None:
        op = node["op"]
        if op == "const":
            out.append({"op": "push", "value": _eval_const(node)})
            return
        if op == "var":
            out.append({"op": "load", "name": node["name"]})
            return
        if op == "cmp":
            walk(node["left"])
            walk(node["right"])
            out.append({"op": "cmp", "rel": node["rel"]})
            return
        if op in {"and", "or"}:
            for a in node["args"]:
                walk(a)
            out.append({"op": op, "n": len(node["args"])})
            return
        if op == "not":
            walk(node["arg"])
            out.append({"op": "not"})
            return
        raise PurityError(f"impure-or-unknown-op:{op}")

    walk(expr)
    return out


def eval_rpn(expr: dict, snapshot: Mapping[str, Any]) -> Any:
    """Independent mechanism: postfix machine over the same frozen snapshot."""
    stack: list[Any] = []
    for ins in compile_rpn(expr):
        op = ins["op"]
        if op == "push":
            stack.append(ins["value"])
        elif op == "load":
            name = ins["name"]
            stack.append(snapshot[name] if name in snapshot else UNKNOWN)
        elif op == "cmp":
            right = stack.pop()
            left = stack.pop()
            if left == UNKNOWN or right == UNKNOWN:
                stack.append(UNKNOWN)
            else:
                stack.append(bool(CMP_RELS[ins["rel"]](left, right)))
        elif op == "and":
            n = ins["n"]
            args = [stack.pop() for _ in range(n)]
            args.reverse()
            stack.append(_kleene_and(args))
        elif op == "or":
            n = ins["n"]
            args = [stack.pop() for _ in range(n)]
            args.reverse()
            stack.append(_kleene_or(args))
        elif op == "not":
            stack.append(_kleene_not(stack.pop()))
        else:
            raise PurityError(f"impure-or-unknown-op:{op}")
    if len(stack) != 1:
        raise ValueError("rpn-stack-imbalance")
    return stack[0]


def freeze(metrics: Mapping[str, Any]) -> FrozenSnapshot:
    return FrozenSnapshot(metrics)


def recount_last_snapshot(expr: dict, turns: list[dict]) -> Any:
    """Independent recount: last turn of the round only, no cadence driver."""
    if not turns:
        return UNKNOWN
    snap = freeze(turns[-1]["metrics"])
    a = eval_ast(expr, snap)
    b = eval_rpn(expr, snap)
    if a != b:
        raise ValueError(f"mechanism-disagreement ast={a!r} rpn={b!r}")
    return a


def force_eval_impure(expr: dict, snapshot: FrozenSnapshot) -> dict[str, Any]:
    """Negative-control helper: skip the purity gate and try to run anyway.

    Used to prove the gate is not vacuous: an assign/call does not become a
    successful halt when the gate is bypassed; it errors on the frozen snapshot
    or on the unknown op.
    """
    try:
        val = eval_ast(expr, snapshot)
        return {"raised": False, "value": val, "halt": val is TRUE}
    except (PurityError, TypeError, KeyError, ValueError) as exc:
        return {
            "raised": True,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "halt": False,
        }


def run_round(
    expr: dict,
    turns: list[dict],
    eval_point: str,
    skip_purity: bool = False,
) -> dict[str, Any]:
    """Drive one round. Halt is decided only at end-of-round on the frozen last snapshot."""
    purity = check_purity(expr)
    if not skip_purity and purity["rejected"]:
        return {
            "evaluated": False,
            "rejected": True,
            "purity": purity,
            "halt": False,
            "result": None,
            "cadence_violation": False,
            "eval_point": eval_point,
            "reasons": purity["reasons"],
        }
    if eval_point not in ALLOWED_EVAL_POINTS:
        return {
            "evaluated": False,
            "rejected": False,
            "purity": purity,
            "halt": False,
            "result": None,
            "cadence_violation": True,
            "eval_point": eval_point,
            "reasons": [f"cadence-forbidden:{eval_point}"],
        }
    intra = []
    for t in turns:
        snap_t = freeze(t["metrics"])
        intra.append(
            {
                "id": t.get("id"),
                "metrics": snap_t.as_dict(),
                "would_be": eval_ast(expr, snap_t),
            }
        )
    last = freeze(turns[-1]["metrics"]) if turns else freeze({})
    ast_v = eval_ast(expr, last)
    rpn_v = eval_rpn(expr, last)
    if ast_v != rpn_v:
        raise ValueError(f"mechanism-disagreement ast={ast_v!r} rpn={rpn_v!r}")
    halt = ast_v is TRUE
    return {
        "evaluated": True,
        "rejected": False,
        "purity": purity,
        "halt": halt,
        "result": ast_v,
        "rpn_result": rpn_v,
        "cadence_violation": False,
        "eval_point": eval_point,
        "cadence": CADENCE,
        "snapshot": last.as_dict(),
        "intra_round_path": intra,
        "reasons": [],
    }
