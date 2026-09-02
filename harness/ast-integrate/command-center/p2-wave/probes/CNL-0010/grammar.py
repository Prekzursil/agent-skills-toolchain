"""Stopping-expression surface parser (AND/OR/NOT, ANY, ALL, weighted).

Precedence: NOT binds tightest, then AND, then OR (left-associative).
Bare identifiers are boolean atoms. Identifiers after a relation are values.
"""
from __future__ import annotations

from typing import Any

KEYWORDS = {
    "AND": "AND",
    "OR": "OR",
    "NOT": "NOT",
    "ANY": "ANY",
    "ALL": "ALL",
    "WEIGHTED": "WEIGHTED",
    "TRUE": "TRUE",
    "FALSE": "FALSE",
}
RELS = (">=", "<=", "!=", "==", ">", "<")


class ParseError(ValueError):
    def __init__(self, message: str, pos: int = 0):
        super().__init__(message)
        self.pos = pos
        self.code = "PARSE"


def tokenize(src: str) -> list[tuple[str, Any, int]]:
    s = src.strip()
    i = 0
    n = len(s)
    out: list[tuple[str, Any, int]] = []
    while i < n:
        ch = s[i]
        if ch.isspace():
            i += 1
            continue
        if s.startswith(RELS, i) or any(s.startswith(r, i) for r in RELS):
            rel = next(r for r in RELS if s.startswith(r, i))
            out.append(("REL", rel, i))
            i += len(rel)
            continue
        if ch in "()":
            out.append((ch, ch, i))
            i += 1
            continue
        if ch == ",":
            out.append(("COMMA", ",", i))
            i += 1
            continue
        if ch == "*":
            out.append(("STAR", "*", i))
            i += 1
            continue
        if ch in ("'", '"'):
            q = ch
            j = i + 1
            buf: list[str] = []
            while j < n and s[j] != q:
                buf.append(s[j])
                j += 1
            if j >= n:
                raise ParseError("unterminated string", i)
            out.append(("STRING", "".join(buf), i))
            i = j + 1
            continue
        if ch == "-" or ch.isdigit():
            j = i
            if s[j] == "-":
                j += 1
            if j >= n or not s[j].isdigit():
                raise ParseError("expected number", i)
            while j < n and s[j].isdigit():
                j += 1
            if j < n and s[j] == ".":
                j += 1
                while j < n and s[j].isdigit():
                    j += 1
            raw = s[i:j]
            val: int | float
            if "." in raw:
                val = float(raw)
            else:
                val = int(raw)
            out.append(("NUMBER", val, i))
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (s[j].isalnum() or s[j] == "_"):
                j += 1
            word = s[i:j]
            key = KEYWORDS.get(word.upper())
            if key in {"AND", "OR", "NOT", "ANY", "ALL", "WEIGHTED"}:
                out.append((key, word, i))
            elif key == "TRUE":
                out.append(("BOOL", True, i))
            elif key == "FALSE":
                out.append(("BOOL", False, i))
            else:
                out.append(("IDENT", word, i))
            i = j
            continue
        raise ParseError(f"unexpected character {ch!r}", i)
    out.append(("EOF", None, n))
    return out


