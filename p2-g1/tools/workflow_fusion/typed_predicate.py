"""Finite typed predicates for conditional-hybrid fusion (IMP-0186)."""
from __future__ import annotations

from itertools import product
from typing import Any


def input_fields(input_type: dict[str, Any]) -> dict[str, list[Any]]:
    fields = (input_type or {}).get("fields") or {}
    out: dict[str, list[Any]] = {}
    for name, spec in fields.items():
        kind = str((spec or {}).get("kind") or "")
        if kind == "enum":
            out[name] = list((spec or {}).get("values") or [])
        else:
            out[name] = list((spec or {}).get("values") or [None])
    return out


def typed_universe(input_type: dict[str, Any]) -> list[dict[str, Any]]:
    fields = input_fields(input_type)
    names = sorted(fields)
    if not names:
        return [{}]
    rows: list[dict[str, Any]] = []
    for combo in product(*(fields[n] for n in names)):
        rows.append(dict(zip(names, combo)))
    return rows


def check_assignment(raw: dict[str, Any], input_type: dict[str, Any]) -> dict[str, Any]:
    fields = input_fields(input_type)
    typed: dict[str, Any] = {}
    for name, values in fields.items():
        if name not in raw:
            raise KeyError(name)
        val = raw[name]
        if values and val not in values:
            raise ValueError(f"{name}={val!r} not in {values}")
        typed[name] = val
    return typed


def eval_pred(pred: dict[str, Any] | None, env: dict[str, Any]) -> bool:
    if not pred:
        return False
    op = str(pred.get("op") or "")
    if op == "true":
        return True
    if op == "false":
        return False
    if op == "eq":
        return env.get(pred.get("field")) == pred.get("value")
    if op == "in":
        return env.get(pred.get("field")) in list(pred.get("values") or [])
    if op == "and":
        args = list(pred.get("args") or [])
        return all(eval_pred(a, env) for a in args) if args else False
    if op == "or":
        args = list(pred.get("args") or [])
        return any(eval_pred(a, env) for a in args)
    if op == "not":
        inner = pred.get("arg") or (pred.get("args") or [None])[0]
        return not eval_pred(inner, env)
    return False
