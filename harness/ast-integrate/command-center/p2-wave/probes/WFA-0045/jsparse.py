#!/usr/bin/env python3
"""Recursive-descent parser for the saved-Workflow JS dialect subset.

Produces ESTree-shaped dicts. This is a syntactic parser only: it does not
know agent/phase/schema meaning. Used by both the independent counter and
the semantic adapter.
"""
from __future__ import annotations

from typing import Any


class ParseError(Exception):
    def __init__(self, message: str, line: int = 1, column: int = 0) -> None:
        super().__init__(f"{message} at {line}:{column}")
        self.line = line
        self.column = column


def loc(line: int, column: int) -> dict[str, int]:
    return {"line": line, "column": column}


class Tok:
    __slots__ = ("kind", "value", "line", "column")

    def __init__(self, kind: str, value: str, line: int, column: int) -> None:
        self.kind = kind
        self.value = value
        self.line = line
        self.column = column


def tokenize(src: str) -> list[Tok]:
    i = 0
    n = len(src)
    line = 1
    col = 0
    out: list[Tok] = []

    def adv(k: int = 1) -> None:
        nonlocal i, line, col
        for _ in range(k):
            if i < n and src[i] == "\n":
                line += 1
                col = 0
            else:
                col += 1
            i += 1

    two = {
        "=>",
        "===",
        "!==",
        "==",
        "!=",
        "&&",
        "||",
        "<=",
        ">=",
        "??",
        "...",
    }
    one = set("(){}[],.;:?+-*/%<>=!|&")

    while i < n:
        ch = src[i]
        if ch in " \t\r\n":
            adv()
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                adv()
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "*":
            adv(2)
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                adv()
            if i + 1 >= n:
                raise ParseError("unterminated comment", line, col)
            adv(2)
            continue
        sl, sc = line, col
        if ch in "\"'`":
            quote = ch
            adv()
            buf: list[str] = []
            while i < n and src[i] != quote:
                if src[i] == "\\":
                    adv()
                    if i >= n:
                        raise ParseError("unterminated string", sl, sc)
                    esc = src[i]
                    mapping = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", quote: quote}
                    buf.append(mapping.get(esc, esc))
                    adv()
                    continue
                if src[i] == "\n" and quote != "`":
                    raise ParseError("unterminated string", sl, sc)
                buf.append(src[i])
                adv()
            if i >= n:
                raise ParseError("unterminated string", sl, sc)
            adv()
            out.append(Tok("string", "".join(buf), sl, sc))
            continue
        if ch.isdigit():
            j = i
            while j < n and (src[j].isdigit() or src[j] == "."):
                j += 1
            out.append(Tok("number", src[i:j], sl, sc))
            adv(j - i)
            continue
        if ch.isalpha() or ch in "_$":
            j = i
            while j < n and (src[j].isalnum() or src[j] in "_$"):
                j += 1
            out.append(Tok("ident", src[i:j], sl, sc))
            adv(j - i)
            continue
        if src[i : i + 3] == "...":
            out.append(Tok("punct", "...", sl, sc))
            adv(3)
            continue
        if src[i : i + 3] in ("===", "!=="):
            out.append(Tok("punct", src[i : i + 3], sl, sc))
            adv(3)
            continue
        if src[i : i + 2] in two:
            out.append(Tok("punct", src[i : i + 2], sl, sc))
            adv(2)
            continue
        if ch in one:
            out.append(Tok("punct", ch, sl, sc))
            adv()
            continue
        raise ParseError(f"unexpected character {ch!r}", sl, sc)
    out.append(Tok("eof", "", line, col))
    return out


