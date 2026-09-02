#!/usr/bin/env python3
"""Typed stopping-rule algebra: ANY / ALL / NOT / WEIGHTED, executable eval.

Compile rejects expressions that can never become true. Expressions already
true on the t0 run state are compiled but flagged degenerate_immediate_stop.
"""
from __future__ import annotations

import json
from typing import Any

TRUE = True
FALSE = False
UNKNOWN = "unknown"

RELS = (">=", "<=", "==", "!=", ">", "<")
CMP_FN = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}
INVERT_REL = {
    ">=": "<",
    ">": "<=",
    "<=": ">",
    "<": ">=",
    "==": "!=",
    "!=": "==",
}

T0_STATE: dict[str, Any] = {
    "rounds": 0,
    "stages_completed": 0,
    "unique_ideas": 0,
    "completeness_score": 0.0,
    "error_present": False,
    "halt_requested": False,
    "stalled": False,
    "done": False,
    "quality": 0.0,
    "coverage": 0.0,
}


class ParseError(ValueError):
    pass


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _kleene_not(v: Any) -> Any:
    if v is TRUE:
        return FALSE
    if v is FALSE:
        return TRUE
    return UNKNOWN


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


def ast_cmp(pred: str, rel: str, value: Any) -> dict[str, Any]:
    if rel not in RELS:
        raise ParseError(f"bad-rel:{rel}")
    if not pred:
        raise ParseError("empty-pred")
    return {"op": "cmp", "pred": pred, "rel": rel, "value": value}


def ast_all(args: list[dict[str, Any]]) -> dict[str, Any]:
    return {"op": "ALL", "args": list(args)}


def ast_any(args: list[dict[str, Any]]) -> dict[str, Any]:
    return {"op": "ANY", "args": list(args)}


def ast_not(arg: dict[str, Any]) -> dict[str, Any]:
    return {"op": "NOT", "arg": arg}


