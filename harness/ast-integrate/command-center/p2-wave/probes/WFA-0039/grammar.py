"""Boolean stopping grammar: ANY/ALL/NOT over named predicates.

Two mechanically independent evaluators:
  eval_normalized — recursive walk of the ALL/ANY/NOT tree
  eval_direct     — recursive-descent over tokens against a state, no AST

The six spec-named expressions (catalog CNL-0078..CNL-0083 /
_USER-PROMPTS.md:10937-10942) are the fixed conformance set.
"""
from __future__ import annotations

import re
from typing import Any

AND, OR, NOT = "AND", "OR", "NOT"
ALL, ANY = "ALL", "ANY"
PRED = "PRED"
LP, RP, NAME, CMP, EOF = "LP", "RP", "NAME", "CMP", "EOF"

CMP_OPS = (">=", "<=", "!=", "==", ">", "<")

# Catalog CNL-0078..CNL-0083 titles, mapped to spec lines 10937-10942.
SPEC_EXPRESSIONS: tuple[tuple[str, int, str], ...] = (
    (
        "spec-10937",
        10937,
        "unique_ideas >= 100 AND completeness_score >= 0.90",
    ),
    (
        "spec-10938",
        10938,
        "consensus >= 0.95 AND no_new_objection_rounds >= 2",
    ),
    (
        "spec-10939",
        10939,
        "unanimity == true OR max_rounds == 12",
    ),
    (
        "spec-10940",
        10940,
        "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0",
    ),
    (
        "spec-10941",
        10941,
        "evidence_saturation == true OR time_minutes >= 180",
    ),
    (
        "spec-10942",
        10942,
        "proof_of_impossibility == true",
    ),
)

# CNL-0076 runtime metric unique_ideas binds the spec metric unique_ideas.
METRIC_ALIASES = {
    "unique_ideas": "unique_ideas",
}


class ParseError(ValueError):
    pass


class EvalError(ValueError):
    pass


_TOKEN_RE = re.compile(
    r"""
    \s*
    (
        >=|<=|!=|==|>|<
      | \( | \)
      | true | false | TRUE | FALSE
      | AND | OR | NOT
      | [A-Za-z_][A-Za-z0-9_]*
      | -?\d+\.\d+
      | -?\d+
    )
    """,
    re.VERBOSE,
)


def tokenize(source: str) -> list[tuple[str, Any]]:
    text = (source or "").strip()
    if not text:
        raise ParseError("empty-expression")
    tokens: list[tuple[str, Any]] = []
    pos = 0
    n = len(text)
    while pos < n:
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise ParseError(f"untokenizable-at:{pos}:{text[pos:pos + 16]!r}")
        raw = m.group(1)
        pos = m.end()
        up = raw.upper()
        if up in {AND, OR, NOT}:
            tokens.append((up, up))
        elif raw in CMP_OPS:
            tokens.append(("CMP", raw))
        elif raw == "(":
            tokens.append(("LP", raw))
        elif raw == ")":
            tokens.append(("RP", raw))
        elif up in {"TRUE", "FALSE"}:
            tokens.append(("BOOL", up == "TRUE"))
        elif re.fullmatch(r"-?\d+\.\d+", raw):
            tokens.append(("NUM", float(raw)))
        elif re.fullmatch(r"-?\d+", raw):
            tokens.append(("NUM", int(raw)))
        else:
            tokens.append(("NAME", raw))
    tokens.append(("EOF", None))
    return tokens


def _pred_name(metric: str, rel: str, value: Any) -> str:
    val = str(value).replace(".", "p").replace("-", "m")
    rel_key = {
        ">=": "ge",
        "<=": "le",
        "==": "eq",
        "!=": "ne",
        ">": "gt",
        "<": "lt",
    }[rel]
    return f"{metric}_{rel_key}_{val}"


