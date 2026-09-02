"""Evaluator-readable stopping expressions (AND/OR/NOT, ANY, ALL, weighted)."""
from __future__ import annotations

import re
from typing import Any

OPS_NARY = {"AND", "OR"}
OPS_UNARY = {"NOT"}
OPS_QUANT = {"ANY", "ALL"}
OPS_W = {"WEIGHTED"}
CMPS = {">=", "<=", "==", "!=", ">", "<"}
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUM = re.compile(r"-?\d+(?:\.\d+)?")
_CMP = re.compile(r">=|<=|==|!=")
_CMP1 = re.compile(r"[><]")


class StopError(ValueError):
    pass


def is_readable(node: Any) -> tuple[bool, str]:
    try:
        _require_readable(node)
    except StopError as exc:
        return False, str(exc)
    return True, "ok"


def _require_readable(node: Any) -> None:
    if node is None:
        raise StopError("missing-stopping")
    if isinstance(node, str):
        text = node.strip()
        if not text:
            raise StopError("empty-prose")
        try:
            _parse_infix(text)
        except StopError as exc:
            raise StopError(f"prose-unreadable:{exc}") from exc
        return
    if not isinstance(node, dict):
        raise StopError(f"non-object-stopping:{type(node).__name__}")
    if "prose" in node:
        raise StopError("prose-field")
    if "var" in node:
        if node.get("cmp") not in CMPS:
            raise StopError("atom-bad-cmp")
        if "value" not in node:
            raise StopError("atom-missing-value")
        if not isinstance(node["var"], str) or not node["var"]:
            raise StopError("atom-bad-var")
        return
    op = node.get("op")
    if op in OPS_NARY:
        args = node.get("args")
        if not isinstance(args, list) or len(args) < 2:
            raise StopError("nary-malformed")
        for arg in args:
            _require_readable(arg)
        return
    if op in OPS_UNARY:
        if "arg" not in node:
            raise StopError("not-missing-arg")
        _require_readable(node["arg"])
        return
    if op in OPS_QUANT:
        if not isinstance(node.get("over"), str) or not node.get("over"):
            raise StopError("quant-bad-over")
        _require_readable(node.get("pred"))
        return
    if op in OPS_W:
        thr = node.get("threshold")
        if not isinstance(thr, (int, float)):
            raise StopError("weighted-bad-threshold")
        if not isinstance(node.get("over"), str):
            raise StopError("weighted-bad-over")
        _require_readable(node.get("pred"))
        return
    raise StopError(f"unknown-op:{op!r}")


def _tokens(text: str) -> list[tuple[str, Any]]:
    i = 0
    n = len(text)
    out: list[tuple[str, Any]] = []
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if text.startswith("AND", i) and _kw_end(text, i, 3):
            out.append(("AND", "AND"))
            i += 3
            continue
        if text.startswith("OR", i) and _kw_end(text, i, 2):
            out.append(("OR", "OR"))
            i += 2
            continue
        if text.startswith("NOT", i) and _kw_end(text, i, 3):
            out.append(("NOT", "NOT"))
            i += 3
            continue
        m = _CMP.match(text, i)
        if m:
            out.append(("CMP", m.group(0)))
            i = m.end()
            continue
        m = _CMP1.match(text, i)
        if m:
            out.append(("CMP", m.group(0)))
            i = m.end()
            continue
        if ch == "(":
            out.append(("LP", "("))
            i += 1
            continue
        if ch == ")":
            out.append(("RP", ")"))
            i += 1
            continue
        m = _NUM.match(text, i)
        if m and (i == 0 or not text[i - 1].isalpha()):
            raw = m.group(0)
            out.append(("NUM", float(raw) if "." in raw else int(raw)))
            i = m.end()
            continue
        m = _IDENT.match(text, i)
        if m:
            ident = m.group(0)
            if ident in {"true", "false"}:
                out.append(("BOOL", ident == "true"))
            else:
                out.append(("ID", ident))
            i = m.end()
            continue
        raise StopError(f"infix-bad-char:{ch!r}@{i}")
    out.append(("EOF", None))
    return out


