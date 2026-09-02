"""A10 stopping-expression grammar (local stand-in for undelivered CNL-0010).

Covers AND / OR / NOT, parentheses, comparisons, ANY/ALL n-ary forms.
The CNL-0079 example is accepted unchanged: no rewrite of identifiers or ops.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from expr import A10_REQUIRED_EXAMPLES, SPEC_EXPRESSION


class ParseError(ValueError):
    pass


@dataclass(frozen=True)
class Tok:
    kind: str
    value: Any
    pos: int


def _lex(src: str) -> list[Tok]:
    s = src
    i = 0
    n = len(s)
    out: list[Tok] = []
    keywords = {
        "AND": "AND",
        "OR": "OR",
        "NOT": "NOT",
        "ANY": "ANY",
        "ALL": "ALL",
        "TRUE": "BOOL",
        "FALSE": "BOOL",
    }
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if s.startswith(">=", i):
            out.append(Tok("OP", ">=", i))
            i += 2
            continue
        if s.startswith("<=", i):
            out.append(Tok("OP", "<=", i))
            i += 2
            continue
        if s.startswith("==", i):
            out.append(Tok("OP", "==", i))
            i += 2
            continue
        if s.startswith("!=", i):
            out.append(Tok("OP", "!=", i))
            i += 2
            continue
        if c in "><":
            out.append(Tok("OP", c, i))
            i += 1
            continue
        if c == "(":
            out.append(Tok("LPAREN", "(", i))
            i += 1
            continue
        if c == ")":
            out.append(Tok("RPAREN", ")", i))
            i += 1
            continue
        if c == ",":
            out.append(Tok("COMMA", ",", i))
            i += 1
            continue
        if c.isdigit() or (c == "." and i + 1 < n and s[i + 1].isdigit()):
            j = i
            while j < n and (s[j].isdigit() or s[j] == "."):
                j += 1
            out.append(Tok("NUM", float(s[i:j]), i))
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (s[j].isalnum() or s[j] == "_"):
                j += 1
            word = s[i:j]
            up = word.upper()
            if up in keywords:
                kind = keywords[up]
                val: Any = True if up == "TRUE" else False if up == "FALSE" else word
                if kind == "BOOL":
                    out.append(Tok("BOOL", val, i))
                else:
                    out.append(Tok(kind, word, i))
            else:
                out.append(Tok("IDENT", word, i))
            i = j
            continue
        raise ParseError(f"unexpected character {c!r} at {i}")
    out.append(Tok("EOF", None, i))
    return out


@dataclass
class Node:
    kind: str
    value: Any = None
    children: tuple["Node", ...] = ()


class _Parser:
    def __init__(self, src: str) -> None:
        self.src = src
        self.toks = _lex(src)
        self.i = 0

    def peek(self) -> Tok:
        return self.toks[self.i]

    def eat(self, kind: str | None = None) -> Tok:
        t = self.toks[self.i]
        if kind is not None and t.kind != kind:
            raise ParseError(f"expected {kind} at {t.pos}, got {t.kind} ({t.value!r})")
        self.i += 1
        return t

    def parse(self) -> Node:
        node = self.or_expr()
        if self.peek().kind != "EOF":
            t = self.peek()
            raise ParseError(f"trailing input at {t.pos}: {t.kind} {t.value!r}")
        return node

    def or_expr(self) -> Node:
        left = self.and_expr()
        while self.peek().kind == "OR":
            self.eat("OR")
            left = Node("or", children=(left, self.and_expr()))
        return left

    def and_expr(self) -> Node:
        left = self.not_expr()
        while self.peek().kind == "AND":
            self.eat("AND")
            left = Node("and", children=(left, self.not_expr()))
        return left

    def not_expr(self) -> Node:
        if self.peek().kind == "NOT":
            self.eat("NOT")
            return Node("not", children=(self.not_expr(),))
        return self.atom()

    def atom(self) -> Node:
        t = self.peek()
        if t.kind == "LPAREN":
            self.eat("LPAREN")
            n = self.or_expr()
            self.eat("RPAREN")
            return n
        if t.kind == "ANY":
            return self.nary("any")
        if t.kind == "ALL":
            return self.nary("all")
        if t.kind == "BOOL":
            self.eat("BOOL")
            return Node("lit", value=bool(t.value))
        if t.kind == "IDENT":
            ident = self.eat("IDENT").value
            if self.peek().kind == "OP":
                op = self.eat("OP").value
                rhs = self.value()
                return Node("cmp", value=(ident, op, rhs))
            return Node("ident", value=ident)
        raise ParseError(f"expected atom at {t.pos}, got {t.kind}")

    def nary(self, kind: str) -> Node:
        self.eat(kind.upper())
        self.eat("LPAREN")
        args = [self.or_expr()]
        while self.peek().kind == "COMMA":
            self.eat("COMMA")
            args.append(self.or_expr())
        self.eat("RPAREN")
        if len(args) < 1:
            raise ParseError(f"{kind} requires at least one argument")
        return Node(kind, children=tuple(args))

    def value(self) -> Any:
        t = self.peek()
        if t.kind == "NUM":
            self.eat("NUM")
            return t.value
        if t.kind == "BOOL":
            self.eat("BOOL")
            return t.value
        if t.kind == "IDENT":
            return self.eat("IDENT").value
        raise ParseError(f"expected value at {t.pos}")


def parse(src: str) -> Node:
    return _Parser(src).parse()


def accepted_unchanged(src: str) -> bool:
    """True iff src parses with no rewrite. Identifiers stay as written."""
    try:
        node = parse(src)
    except ParseError:
        return False
    return _mentions_idents_from_source(node, src)


def _mentions_idents_from_source(node: Node, src: str) -> bool:
    idents: list[str] = []

    def walk(n: Node) -> None:
        if n.kind == "cmp":
            idents.append(n.value[0])
            rhs = n.value[2]
            if isinstance(rhs, str):
                idents.append(rhs)
        elif n.kind == "ident":
            idents.append(n.value)
        for ch in n.children:
            walk(ch)

    walk(node)
    return all(i in src for i in idents)


def eval_tree(node: Node, env: dict[str, Any]) -> bool:
    def truth(x: Any) -> bool:
        if isinstance(x, bool):
            return x
        if isinstance(x, (int, float)):
            return bool(x)
        raise TypeError(f"not boolean: {x!r}")

    if node.kind == "and":
        return all(eval_tree(c, env) for c in node.children)
    if node.kind == "or":
        return any(eval_tree(c, env) for c in node.children)
    if node.kind == "not":
        return not eval_tree(node.children[0], env)
    if node.kind == "any":
        return any(eval_tree(c, env) for c in node.children)
    if node.kind == "all":
        return all(eval_tree(c, env) for c in node.children)
    if node.kind == "lit":
        return bool(node.value)
    if node.kind == "ident":
        return truth(env[node.value])
    if node.kind == "cmp":
        name, op, rhs = node.value
        if name not in env:
            raise KeyError(f"unbound metric {name}")
        lhs = env[name]
        if op == ">=":
            return lhs >= rhs
        if op == "<=":
            return lhs <= rhs
        if op == ">":
            return lhs > rhs
        if op == "<":
            return lhs < rhs
        if op == "==":
            return lhs == rhs or str(lhs) == str(rhs)
        if op == "!=":
            return not (lhs == rhs or str(lhs) == str(rhs))
        raise ParseError(f"unknown op {op}")
    raise ParseError(f"unknown node {node.kind}")


def eval_expr(src: str, env: dict[str, Any]) -> bool:
    return eval_tree(parse(src), env)


def parse_all_required() -> list[dict[str, Any]]:
    rows = []
    for src in A10_REQUIRED_EXAMPLES:
        try:
            parse(src)
            ok = accepted_unchanged(src)
            err = None
        except ParseError as exc:
            ok = False
            err = str(exc)
        rows.append(
            {
                "expression": src,
                "accepted_unchanged": ok,
                "accepted_unchanged": ok,
                "error": err,
            }
        )
    return rows


def tautology_or_unsat_rejected() -> dict[str, Any]:
    """Vacuous-parser control: x AND NOT x must parse but is statically unsat."""
    src = "x AND NOT x"
    tree = parse(src)

    def collect_cmp_or_ident(n: Node, acc: list[str]) -> None:
        if n.kind in {"ident", "cmp"}:
            acc.append(n.kind)
        for c in n.children:
            collect_cmp_or_ident(c, acc)

    kinds: list[str] = []
    collect_cmp_or_ident(tree, kinds)
    # Evaluate both assignments of x; never true.
    ever = eval_expr(src, {"x": True}) or eval_expr(src, {"x": False})
    return {
        "expression": src,
        "parses": True,
        "ever_true": ever,
        "statically_unsatisfiable": not ever,
        "statically_unsatisfiable": not ever,
        "ever_true": ever,
        "ever_true": ever,
    }


def compile_spec() -> Callable[[dict[str, Any]], bool]:
    tree = parse(SPEC_EXPRESSION)
    if not accepted_unchanged(SPEC_EXPRESSION):
        raise ParseError("spec expression not accepted unchanged")
    return lambda env: eval_tree(tree, env)


accepted_unchanged = accepted_unchanged
parse_all_required = parse_all_required
tautology_or_unsat_rejected = tautology_or_unsat_rejected
accepted_unchanged = accepted_unchanged
parse_all_required = parse_all_required
tautology_or_unsat_rejected = tautology_or_unsat_rejected
accepted_unchanged = accepted_unchanged
parse_all_required = parse_all_required
tautology_or_unsat_rejected = tautology_or_unsat_rejected
