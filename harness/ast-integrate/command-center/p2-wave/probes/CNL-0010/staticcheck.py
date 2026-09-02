"""Static validation of a stopping-expression tree before any round runs.

Rejects: UNBOUND, TYPE, UNSATISFIABLE, TAUTOLOGY.
Does not evaluate a live council; domains come from the declared metric registry.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

from grammar import ParseError, parse, used_names

HERE = Path(__file__).resolve().parent
METRICS_PATH = HERE / "fixtures" / "metrics.json"

REL_INV = {
    ">=": "<",
    ">": "<=",
    "<=": ">",
    "<": ">=",
    "==": "!=",
    "!=": "==",
}


def load_metrics(path: Path | None = None) -> dict[str, Any]:
    p = path or METRICS_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def apply_rel(left: Any, rel: str, right: Any) -> bool:
    if rel == ">=":
        return left >= right
    if rel == "<=":
        return left <= right
    if rel == ">":
        return left > right
    if rel == "<":
        return left < right
    if rel == "==":
        return left == right
    if rel == "!=":
        return left != right
    raise ValueError(f"unknown rel {rel}")


def eval_tree(node: dict[str, Any], asn: dict[str, Any]) -> bool:
    op = node["op"]
    if op == "var":
        return bool(asn[node["name"]])
    if op == "cmp":
        return apply_rel(asn[node["var"]], node["rel"], node["value"])
    if op == "not":
        return not eval_tree(node["arg"], asn)
    if op == "and":
        return all(eval_tree(a, asn) for a in node["args"])
    if op == "or":
        return any(eval_tree(a, asn) for a in node["args"])
    if op == "all":
        return all(eval_tree(a, asn) for a in node["args"])
    if op == "any":
        return sum(1 for a in node["args"] if eval_tree(a, asn)) >= int(node["k"])
    if op == "weighted":
        total = sum(
            float(t["weight"]) for t in node["terms"] if eval_tree(t["arg"], asn)
        )
        return total >= float(node["threshold"])
    raise ValueError(f"unknown op {op}")


def _collect_cmp_constants(node: dict[str, Any], name: str, acc: list[Any]) -> None:
    op = node["op"]
    if op == "cmp" and node["var"] == name:
        acc.append(node["value"])
    elif op == "not":
        _collect_cmp_constants(node["arg"], name, acc)
    elif op in {"and", "or", "all", "any"}:
        for a in node["args"]:
            _collect_cmp_constants(a, name, acc)
    elif op == "weighted":
        for t in node["terms"]:
            _collect_cmp_constants(t["arg"], name, acc)


def candidates(name: str, spec: dict[str, Any], node: dict[str, Any]) -> list[Any]:
    kind = spec["type"]
    if kind == "boolean":
        return [False, True]
    if kind == "enum":
        return list(spec["values"])
    consts: list[Any] = []
    _collect_cmp_constants(node, name, consts)
    lo = spec.get("min")
    hi = spec.get("max")
    cands: set[Any] = set()
    if lo is not None:
        cands.add(lo)
    if hi is not None:
        cands.add(hi)
    for c in consts:
        if isinstance(c, bool) or isinstance(c, str):
            continue
        cands.add(c)
        if kind == "integer" and isinstance(c, (int, float)):
            cands.add(int(c) - 1)
            cands.add(int(c) + 1)
        elif isinstance(c, (int, float)):
            cands.add(float(c) - 1e-6)
            cands.add(float(c) + 1e-6)
    out = []
    for v in cands:
        if isinstance(v, str) or isinstance(v, bool):
            continue
        if lo is not None and v < lo:
            continue
        if hi is not None and v > hi:
            continue
        if kind == "integer":
            out.append(int(v) if float(v).is_integer() else v)
        else:
            out.append(v)
    if not out:
        if lo is not None:
            out.append(lo)
        elif hi is not None:
            out.append(hi)
        else:
            out.append(0)
    # unique preserving order
    seen = set()
    uniq = []
    for v in out:
        key = (type(v).__name__, v)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(v)
    return uniq


def type_error(node: dict[str, Any], metrics: dict[str, Any]) -> str | None:
    op = node["op"]
    if op == "var":
        name = node["name"]
        spec = metrics.get(name)
        if spec is None:
            return name
        if spec["type"] not in {"boolean"}:
            return f"TYPE:{name}:boolean-atom-on-{spec['type']}"
        return None
    if op == "cmp":
        name = node["var"]
        spec = metrics.get(name)
        if spec is None:
            return name
        val = node["value"]
        kind = spec["type"]
        if kind == "boolean" and not isinstance(val, bool):
            return f"TYPE:{name}:expected-boolean"
        if kind == "enum" and not isinstance(val, str):
            return f"TYPE:{name}:expected-enum"
        if kind == "enum" and val not in spec["values"]:
            return f"TYPE:{name}:enum-value"
        if kind in {"integer", "number"} and not isinstance(val, (int, float)):
            return f"TYPE:{name}:expected-number"
        if kind == "boolean" and node["rel"] not in {"==", "!="}:
            return f"TYPE:{name}:bad-rel-on-boolean"
        return None
    if op == "not":
        return type_error(node["arg"], metrics)
    if op in {"and", "or", "all", "any"}:
        for a in node["args"]:
            err = type_error(a, metrics)
            if err:
                return err
        return None
    if op == "weighted":
        for t in node["terms"]:
            err = type_error(t["arg"], metrics)
            if err:
                return err
        return None
    return f"TYPE:unknown-op:{op}"


def enumerate_assignments(
    node: dict[str, Any], metrics: dict[str, Any]
) -> list[dict[str, Any]]:
    names = sorted(used_names(node))
    axes = []
    for name in names:
        axes.append([(name, v) for v in candidates(name, metrics[name], node)])
    if not axes:
        return [{}]
    out = []
    for combo in itertools.product(*axes):
        out.append({k: v for k, v in combo})
    return out


def satisfiable(node: dict[str, Any], metrics: dict[str, Any]) -> bool:
    return any(eval_tree(node, asn) for asn in enumerate_assignments(node, metrics))


def tautology(node: dict[str, Any], metrics: dict[str, Any]) -> bool:
    asns = enumerate_assignments(node, metrics)
    if not asns:
        return False
    return all(eval_tree(node, asn) for asn in asns)


class StaticResult:
    def __init__(self, code: str, tree: dict[str, Any] | None, detail: str):
        self.code = code
        self.tree = tree
        self.detail = detail
        self.ok = code == "OK"

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "ok": self.ok,
            "detail": self.detail,
            "tree": self.tree,
        }


def check(src: str, metrics: dict[str, Any] | None = None) -> StaticResult:
    mets = metrics if metrics is not None else load_metrics()
    try:
        tree = parse(src)
    except ParseError as exc:
        return StaticResult("PARSE", None, str(exc))
    missing = sorted(n for n in used_names(tree) if n not in mets)
    if missing:
        return StaticResult(
            "UNBOUND",
            tree,
            "unbound variable(s): " + ", ".join(missing),
        )
    terr = type_error(tree, mets)
    if terr and not terr.startswith("TYPE:"):
        return StaticResult("UNBOUND", tree, f"unbound variable(s): {terr}")
    if terr and terr.startswith("TYPE:"):
        return StaticResult("TYPE", tree, terr)
    if not satisfiable(tree, mets):
        return StaticResult(
            "UNSATISFIABLE",
            tree,
            "never-satisfiable over the declared metric domains; rejected before any round",
        )
    if tautology(tree, mets):
        return StaticResult(
            "TAUTOLOGY",
            tree,
            "always-true over the declared metric domains; rejected before any round",
        )
    return StaticResult("OK", tree, "accepted")


def check_tree(tree: dict[str, Any], metrics: dict[str, Any] | None = None) -> StaticResult:
    mets = metrics if metrics is not None else load_metrics()
    missing = sorted(n for n in used_names(tree) if n not in mets)
    if missing:
        return StaticResult("UNBOUND", tree, "unbound variable(s): " + ", ".join(missing))
    if not satisfiable(tree, mets):
        return StaticResult("UNSATISFIABLE", tree, "never-satisfiable")
    if tautology(tree, mets):
        return StaticResult("TAUTOLOGY", tree, "always-true")
    return StaticResult("OK", tree, "accepted")