class Parser:
    def __init__(self, src: str):
        self.src = src
        self.toks = tokenize(src)
        self.i = 0

    def peek(self) -> tuple[str, Any, int]:
        return self.toks[self.i]

    def kind(self) -> str:
        return self.peek()[0]

    def eat(self, kind: str) -> tuple[str, Any, int]:
        tok = self.peek()
        if tok[0] != kind:
            raise ParseError(f"expected {kind}, got {tok[0]}", tok[2])
        self.i += 1
        return tok

    def parse(self) -> dict[str, Any]:
        node = self.parse_or()
        if self.kind() != "EOF":
            raise ParseError(f"trailing input at {self.peek()[0]}", self.peek()[2])
        return node

    def parse_or(self) -> dict[str, Any]:
        left = self.parse_and()
        args = [left]
        while self.kind() == "OR":
            self.eat("OR")
            args.append(self.parse_and())
        if len(args) == 1:
            return args[0]
        return {"op": "or", "args": args}

    def parse_and(self) -> dict[str, Any]:
        left = self.parse_not()
        args = [left]
        while self.kind() == "AND":
            self.eat("AND")
            args.append(self.parse_not())
        if len(args) == 1:
            return args[0]
        return {"op": "and", "args": args}

    def parse_not(self) -> dict[str, Any]:
        if self.kind() == "NOT":
            self.eat("NOT")
            return {"op": "not", "arg": self.parse_not()}
        return self.parse_primary()

    def parse_primary(self) -> dict[str, Any]:
        k = self.kind()
        if k == "(":
            self.eat("(")
            node = self.parse_or()
            self.eat(")")
            return node
        if k == "ANY":
            return self.parse_any()
        if k == "ALL":
            return self.parse_all()
        if k == "WEIGHTED":
            return self.parse_weighted()
        if k == "IDENT":
            return self.parse_ident_or_cmp()
        raise ParseError(f"expected expression, got {k}", self.peek()[2])

    def parse_ident_or_cmp(self) -> dict[str, Any]:
        name = self.eat("IDENT")[1]
        if self.kind() == "REL":
            rel = self.eat("REL")[1]
            value = self.parse_value()
            return {"op": "cmp", "var": name, "rel": rel, "value": value}
        return {"op": "var", "name": name}

    def parse_value(self) -> Any:
        k = self.kind()
        if k == "NUMBER":
            return self.eat("NUMBER")[1]
        if k == "BOOL":
            return self.eat("BOOL")[1]
        if k == "STRING":
            return self.eat("STRING")[1]
        if k == "IDENT":
            return self.eat("IDENT")[1]
        raise ParseError("expected comparison value", self.peek()[2])

    def parse_any(self) -> dict[str, Any]:
        self.eat("ANY")
        self.eat("(")
        first = self.parse_any_arg()
        args: list[dict[str, Any]] = []
        k = 1
        if isinstance(first, dict) and first.get("_number") is not None:
            k = int(first["_number"])
        else:
            args.append(first)  # type: ignore[arg-type]
        while self.kind() == "COMMA":
            self.eat("COMMA")
            args.append(self.parse_or())
        self.eat(")")
        if k < 1:
            raise ParseError("ANY k must be >= 1")
        if not args:
            raise ParseError("ANY needs at least one clause")
        return {"op": "any", "k": k, "args": args}

    def parse_any_arg(self) -> dict[str, Any]:
        if self.kind() == "NUMBER" and self._looks_like_k_then_comma():
            return {"_number": self.eat("NUMBER")[1]}
        return self.parse_or()

    def _looks_like_k_then_comma(self) -> bool:
        if self.kind() != "NUMBER":
            return False
        nxt = self.toks[self.i + 1][0]
        return nxt == "COMMA"

    def parse_all(self) -> dict[str, Any]:
        self.eat("ALL")
        self.eat("(")
        args = [self.parse_or()]
        while self.kind() == "COMMA":
            self.eat("COMMA")
            args.append(self.parse_or())
        self.eat(")")
        return {"op": "all", "args": args}

    def parse_weighted(self) -> dict[str, Any]:
        self.eat("WEIGHTED")
        self.eat("(")
        if self.kind() != "NUMBER":
            raise ParseError("WEIGHTED first argument must be a threshold number")
        threshold = float(self.eat("NUMBER")[1])
        terms = []
        while self.kind() == "COMMA":
            self.eat("COMMA")
            terms.append(self.parse_weighted_term())
        self.eat(")")
        if not terms:
            raise ParseError("WEIGHTED needs at least one term")
        return {"op": "weighted", "threshold": threshold, "terms": terms}

    def parse_weighted_term(self) -> dict[str, Any]:
        if self.kind() != "NUMBER":
            raise ParseError("weighted term must start with a numeric weight")
        weight = float(self.eat("NUMBER")[1])
        self.eat("STAR")
        if self.kind() == "(":
            self.eat("(")
            arg = self.parse_or()
            self.eat(")")
        else:
            arg = self.parse_not()
        return {"weight": weight, "arg": arg}


def parse(src: str) -> dict[str, Any]:
    return Parser(src).parse()


def used_names(node: dict[str, Any]) -> set[str]:
    op = node.get("op")
    if op == "var":
        return {str(node["name"])}
    if op == "cmp":
        return {str(node["var"])}
    if op == "not":
        return used_names(node["arg"])
    if op in {"and", "or", "all", "any"}:
        names: set[str] = set()
        for arg in node.get("args") or []:
            names |= used_names(arg)
        return names
    if op == "weighted":
        names = set()
        for term in node.get("terms") or []:
            names |= used_names(term["arg"])
        return names
    return set()
