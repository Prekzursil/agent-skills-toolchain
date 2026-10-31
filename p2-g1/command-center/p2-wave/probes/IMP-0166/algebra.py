"""IMP-0166: composable Boolean stopping-rule algebra with Kleene evaluation.

Grammar (case-insensitive keywords, inspector-friendly):
  expr    := or_expr
  or_expr := and_expr (OR and_expr)*
  and_expr:= unit (AND unit)*
  unit    := metric op value
           | ALL '(' expr (',' expr)* ')'
           | ANY '(' expr (',' expr)* ')'
           | WEIGHTED '(' NUMBER ',' witem (',' witem)* ')'
  witem   := expr ':' NUMBER
Values: NUMBER | true | false | quoted-string. Prefixes "stop when"/"halt when"
are stripped before parsing. A missing metric evaluates UNKNOWN (Kleene):
  ALL: FALSE if any FALSE, TRUE if all TRUE, else UNKNOWN
  ANY: TRUE if any TRUE, FALSE if all FALSE, else UNKNOWN
"""
from __future__ import annotations

import re


class ParseError(Exception):
    pass


_TOKEN_RE = re.compile(
    r"""\s*(?:
        (?P<op>>=|<=|==|!=|>|<)
      | (?P<num>-?\d+(?:\.\d+)?)
      | (?P<str>'[^']*'|"[^"]*")
      | (?P<lparen>\()
      | (?P<rparen>\))
      | (?P<comma>,)
      | (?P<colon>:)
      | (?P<ident>[A-Za-z_][A-Za-z0-9_-]*)
    )""",
    re.VERBOSE,
)

_PREFIX_RE = re.compile(r"^(?:stop|halt)\s+when\s+", re.IGNORECASE)


def _tokenize(text: str) -> list:
    toks = []
    pos = 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if m is None:
            if text[pos:].strip() == "":
                break
            raise ParseError(f"bad character at {pos}: {text[pos:pos+8]!r}")
        pos = m.end()
        kind = m.lastgroup
        val = m.group(kind)
        if kind == "ident" and val.upper() in ("AND", "OR"):
            toks.append((val.upper(), val))
        elif kind == "ident" and val in ("true", "false"):
            toks.append(("BOOL", val == "true"))
        else:
            toks.append((kind, val))
    return toks


class _Parser:
    def __init__(self, toks):
        self.toks = toks
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def eat(self, kind=None):
        k, v = self.peek()
        if k is None or (kind is not None and k != kind):
            return None
        self.i += 1
        return (k, v)

    def expect(self, kind):
        got = self.eat(kind)
        if got is None:
            k, v = self.peek()
            raise ParseError(f"expected {kind}, got {k} {v!r} at {self.i}")
        return got

    def parse(self):
        node = self.or_expr()
        if self.i < len(self.toks):
            k, v = self.peek()
            raise ParseError(f"trailing tokens at {self.i} ({k})")
        return node

    def or_expr(self):
        args = [self.and_expr()]
        while self.peek()[0] == "OR":
            self.eat()
            args.append(self.and_expr())
        return args[0] if len(args) == 1 else {"kind": "ANY", "args": args}

    def and_expr(self):
        args = [self.unit()]
        while self.peek()[0] == "AND":
            self.eat()
            args.append(self.unit())
        return args[0] if len(args) == 1 else {"kind": "ALL", "args": args}

    def unit(self):
        k, v = self.peek()
        if k == "ident" and v.upper() in ("ALL", "ANY"):
            self.eat()
            self.expect("lparen")
            args = [self.or_expr()]
            while self.eat("comma"):
                args.append(self.or_expr())
            self.expect("rparen")
            return {"kind": v.upper(), "args": args}
        if k == "ident" and v.upper() == "WEIGHTED":
            self.eat()
            self.expect("lparen")
            thr = float(self.expect("num")[1])
            self.expect("comma")  # threshold is separated from the first item
            items = []
            while True:
                sub = self.or_expr()
                self.expect("colon")
                w = float(self.expect("num")[1])
                items.append({"expr": sub, "weight": w})
                if not self.eat("comma"):
                    break
            self.expect("rparen")
            return {"kind": "WEIGHTED", "threshold": thr, "items": items}
        metric = self.expect("ident")[1]
        op = self.expect("op")[1]
        kk, vv = self.peek()
        if kk == "num":
            self.eat()
            value = float(vv) if "." in vv else int(vv)
        elif kk == "str":
            self.eat()
            value = vv[1:-1]
        elif kk == "BOOL":
            self.eat()
            value = vv
        elif kk == "ident":  # bare symbol value, e.g. quality_gate == PASS
            self.eat()
            value = vv
        else:
            raise ParseError(f"expected value, got {kk} {vv!r} at {self.i}")
        return {"kind": "CMP", "metric": metric, "rel": op, "value": value}


_CMP = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
}


def parse(source: str) -> dict:
    text = _PREFIX_RE.sub("", source.strip())
    return _Parser(_tokenize(text)).parse()


UNKNOWN = "UNKNOWN"


def evaluate(node: dict, state: dict):
    """Kleene evaluation -> 'TRUE' | 'FALSE' | UNKNOWN."""
    kind = node["kind"]
    if kind == "CMP":
        if node["metric"] not in state:
            return UNKNOWN
        try:
            ok = _CMP[node["rel"]](state[node["metric"]], node["value"])
        except TypeError:
            return UNKNOWN
        return "TRUE" if ok else "FALSE"
    if kind == "ALL":
        vals = [evaluate(a, state) for a in node["args"]]
        if "FALSE" in vals:
            return "FALSE"
        if all(v == "TRUE" for v in vals):
            return "TRUE"
        return UNKNOWN
    if kind == "ANY":
        vals = [evaluate(a, state) for a in node["args"]]
        if "TRUE" in vals:
            return "TRUE"
        if all(v == "FALSE" for v in vals):
            return "FALSE"
        return UNKNOWN
    if kind == "WEIGHTED":
        got = 0.0
        total = 0.0
        known = True
        for item in node["items"]:
            total += item["weight"]
            v = evaluate(item["expr"], state)
            if v == UNKNOWN:
                known = False
            elif v == "TRUE":
                got += item["weight"]
        if not known:
            return UNKNOWN
        return "TRUE" if (got / total) >= node["threshold"] else "FALSE"
    raise ParseError(f"unknown node kind {kind!r}")


def decide(tri: str) -> str:
    return {"TRUE": "STOP", "FALSE": "CONTINUE", UNKNOWN: "NEEDS-PROBE"}[tri]