def parse(source: str) -> dict[str, Any]:
    """Parse infix AND/OR/NOT/comparisons into an operator AST."""
    tokens = tokenize(source)
    i = 0

    def peek() -> str:
        return tokens[i][0]

    def eat(kind: str | None = None) -> tuple[str, Any]:
        nonlocal i
        tok = tokens[i]
        if kind and tok[0] != kind:
            raise ParseError(f"expected-{kind}-got-{tok[0]}")
        i += 1
        return tok

    def parse_or() -> dict[str, Any]:
        node = parse_and()
        parts = [node]
        while peek() == OR:
            eat(OR)
            parts.append(parse_and())
        if len(parts) == 1:
            return parts[0]
        return {"op": OR, "args": parts}

    def parse_and() -> dict[str, Any]:
        node = parse_not()
        parts = [node]
        while peek() == AND:
            eat(AND)
            parts.append(parse_not())
        if len(parts) == 1:
            return parts[0]
        return {"op": AND, "args": parts}

    def parse_not() -> dict[str, Any]:
        if peek() == NOT:
            eat(NOT)
            return {"op": NOT, "arg": parse_not()}
        return parse_primary()

    def parse_primary() -> dict[str, Any]:
        if peek() == LP:
            eat(LP)
            node = parse_or()
            eat(RP)
            return node
        if peek() == NAME:
            name = eat(NAME)[1]
            if peek() == CMP:
                rel = eat("CMP")[1]
                kind, val = eat()
                if kind not in {"NUM", "BOOL", "NAME"}:
                    raise ParseError(f"bad-cmp-rhs:{kind}")
                if kind == "NAME":
                    val = str(val)
                return {
                    "op": "CMP",
                    "metric": name,
                    "rel": rel,
                    "value": val,
                }
            raise ParseError(f"bare-name-not-comparison:{name}")
        raise ParseError(f"unexpected-token:{peek()}")

    tree = parse_or()
    if peek() != "EOF":
        raise ParseError(f"trailing-tokens:{tokens[i]}")
    return tree


def normalize(ast: dict[str, Any]) -> dict[str, Any]:
    """Map AND/OR/NOT/CMP onto ALL/ANY/NOT over named predicates."""
    op = ast["op"]
    if op == AND:
        return {"op": ALL, "args": [normalize(a) for a in ast["args"]]}
    if op == OR:
        return {"op": ANY, "args": [normalize(a) for a in ast["args"]]}
    if op == NOT:
        return {"op": NOT, "arg": normalize(ast["arg"])}
    if op == "CMP":
        metric = ast["metric"]
        rel = ast["rel"]
        value = ast["value"]
        return {
            "op": PRED,
            "name": _pred_name(metric, rel, value),
            "metric": metric,
            "rel": rel,
            "value": value,
        }
    raise ParseError(f"unknown-ast-op:{op}")


def parse_normalized(source: str) -> dict[str, Any]:
    return normalize(parse(source))


def _cmp(left: Any, rel: str, right: Any) -> bool:
    if rel == ">=":
        return left >= right
    if rel == "<=":
        return left <= right
    if rel == ">":
        return left > right
    if rel == "<":
        return left < right
    if rel == "==":
        if isinstance(right, bool):
            return bool(left) is right
        if isinstance(right, str) and isinstance(left, str):
            return left == right
        return left == right
    if rel == "!=":
        return not _cmp(left, "==", right)
    raise EvalError(f"unknown-rel:{rel}")


def _lookup(state: dict[str, Any], metric: str) -> Any:
    if metric in state:
        return state[metric]
    alias = METRIC_ALIASES.get(metric)
    if alias and alias in state:
        return state[alias]
    # reverse alias
    for src, dst in METRIC_ALIASES.items():
        if dst == metric and src in state:
            return state[src]
    raise EvalError(f"unbound-metric:{metric}")


def eval_normalized(node: dict[str, Any], state: dict[str, Any]) -> bool:
    op = node["op"]
    if op == ALL:
        return all(eval_normalized(a, state) for a in node["args"])
    if op == ANY:
        return any(eval_normalized(a, state) for a in node["args"])
    if op == NOT:
        return not eval_normalized(node["arg"], state)
    if op == PRED:
        left = _lookup(state, node["metric"])
        return _cmp(left, node["rel"], node["value"])
    raise EvalError(f"unknown-norm-op:{op}")


