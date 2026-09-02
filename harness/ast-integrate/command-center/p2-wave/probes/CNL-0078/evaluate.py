#!/usr/bin/env python3
"""Evaluate unique_ideas >= 100 AND completeness_score >= 0.90 with identity bind."""
from __future__ import annotations

from typing import Any

from a10_grammar import CNL_0078_EXPR, eval_node, parse
from metrics import (
    IDENTITY_CANONICAL,
    IDENTITY_RAW,
    completeness_score,
    unique_ideas,
)

EXPR = CNL_0078_EXPR


def evaluate(
    ledger: list[dict[str, Any]],
    required: dict[str, list[str]],
    *,
    unique_identity: str = IDENTITY_CANONICAL,
    completeness_identity: str = IDENTITY_CANONICAL,
    completeness_gamed: bool = False,
    expr: str = EXPR,
) -> dict[str, Any]:
    ast = parse(expr)
    u = unique_ideas(ledger, unique_identity)
    c = completeness_score(
        ledger, required, completeness_identity, gamed_fields=completeness_gamed
    )
    bound = (
        unique_identity == completeness_identity == IDENTITY_CANONICAL
        and not completeness_gamed
        and u["identity_sha256"] == c["identity_sha256"]
    )
    naive_env = {
        "unique_ideas": u["count"],
        "completeness_score": c["score"],
    }
    naive_true = eval_node(ast, naive_env)
    if not bound:
        verdict = "UNBOUND"
        fired = False
    else:
        fired = bool(naive_true)
        verdict = "FIRE" if fired else "SILENT"
    return {
        "expression": expr,
        "verdict": verdict,
        "fired": fired,
        "naive_and": naive_true,
        "bound": bound,
        "unique_ideas": u["count"],
        "completeness_score": c["score"],
        "completeness_parts": c["parts"],
        "unique_identity": unique_identity,
        "completeness_identity": completeness_identity,
        "unique_identity_sha256": u["identity_sha256"],
        "completeness_identity_sha256": c["identity_sha256"],
        "n_raw": u["n_raw"],
        "corroboration": u.get("corroboration") or [],
        "completeness_gamed": completeness_gamed,
        "required": {k: list(v) for k, v in required.items()},
    }


def bound_eval(ledger: list[dict[str, Any]], required: dict[str, list[str]]) -> dict[str, Any]:
    return evaluate(
        ledger,
        required,
        unique_identity=IDENTITY_CANONICAL,
        completeness_identity=IDENTITY_CANONICAL,
        completeness_gamed=False,
    )


def mixed_unbound(
    ledger: list[dict[str, Any]], required: dict[str, list[str]]
) -> dict[str, Any]:
    """Lenient unique (raw) + gamed completeness — the disagree-and-satisfiable pairing."""
    return evaluate(
        ledger,
        required,
        unique_identity=IDENTITY_RAW,
        completeness_identity=IDENTITY_RAW,
        completeness_gamed=True,
    )