class Parser:
    def __init__(self, tokens: list[Tok], filename: str) -> None:
        self.toks = tokens
        self.i = 0
        self.filename = filename

    def cur(self) -> Tok:
        return self.toks[self.i]

    def at(self, *vals: str) -> bool:
        t = self.cur()
        return t.value in vals or t.kind in vals

    def eat(self, *vals: str) -> Tok | None:
        if self.at(*vals):
            t = self.cur()
            self.i += 1
            return t
        return None

    def expect(self, *vals: str) -> Tok:
        t = self.eat(*vals)
        if t is None:
            c = self.cur()
            raise ParseError(f"expected {vals} got {c.value!r}", c.line, c.column)
        return t

    def ident(self) -> Tok:
        t = self.cur()
        if t.kind != "ident":
            raise ParseError(f"expected identifier got {t.value!r}", t.line, t.column)
        self.i += 1
        return t

    def node(self, typ: str, t: Tok, **fields: Any) -> dict[str, Any]:
        d: dict[str, Any] = {"type": typ, "loc": loc(t.line, t.column), "file": self.filename}
        d.update(fields)
        return d

    def parse_program(self) -> dict[str, Any]:
        t0 = self.cur()
        body: list[dict[str, Any]] = []
        while not self.at("eof"):
            body.append(self.parse_stmt())
        return self.node("Program", t0, body=body, sourceType="module")

    def parse_stmt(self) -> dict[str, Any]:
        if self.at("export"):
            return self.parse_export()
        if self.at("async") or self.at("function"):
            return self.parse_function_decl()
        if self.at("const", "let", "var"):
            return self.parse_var()
        if self.at("return"):
            t = self.expect("return")
            arg = None if self.at(";", "}") else self.parse_expr()
            self.eat(";")
            return self.node("ReturnStatement", t, argument=arg)
        if self.at("if"):
            t = self.expect("if")
            self.expect("(")
            test = self.parse_expr()
            self.expect(")")
            cons = self.parse_stmt()
            alt = self.parse_stmt() if self.eat("else") else None
            return self.node("IfStatement", t, test=test, consequent=cons, alternate=alt)
        if self.at("{"):
            return self.parse_block()
        expr = self.parse_expr()
        self.eat(";")
        t = self.cur()
        return self.node("ExpressionStatement", t, expression=expr)

    def parse_export(self) -> dict[str, Any]:
        t = self.expect("export")
        default = bool(self.eat("default"))
        decl = self.parse_function_decl() if self.at("async", "function") else self.parse_expr()
        self.eat(";")
        return self.node("ExportDefaultDeclaration" if default else "ExportNamedDeclaration", t, declaration=decl)

    def parse_block(self) -> dict[str, Any]:
        t = self.expect("{")
        body: list[dict[str, Any]] = []
        while not self.at("}"):
            body.append(self.parse_stmt())
        self.expect("}")
        return self.node("BlockStatement", t, body=body)

    def parse_var(self) -> dict[str, Any]:
        t = self.expect("const", "let", "var")
        kind = t.value
        decls = [self.parse_var_decl()]
        while self.eat(","):
            decls.append(self.parse_var_decl())
        self.eat(";")
        return self.node("VariableDeclaration", t, kind=kind, declarations=decls)

    def parse_var_decl(self) -> dict[str, Any]:
        t = self.cur()
        ident = self.node("Identifier", t, name=self.ident().value)
        init = None
        if self.eat("="):
            init = self.parse_expr()
        return self.node("VariableDeclarator", t, id=ident, init=init)

    def parse_function_decl(self) -> dict[str, Any]:
        t0 = self.cur()
        is_async = bool(self.eat("async"))
        self.expect("function")
        name = None
        if self.cur().kind == "ident":
            it = self.ident()
            name = self.node("Identifier", it, name=it.value)
        params = self.parse_params()
        body = self.parse_block()
        return self.node(
            "FunctionDeclaration",
            t0,
            id=name,
            params=params,
            body=body,
            async_=is_async,
            generator=False,
        )

    def parse_params(self) -> list[dict[str, Any]]:
        self.expect("(")
        params: list[dict[str, Any]] = []
        if not self.at(")"):
            params.append(self.parse_pattern())
            while self.eat(","):
                if self.at(")"):
                    break
                params.append(self.parse_pattern())
        self.expect(")")
        return params

    def parse_pattern(self) -> dict[str, Any]:
        if self.at("{"):
            return self.parse_object_pattern()
        t = self.ident()
        return self.node("Identifier", t, name=t.value)

    def parse_object_pattern(self) -> dict[str, Any]:
        t = self.expect("{")
        props: list[dict[str, Any]] = []
        while not self.at("}"):
            key_tok = self.ident()
            key = self.node("Identifier", key_tok, name=key_tok.value)
            props.append(
                self.node(
                    "Property",
                    key_tok,
                    key=key,
                    value=key,
                    kind="init",
                    method=False,
                    shorthand=True,
                )
            )
            if not self.eat(","):
                break
        self.expect("}")
        return self.node("ObjectPattern", t, properties=props)

    def parse_expr(self) -> dict[str, Any]:
        return self.parse_or()

    def parse_or(self) -> dict[str, Any]:
        left = self.parse_and()
        while self.at("||", "??"):
            op = self.cur()
            self.i += 1
            right = self.parse_and()
            left = self.node("LogicalExpression", op, operator=op.value, left=left, right=right)
        return left

    def parse_and(self) -> dict[str, Any]:
        left = self.parse_eq()
        while self.at("&&"):
            op = self.cur()
            self.i += 1
            right = self.parse_eq()
            left = self.node("LogicalExpression", op, operator=op.value, left=left, right=right)
        return left

    def parse_eq(self) -> dict[str, Any]:
        left = self.parse_add()
        while self.at("==", "===", "!=", "!==", "<", ">", "<=", ">="):
            op = self.cur()
            self.i += 1
            right = self.parse_add()
            left = self.node("BinaryExpression", op, operator=op.value, left=left, right=right)
        return left

    def parse_add(self) -> dict[str, Any]:
        left = self.parse_unary()
        while self.at("+", "-", "*"):
            op = self.cur()
            self.i += 1
            right = self.parse_unary()
            left = self.node("BinaryExpression", op, operator=op.value, left=left, right=right)
        return left

    def parse_unary(self) -> dict[str, Any]:
        if self.at("await", "!", "+", "-"):
            op = self.cur()
            self.i += 1
            arg = self.parse_unary()
            if op.value == "await":
                return self.node("AwaitExpression", op, argument=arg)
            return self.node("UnaryExpression", op, operator=op.value, argument=arg, prefix=True)
        return self.parse_postfix()

    def parse_postfix(self) -> dict[str, Any]:
        node = self.parse_primary()
        while True:
            if self.eat("."):
                prop_tok = self.ident()
                node = self.node(
                    "MemberExpression",
                    prop_tok,
                    object=node,
                    property=self.node("Identifier", prop_tok, name=prop_tok.value),
                    computed=False,
                )
                continue
            if self.at("("):
                t = self.cur()
                args = self.parse_args()
                node = self.node("CallExpression", t, callee=node, arguments=args)
                continue
            if self.at("["):
                t = self.expect("[")
                idx = self.parse_expr()
                self.expect("]")
                node = self.node("MemberExpression", t, object=node, property=idx, computed=True)
                continue
            break
        return node

    def parse_args(self) -> list[dict[str, Any]]:
        self.expect("(")
        args: list[dict[str, Any]] = []
        if not self.at(")"):
            args.append(self.parse_expr())
            while self.eat(","):
                if self.at(")"):
                    break
                args.append(self.parse_expr())
        self.expect(")")
        return args

    def parse_primary(self) -> dict[str, Any]:
        t = self.cur()
        if self.at("async"):
            nxt = self.toks[self.i + 1]
            if nxt.value == "function":
                return self.parse_function_expr()
            if nxt.value == "(" or nxt.kind == "ident":
                return self.parse_arrow()
        if self.at("function"):
            return self.parse_function_expr()
        if t.kind == "ident":
            peek = self.toks[self.i + 1]
            if peek.value == "=>":
                return self.parse_arrow()
            self.i += 1
            if t.value == "true":
                return self.node("Literal", t, value=True, raw="true")
            if t.value == "false":
                return self.node("Literal", t, value=False, raw="false")
            if t.value == "null":
                return self.node("Literal", t, value=None, raw="null")
            if t.value == "undefined":
                return self.node("Identifier", t, name="undefined")
            return self.node("Identifier", t, name=t.value)
        if t.kind == "string":
            self.i += 1
            return self.node("Literal", t, value=t.value, raw=repr(t.value))
        if t.kind == "number":
            self.i += 1
            num: float | int
            num = float(t.value) if "." in t.value else int(t.value)
            return self.node("Literal", t, value=num, raw=t.value)
        if self.at("("):
            # (a, b) => or grouping
            save = self.i
            self.expect("(")
            if self.at(")") and self.toks[self.i + 1].value == "=>":
                self.i = save
                return self.parse_arrow()
            # look ahead: ident , ident ) =>
            if self.cur().kind == "ident":
                self.i = save
                # try arrow; fall back
                try:
                    return self.parse_arrow()
                except ParseError:
                    self.i = save
                    self.expect("(")
                    expr = self.parse_expr()
                    self.expect(")")
                    return expr
            expr = self.parse_expr()
            self.expect(")")
            return expr
        if self.at("{"):
            return self.parse_object()
        if self.at("["):
            return self.parse_array()
        raise ParseError(f"unexpected token {t.value!r}", t.line, t.column)

    def parse_arrow(self) -> dict[str, Any]:
        t0 = self.cur()
        is_async = bool(self.eat("async"))
        if self.at("("):
            params = self.parse_params()
        else:
            it = self.ident()
            params = [self.node("Identifier", it, name=it.value)]
        self.expect("=>")
        body = self.parse_block() if self.at("{") else self.parse_expr()
        return self.node(
            "ArrowFunctionExpression",
            t0,
            params=params,
            body=body,
            async_=is_async,
            expression=body.get("type") != "BlockStatement",
        )

    def parse_function_expr(self) -> dict[str, Any]:
        t0 = self.cur()
        is_async = bool(self.eat("async"))
        self.expect("function")
        name = None
        if self.cur().kind == "ident":
            it = self.ident()
            name = self.node("Identifier", it, name=it.value)
        params = self.parse_params()
        body = self.parse_block()
        return self.node(
            "FunctionExpression",
            t0,
            id=name,
            params=params,
            body=body,
            async_=is_async,
            generator=False,
        )

    def parse_object(self) -> dict[str, Any]:
        t = self.expect("{")
        props: list[dict[str, Any]] = []
        while not self.at("}"):
            key_tok = self.cur()
            if key_tok.kind == "ident":
                self.i += 1
                key = self.node("Identifier", key_tok, name=key_tok.value)
            elif key_tok.kind == "string":
                self.i += 1
                key = self.node("Literal", key_tok, value=key_tok.value, raw=repr(key_tok.value))
            else:
                raise ParseError("expected property key", key_tok.line, key_tok.column)
            self.expect(":")
            val = self.parse_expr()
            props.append(
                self.node(
                    "Property",
                    key_tok,
                    key=key,
                    value=val,
                    kind="init",
                    method=False,
                    shorthand=False,
                )
            )
            if not self.eat(","):
                break
        self.expect("}")
        return self.node("ObjectExpression", t, properties=props)

    def parse_array(self) -> dict[str, Any]:
        t = self.expect("[")
        els: list[dict[str, Any] | None] = []
        while not self.at("]"):
            if self.at(","):
                els.append(None)
                self.eat(",")
                continue
            els.append(self.parse_expr())
            if not self.eat(","):
                break
        self.expect("]")
        return self.node("ArrayExpression", t, elements=els)


