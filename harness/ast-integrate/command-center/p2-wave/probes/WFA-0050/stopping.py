"""Boolean stopping grammar: AND / OR / NOT, comparisons, +/-, identifiers.

Estate-local evaluator used to re-express CrewAI/AutoGen termination.
Unknown identifiers raise; they are not treated as false.
"""
from __future__ import annotations

from typing import Any, Mapping

AND = "AND"
OR = "OR"
NOT = "NOT"
TRUE = "TRUE"
FALSE = "FALSE"

_CMP = {"==", "!=", ">=", "<=", ">", "<"}


class StopParseError(ValueError):
    pass


def tokenize(src: str) -> list[tuple[str, Any]]:
    s = src.strip()
    i = 0
    out: list[tuple[str, Any]] = []
    while i < len(s):
        ch = s[i]
        if ch.isspace():
            i += 1
            continue
        if s.startswith("==", i) or s.startswith("!=", i) or s.startswith(">=", i) or s.startswith("<=", i):
            out.append(("OP", s[i : i + 2]))
            i += 2
            continue
        if ch in "><":
            out.append(("OP", ch))
            i += 1
            continue
        if ch in "+-":
            out.append(("OP", ch))
            i += 1
            continue
        if ch == "(":
            out.append(("LPAREN", "("))
            i += 1
            continue
        if ch == ")":
            out.append(("RPAREN", ")"))
            i += 1
            continue
        if ch.isdigit() or (ch == "." and i + 1 < len(s) and s[i + 1].isdigit()):
            j = i
            while j < len(s) and (s[j].isdigit() or s[j] == "."):
                j += 1
            raw = s[i:j]
            out.append(("NUM", float(raw) if "." in raw else int(raw)))
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i
            while j < len(s) and (s[j].isalnum() or s[j] in "._"):
                j += 1
            word = s[i:j]
            upper = word.upper()
            if upper in {AND, OR, NOT, TRUE, FALSE}:
                out.append((upper, upper))
            else:
                out.append(("IDENT", word))
            i = j
            continue
        raise StopParseError(f"unexpected {ch!r} at {i}")
    out.append(("EOF", None))
    return out


class _P:
    def __init__(self, tokens: list[tuple[str, Any]], env: Mapping[str, Any]):
        self.toks = tokens
        self.i = 0
        self.env = env

    def peek(self) -> tuple[str, Any]:
        return self.toks[self.i]

    def eat(self, kind: str | None = None) -> tuple[str, Any]:
        tok = self.toks[self.i]
        if kind is not None and tok[0] != kind:
            raise StopParseError(f"expected {kind} got {tok}")
        self.i += 1
        return tok

    def parse(self) -> Any:
        v = self.or_expr()
        if self.peek()[0] != "EOF":
            raise StopParseError(f"trailing {self.peek()}")
        return v

    def or_expr(self) -> Any:
        v = self.and_expr()
        while self.peek()[0] == OR:
            self.eat(OR)
            r = self.and_expr()
            v = bool(v) or bool(r)
        return v

    def and_expr(self) -> Any:
        v = self.not_expr()
        while self.peek()[0] == AND:
            self.eat(AND)
            r = self.not_expr()
            v = bool(v) and bool(r)
        return v

    def not_expr(self) -> Any:
        if self.peek()[0] == NOT:
            self.eat(NOT)
            return not bool(self.not_expr())
        return self.cmp()

    def cmp(self) -> Any:
        left = self.add()
        kind, val = self.peek()
        if kind == "OP" and val in _CMP:
            self.eat()
            right = self.add()
            if val == "==":
                return left == right
            if val == "!=":
                return left != right
            if val == ">=":
                return left >= right
            if val == "<=":
                return left <= right
            if val == ">":
                return left > right
            if val == "<":
                return left < right
        return left

    def add(self) -> Any:
        v = self.unary()
        while self.peek()[0] == "OP" and self.peek()[1] in {"+", "-"}:
            op = self.eat()[1]
            r = self.unary()
            v = v + r if op == "+" else v - r
        return v

    def unary(self) -> Any:
        if self.peek()[0] == "OP" and self.peek()[1] == "-":
            self.eat()
            return -self.unary()
        return self.atom()

    def atom(self) -> Any:
        kind, val = self.peek()
        if kind == "IDENT":
            self.eat()
            if val not in self.env:
                raise StopParseError(f"unbound {val}")
            return self.env[val]
        if kind == "NUM":
            self.eat()
            return val
        if kind == TRUE:
            self.eat()
            return True
        if kind == FALSE:
            self.eat()
            return False
        if kind == "LPAREN":
            self.eat()
            v = self.or_expr()
            self.eat("RPAREN")
            return v
        raise StopParseError(f"atom {self.peek()}")


def evaluate(expr: str, env: Mapping[str, Any]) -> bool:
    return bool(_P(tokenize(expr), env).parse())


CREW_SEQUENTIAL_STOP = "tasks_completed >= task_count"
AUTOGEN_GROUPCHAT_STOP = (
    "is_termination_msg OR round_index == last_round OR "
    "speaker_selection_none OR reply_is_none"
)
PLANTED_AND_MUTATION = (
    "is_termination_msg AND round_index == last_round AND speaker_selection_none"
)


def bind_state(state: Mapping[str, Any]) -> dict[str, Any]:
    """Derive last_round from max_round so the two cannot desync."""
    max_round = int(state.get("max_round") or 0)
    return {
        "is_termination_msg": bool(state.get("is_termination_msg")),
        "speaker_selection_none": bool(state.get("speaker_selection_none")),
        "reply_is_none": bool(state.get("reply_is_none")),
        "round_index": int(state.get("round_index") or 0),
        "max_round": max_round,
        "last_round": max_round - 1,
        "tasks_completed": int(state.get("tasks_completed") or 0),
        "task_count": int(state.get("task_count") or 0),
        "agent_iter": int(state.get("agent_iter") or 0),
        "max_iter": int(state.get("max_iter") or 0),
    }


def grammar_stop(state: Mapping[str, Any]) -> bool:
    kind = state["kind"]
    env = bind_state(state)
    if kind == "crew-sequential":
        return evaluate(CREW_SEQUENTIAL_STOP, env)
    if kind == "autogen-groupchat":
        return evaluate(AUTOGEN_GROUPCHAT_STOP, env)
    raise StopParseError(f"unknown kind {kind}")