def _kw_end(text: str, i: int, ln: int) -> bool:
    end = i + ln
    if end < len(text) and (text[end].isalnum() or text[end] == "_"):
        return False
    return True


def _parse_infix(text: str) -> dict:
    toks = _tokens(text)
    pos = 0

    def peek() -> str:
        return toks[pos][0]

    def eat(kind: str) -> Any:
        nonlocal pos
        k, v = toks[pos]
        if k != kind:
            raise StopError(f"infix-expected-{kind}-got-{k}")
        pos += 1
        return v

    def parse_or() -> dict:
        node = parse_and()
        while peek() == "OR":
            eat("OR")
            node = {"op": "OR", "args": [node, parse_and()]}
        return node

    def parse_and() -> dict:
        node = parse_not()
        while peek() == "AND":
            eat("AND")
            node = {"op": "AND", "args": [node, parse_not()]}
        return node

    def parse_not() -> dict:
        if peek() == "NOT":
            eat("NOT")
            return {"op": "NOT", "arg": parse_not()}
        return parse_atom()

    def parse_atom() -> dict:
        if peek() == "LP":
            eat("LP")
            node = parse_or()
            eat("RP")
            return node
        if peek() != "ID":
            raise StopError(f"infix-atom:{peek()}")
        var = eat("ID")
        cmp_ = eat("CMP")
        k = peek()
        if k == "NUM":
            val: Any = eat("NUM")
        elif k == "BOOL":
            val = eat("BOOL")
        elif k == "ID":
            val = eat("ID")
        else:
            raise StopError("infix-rhs")
        return {"var": var, "cmp": cmp_, "value": val}

    tree = parse_or()
    if peek() != "EOF":
        raise StopError(f"infix-trailing:{peek()}")
    return tree


def normalize(node: Any) -> Any:
    if isinstance(node, str):
        return _parse_infix(node.strip())
    return node


def eval_expr(node: Any, env: dict[str, Any], seat: dict[str, Any] | None = None) -> bool:
    node = normalize(node)
    if "var" in node:
        val = _lookup(node["var"], env, seat)
        return _cmp(val, node["cmp"], node["value"])
    op = node["op"]
    if op == "AND":
        return all(eval_expr(a, env, seat) for a in node["args"])
    if op == "OR":
        return any(eval_expr(a, env, seat) for a in node["args"])
    if op == "NOT":
        return not eval_expr(node["arg"], env, seat)
    if op in OPS_QUANT:
        items = _collection(env, node["over"])
        flags = [eval_expr(node["pred"], env, item) for item in items]
        return all(flags) if op == "ALL" else any(flags)
    if op == "WEIGHTED":
        items = _collection(env, node["over"])
        if not items:
            return False
        acc = 0.0
        tot = 0.0
        for item in items:
            w = float(item.get("weight", 1.0))
            tot += w
            if eval_expr(node["pred"], env, item):
                acc += w
        return (acc / tot) >= float(node["threshold"])
    raise StopError(f"eval-unknown-op:{op}")


def _collection(env: dict[str, Any], name: str) -> list[dict[str, Any]]:
    items = env.get(name)
    if not isinstance(items, list):
        raise StopError(f"missing-collection:{name}")
    return items


def _lookup(var: str, env: dict[str, Any], seat: dict[str, Any] | None) -> Any:
    if seat is not None and var in seat:
        return seat[var]
    if var in env:
        return env[var]
    raise StopError(f"unbound:{var}")


def _cmp(left: Any, op: str, right: Any) -> bool:
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if op == ">=":
        return left >= right
    if op == "<=":
        return left <= right
    if op == ">":
        return left > right
    if op == "<":
        return left < right
    raise StopError(f"bad-cmp:{op}")