def ast_weighted(terms: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    return {"op": "WEIGHTED", "terms": list(terms), "threshold": float(threshold)}


class _Tok:
    def __init__(self, kind: str, value: Any, pos: int) -> None:
        self.kind = kind
        self.value = value
        self.pos = pos


def _tokenize(text: str) -> list[_Tok]:
    s = text.strip()
    i = 0
    n = len(s)
    out: list[_Tok] = []
    while i < n:
        ch = s[i]
        if ch.isspace():
            i += 1
            continue
        if s.startswith(">=", i) or s.startswith("<=", i) or s.startswith("==", i) or s.startswith(
            "!=", i
        ):
            out.append(_Tok("rel", s[i : i + 2], i))
            i += 2
            continue
        if ch in "><":
            out.append(_Tok("rel", ch, i))
            i += 1
            continue
        if ch in "(),:":
            out.append(_Tok(ch, ch, i))
            i += 1
            continue
        if ch in "\"'":
            q = ch
            i += 1
            buf: list[str] = []
            while i < n and s[i] != q:
                buf.append(s[i])
                i += 1
            if i >= n:
                raise ParseError("unterminated-string")
            i += 1
            out.append(_Tok("str", "".join(buf), i))
            continue
        if ch.isdigit() or (ch == "-" and i + 1 < n and s[i + 1].isdigit()):
            j = i + 1
            while j < n and (s[j].isdigit() or s[j] == "."):
                j += 1
            raw = s[i:j]
            val: Any = float(raw) if "." in raw else int(raw)
            out.append(_Tok("num", val, i))
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < n and (s[j].isalnum() or s[j] == "_"):
                j += 1
            word = s[i:j]
            low = word.lower()
            if low == "true":
                out.append(_Tok("bool", True, i))
            elif low == "false":
                out.append(_Tok("bool", False, i))
            else:
                out.append(_Tok("id", word, i))
            i = j
            continue
        raise ParseError(f"bad-char:{ch!r}@{i}")
    out.append(_Tok("eof", None, n))
    return out


class _Parser:
    def __init__(self, text: str) -> None:
        self.toks = _tokenize(text)
        self.i = 0

    def peek(self) -> _Tok:
        return self.toks[self.i]

    def take(self, kind: str | None = None) -> _Tok:
        tok = self.toks[self.i]
        if kind and tok.kind != kind:
            raise ParseError(f"want:{kind} got:{tok.kind} val={tok.value!r}")
        self.i += 1
        return tok

    def parse(self) -> dict[str, Any]:
        expr = self.expr()
        if self.peek().kind != "eof":
            raise ParseError(f"trailing:{self.peek().kind}")
        return expr

    def expr(self) -> dict[str, Any]:
        tok = self.peek()
        if tok.kind != "id":
            raise ParseError(f"expr-start:{tok.kind}")
        name = str(tok.value)
        upper = name.upper()
        nxt = self.toks[self.i + 1] if self.i + 1 < len(self.toks) else None
        if upper in {"ALL", "ANY", "NOT", "WEIGHTED"} and nxt is not None and nxt.kind == "(":
            self.take("id")
            self.take("(")
            if upper == "NOT":
                inner = self.expr()
                self.take(")")
                return ast_not(inner)
            if upper == "WEIGHTED":
                return self._weighted_after_open()
            args: list[dict[str, Any]] = []
            if self.peek().kind != ")":
                args.append(self.expr())
                while self.peek().kind == ",":
                    self.take(",")
                    args.append(self.expr())
            self.take(")")
            if upper == "ALL":
                return ast_all(args)
            return ast_any(args)
        return self._atom()

    def _weighted_after_open(self) -> dict[str, Any]:
        terms: list[dict[str, Any]] = []
        threshold: float | None = None
        if self.peek().kind != ")":
            while True:
                ident = str(self.take("id").value)
                self.take(":")
                num = self.take("num").value
                if ident.lower() == "threshold":
                    threshold = float(num)
                else:
                    terms.append(
                        {
                            "weight": float(num),
                            "expr": ast_cmp(ident, ">=", 1),
                        }
                    )
                if self.peek().kind != ",":
                    break
                self.take(",")
        self.take(")")
        if self.peek().kind == "rel":
            rel = str(self.take("rel").value)
            if rel != ">=":
                raise ParseError(f"weighted-rel-must-be-gte:{rel}")
            threshold = float(self.take("num").value)
        if threshold is None:
            raise ParseError("weighted-missing-threshold")
        return ast_weighted(terms, threshold)

    def _atom(self) -> dict[str, Any]:
        pred = str(self.take("id").value)
        rel = str(self.take("rel").value)
        val_tok = self.peek()
        if val_tok.kind == "num":
            value: Any = self.take("num").value
        elif val_tok.kind == "bool":
            value = self.take("bool").value
        elif val_tok.kind == "str":
            value = self.take("str").value
        elif val_tok.kind == "id":
            value = self.take("id").value
        else:
            raise ParseError(f"atom-value:{val_tok.kind}")
        return ast_cmp(pred, rel, value)


def parse_dsl(text: str) -> dict[str, Any]:
    return _Parser(text).parse()


def _from_stopping_object(obj: dict[str, Any]) -> dict[str, Any] | None:
    max_stages = obj.get("max_stages", obj.get("max_stages"))
    on_error = obj.get("on_error", obj.get("on_error"))
    if max_stages is None and on_error is None:
        return None
    parts: list[dict[str, Any]] = []
    if _is_num(max_stages):
        parts.append(ast_cmp("stages_completed", ">=", max_stages))
    if str(on_error).lower() in {"halt", "stop", "true", "1"}:
        parts.append(ast_cmp("error_present", "==", True))
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return ast_any(parts)


def from_obj(obj: Any) -> dict[str, Any]:
    if isinstance(obj, str):
        return parse_dsl(obj)
    if not isinstance(obj, dict):
        raise ParseError(f"not-object:{type(obj).__name__}")
    if obj.get("op") in {"cmp", "ALL", "ANY", "NOT", "WEIGHTED"}:
        return obj
    if "all" in obj:
        args = obj["all"]
        if not isinstance(args, list):
            raise ParseError("all-not-list")
        return ast_all([from_obj(a) for a in args])
    if "any" in obj:
        args = obj["any"]
        if not isinstance(args, list):
            raise ParseError("any-not-list")
        return ast_any([from_obj(a) for a in args])
    if "not" in obj:
        return ast_not(from_obj(obj["not"]))
    if "weighted" in obj:
        w = obj["weighted"]
        if not isinstance(w, dict):
            raise ParseError("weighted-not-object")
        terms = []
        for t in w.get("terms") or []:
            if not isinstance(t, dict):
                raise ParseError("weighted-term")
            terms.append({"weight": float(t["weight"]), "expr": from_obj(t["expr"])})
        return ast_weighted(terms, float(w["threshold"]))
    stop_obj = _from_stopping_object(obj)
    if stop_obj is not None:
        return stop_obj
    pred = obj.get("pred") or obj.get("name") or obj.get("predicate")
    rel = obj.get("rel") or obj.get("cmp")
    if pred and rel in RELS and "value" in obj:
        return ast_cmp(str(pred), str(rel), obj["value"])
    raise ParseError("unrecognized-object")


def _nnf(ast: dict[str, Any], neg: bool = False) -> dict[str, Any]:
    op = ast["op"]
    if op == "cmp":
        if not neg:
            return ast
        return ast_cmp(ast["pred"], INVERT_REL[ast["rel"]], ast["value"])
    if op == "NOT":
        return _nnf(ast["arg"], not neg)
    if op == "ALL":
        args = [_nnf(a, neg) for a in ast["args"]]
        return ast_any(args) if neg else ast_all(args)
    if op == "ANY":
        args = [_nnf(a, neg) for a in ast["args"]]
        return ast_all(args) if neg else ast_any(args)
    if op == "WEIGHTED":
        if neg:
            return ast_not(ast)
        return ast
    raise ParseError(f"nnf-op:{op}")


def _bounds_unsat(atoms: list[dict[str, Any]]) -> bool:
    by: dict[str, list[tuple[str, Any]]] = {}
    for a in atoms:
        if a.get("op") != "cmp":
            continue
        by.setdefault(str(a["pred"]), []).append((str(a["rel"]), a["value"]))
    for _pred, cons in by.items():
        eqs = [v for rel, v in cons if rel == "=="]
        if len({json.dumps(v, sort_keys=True, default=str) for v in eqs}) > 1:
            return True
        for rel, v in cons:
            if rel == "!=" and any(v == e for e in eqs):
                return True
        nums = [(rel, v) for rel, v in cons if _is_num(v)]
        bools = [(rel, v) for rel, v in cons if isinstance(v, bool)]
        if any(rel == "==" and v is True for rel, v in bools) and any(
            rel == "==" and v is False for rel, v in bools
        ):
            return True
        if not nums:
            continue
        lo: float | None = None
        hi: float | None = None
        lo_inc = True
        hi_inc = True
        for rel, v in nums:
            fv = float(v)
            if rel in {">=", "=="}:
                if lo is None or fv > lo:
                    lo, lo_inc = fv, True
                elif fv == lo:
                    lo_inc = True
            if rel == ">":
                if lo is None or fv > lo or (fv == lo and lo_inc):
                    lo, lo_inc = fv, False
            if rel in {"<=", "=="}:
                if hi is None or fv < hi:
                    hi, hi_inc = fv, True
                elif fv == hi:
                    hi_inc = True
            if rel == "<":
                if hi is None or fv < hi or (fv == hi and hi_inc):
                    hi, hi_inc = fv, False
        if lo is not None and hi is not None:
            if lo > hi:
                return True
            if lo == hi and (not lo_inc or not hi_inc):
                return True
    return False


def _collect_all_cmps(ast: dict[str, Any]) -> list[dict[str, Any]] | None:
    op = ast["op"]
    if op == "cmp":
        return [ast]
    if op == "ALL":
        out: list[dict[str, Any]] = []
        for a in ast["args"]:
            got = _collect_all_cmps(a)
            if got is None:
                return None
            out.extend(got)
        return out
    return None


def unsatisfiable(ast: dict[str, Any]) -> tuple[bool, str]:
    op = ast["op"]
    if op == "ANY" and not ast["args"]:
        return True, "empty-ANY-never-true"
    if op == "WEIGHTED":
        total = sum(float(t["weight"]) for t in ast["terms"])
        if float(ast["threshold"]) > total + 1e-12:
            return True, "weighted-threshold-exceeds-weight-sum"
    if op == "ALL":
        for a in ast["args"]:
            bad, why = unsatisfiable(a)
            if bad:
                return True, f"all-contains-unsat-child:{why}"
        dumped = [json.dumps(a, sort_keys=True, default=str) for a in ast["args"]]
        for a in ast["args"]:
            if a.get("op") == "NOT":
                inner = json.dumps(a["arg"], sort_keys=True, default=str)
                if inner in dumped:
                    return True, "all-p-and-not-p"
    if op == "ANY" and ast["args"] and all(unsatisfiable(a)[0] for a in ast["args"]):
        return True, "any-all-children-unsat"
    if op == "NOT":
        if ast["arg"].get("op") == "ALL" and not ast["arg"].get("args"):
            return True, "not-empty-all"
        if ast["arg"].get("op") == "WEIGHTED" and float(ast["arg"]["threshold"]) <= 0:
            return True, "not-weighted-threshold-nonpositive"
    nnf = _nnf(ast)
    cmps = _collect_all_cmps(nnf)
    if cmps is not None and _bounds_unsat(cmps):
        return True, "contradictory-bounds"
    return False, ""


def tautology_trivial(ast: dict[str, Any]) -> bool:
    if ast["op"] == "ALL" and not ast["args"]:
        return True
    if ast["op"] == "WEIGHTED" and float(ast["threshold"]) <= 0:
        return True
    if ast["op"] == "NOT" and ast["arg"].get("op") == "ANY" and not ast["arg"].get("args"):
        return True
    return False


def eval_ast(ast: dict[str, Any], state: dict[str, Any]) -> Any:
    op = ast["op"]
    if op == "cmp":
        name = ast["pred"]
        if name not in state:
            return UNKNOWN
        left = state[name]
        right = ast["value"]
        try:
            return bool(CMP_FN[ast["rel"]](left, right))
        except TypeError:
            return UNKNOWN
    if op == "ALL":
        if not ast["args"]:
            return TRUE
        return _kleene_and([eval_ast(a, state) for a in ast["args"]])
    if op == "ANY":
        if not ast["args"]:
            return FALSE
        return _kleene_or([eval_ast(a, state) for a in ast["args"]])
    if op == "NOT":
        return _kleene_not(eval_ast(ast["arg"], state))
    if op == "WEIGHTED":
        got = 0.0
        unknown = 0.0
        for t in ast["terms"]:
            v = eval_ast(t["expr"], state)
            w = float(t["weight"])
            if v is TRUE:
                got += w
            elif v == UNKNOWN:
                unknown += w
        thr = float(ast["threshold"])
        if got >= thr:
            return TRUE
        if got + unknown < thr:
            return FALSE
        return UNKNOWN
    raise ParseError(f"eval-op:{op}")


def raw_text(stop: Any) -> str:
    if stop is None:
        return ""
    if isinstance(stop, str):
        return stop
    return json.dumps(stop, sort_keys=True, separators=(",", ":"))


def compile_stop(stop: Any) -> dict[str, Any]:
    if stop is None or stop == "" or stop == []:
        return {
            "compile_result": "ABSENT",
            "ast": None,
            "degenerate_immediate_stop": False,
            "reject_reason": None,
            "eval_t0": None,
            "raw_stop_text": "",
        }
    raw = raw_text(stop)
    try:
        ast = from_obj(stop)
    except ParseError as exc:
        return {
            "compile_result": "PROSE-ONLY",
            "ast": None,
            "degenerate_immediate_stop": False,
            "reject_reason": None,
            "eval_t0": None,
            "raw_stop_text": raw,
            "parse_error": str(exc),
        }
    bad, why = unsatisfiable(ast)
    if bad:
        return {
            "compile_result": "COMPILE-REJECT",
            "ast": ast,
            "degenerate_immediate_stop": False,
            "reject_reason": why,
            "eval_t0": None,
            "raw_stop_text": raw,
        }
    eval_t0 = eval_ast(ast, T0_STATE)
    degenerate = eval_t0 is TRUE or tautology_trivial(ast)
    return {
        "compile_result": "EVALUABLE",
        "ast": ast,
        "degenerate_immediate_stop": bool(degenerate),
        "reject_reason": None,
        "eval_t0": eval_t0,
        "raw_stop_text": raw,
    }


def both_states_controls() -> dict[str, Any]:
    never_src = "ALL(done==true, NOT(done==true))"
    never = compile_stop(never_src)
    already_src = "rounds>=0"
    already = compile_stop(already_src)
    live_src = "unique_ideas>=100"
    live = compile_stop(live_src)
    later = dict(T0_STATE)
    later["unique_ideas"] = 100
    live_later = eval_ast(live["ast"], later) if live["ast"] else None
    return {
        "never_true": {
            "source": never_src,
            "compile_result": never["compile_result"],
            "reject_reason": never["reject_reason"],
            "rejected_at_compile": never["compile_result"] == "COMPILE-REJECT",
        },
        "already_true_at_t0": {
            "source": already_src,
            "compile_result": already["compile_result"],
            "degenerate_immediate_stop": already["degenerate_immediate_stop"],
            "eval_t0": already["eval_t0"],
        },
        "becomes_true": {
            "source": live_src,
            "compile_result": live["compile_result"],
            "eval_t0": live["eval_t0"],
            "eval_later_unique_ideas_100": live_later,
            "degenerate_immediate_stop": live["degenerate_immediate_stop"],
        },
    }