def parse_js(src: str, filename: str = "<input>") -> dict[str, Any]:
    return Parser(tokenize(src), filename).parse_program()


def walk(node: Any) -> Any:
    if isinstance(node, dict) and "type" in node:
        yield node
        for key, val in node.items():
            if key in {"type", "loc", "file", "raw", "operator", "kind", "name"}:
                continue
            yield from walk(val)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


def callee_name(callee: dict[str, Any] | None) -> str | None:
    if not isinstance(callee, dict):
        return None
    typ = callee.get("type")
    if typ == "Identifier":
        return str(callee.get("name") or "")
    if typ == "MemberExpression" and not callee.get("computed"):
        prop = callee.get("property") or {}
        if prop.get("type") == "Identifier":
            obj = callee_name(callee.get("object"))
            return f"{obj}.{prop.get('name')}" if obj else str(prop.get("name"))
    return None


def is_filter_boolean(call: dict[str, Any]) -> bool:
    callee = call.get("callee") or {}
    if callee.get("type") != "MemberExpression":
        return False
    prop = callee.get("property") or {}
    if prop.get("type") != "Identifier" or prop.get("name") != "filter":
        return False
    args = call.get("arguments") or []
    if len(args) != 1:
        return False
    a0 = args[0]
    return a0.get("type") == "Identifier" and a0.get("name") == "Boolean"