def eval_direct(source: str, state: dict[str, Any]) -> bool:
    """Independent evaluator: recursive descent that never builds an AST."""
    tokens = tokenize(source)
    i = 0

    def peek() -> str:
        return tokens[i][0]

    def eat(kind: str | None = None) -> tuple[str, Any]:
        nonlocal i
        tok = tokens[i]
        if kind and tok[0] != kind:
            raise EvalError(f"direct-expected-{kind}-got-{tok[0]}")
        i += 1
        return tok

    def ev_or() -> bool:
        acc = ev_and()
        while peek() == OR:
            eat(OR)
            rhs = ev_and()
            acc = acc or rhs
        return acc

    def ev_and() -> bool:
        acc = ev_not()
        while peek() == AND:
            eat(AND)
            rhs = ev_not()
            acc = acc and rhs
        return acc

    def ev_not() -> bool:
        if peek() == NOT:
            eat(NOT)
            return not ev_not()
        return ev_primary()

    def ev_primary() -> bool:
        if peek() == LP:
            eat(LP)
            v = ev_or()
            eat(RP)
            return v
        if peek() == NAME:
            metric = eat(NAME)[1]
            rel = eat("CMP")[1]
            kind, val = eat()
            if kind == "NAME":
                val = str(val)
            elif kind not in {"NUM", "BOOL"}:
                raise EvalError(f"direct-bad-rhs:{kind}")
            left = _lookup(state, metric)
            return _cmp(left, rel, val)
        raise EvalError(f"direct-unexpected:{peek()}")

    result = ev_or()
    if peek() != "EOF":
        raise EvalError("direct-trailing-tokens")
    return result


def evaluate_pair(source: str, state: dict[str, Any]) -> dict[str, Any]:
    norm = parse_normalized(source)
    a = eval_normalized(norm, state)
    b = eval_direct(source, state)
    return {
        "normalized": a,
        "direct": b,
        "agree": a is b,
        "tree": norm,
    }


def synthetic_states() -> list[dict[str, Any]]:
    """Twenty deterministic states spanning the six spec metrics."""
    ideas = [0, 40, 99, 100, 140]
    complete = [0.0, 0.5, 0.89, 0.90, 1.0]
    cons = [0.0, 0.5, 0.94, 0.95, 1.0]
    obj_rounds = [0, 1, 2, 3, 5]
    una = [False, False, True, True, False]
    max_r = [1, 8, 12, 12, 20]
    gate = ["FAIL", "FAIL", "PASS", "PASS", "FAIL"]
    unresolved = [3, 1, 0, 0, 2]
    sat = [False, False, True, True, False]
    minutes = [0, 60, 179, 180, 240]
    proof = [False, False, False, True, True]
    rounds = [0, 4, 8, 12, 16]
    stages = [0, 1, 2, 3, 4]
    states: list[dict[str, Any]] = []
    for i in range(20):
        k = i % 5
        j = (i // 5) % 5
        n_ideas = ideas[k]
        states.append(
            {
                "id": f"S{i:02d}",
                "unique_ideas": n_ideas,
                "completeness_score": complete[j],
                "consensus": cons[k],
                "no_new_objection_rounds": obj_rounds[j],
                "unanimity": una[k],
                "max_rounds": max_r[j],
                "quality_gate": gate[k],
                "unresolved_load_bearing_counterexample": unresolved[j],
                "evidence_saturation": sat[k],
                "time_minutes": minutes[j],
                "proof_of_impossibility": proof[k],
                "rounds": rounds[k],
                "stages": stages[k],
            }
        )
    return states


def differential(source: str, states: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    states = states or synthetic_states()
    rows = []
    disagreements = 0
    truths = 0
    errors: list[str] = []
    tree = None
    for st in states:
        try:
            pair = evaluate_pair(source, st)
        except (ParseError, EvalError) as exc:
            errors.append(f"{st.get('id')}:{exc}")
            continue
        tree = pair["tree"]
        if pair["normalized"]:
            truths += 1
        if not pair["agree"]:
            disagreements += 1
        rows.append(
            {
                "state_id": st.get("id"),
                "normalized": pair["normalized"],
                "direct": pair["direct"],
                "agree": pair["agree"],
            }
        )
    n = len(rows)
    degenerate = None
    if n and not errors and disagreements == 0:
        if truths == 0:
            degenerate = "always-false"
        elif truths == n:
            degenerate = "always-true"
    return {
        "source": source,
        "n_states": n,
        "n_true": truths,
        "n_false": n - truths,
        "disagreements": disagreements,
        "errors": errors,
        "degenerate": degenerate,
        "tree": tree,
        "rows": rows,
    }


def spec_conformance(states: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    states = states or synthetic_states()
    out = []
    for sid, line, source in SPEC_EXPRESSIONS:
        diff = differential(source, states)
        out.append(
            {
                "id": sid,
                "spec_line": line,
                "source": source,
                "parsed": diff["tree"] is not None and not diff["errors"],
                "disagreements": diff["disagreements"],
                "degenerate": diff["degenerate"],
                "n_true": diff["n_true"],
                "n_false": diff["n_false"],
                "tree": diff["tree"],
                "errors": diff["errors"],
            }
        )
    return out
