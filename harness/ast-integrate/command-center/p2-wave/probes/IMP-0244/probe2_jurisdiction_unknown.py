#!/usr/bin/env python3
"""Probe 2: jurisdictional uncertainty surfaces as UNKNOWN, never a confident verdict.

Both-states: an internal executable rule can return RULE_SATISFIED, so UNKNOWN
is not a constant. External statutes (EU-GDPR) stay UNKNOWN because this
program cannot support a confident legal answer. AST: evaluate() never
returns COMPLIANT/LAWFUL/LEGAL as a verdict.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center"))

from blueprints.legal_compliance import (  # noqa: E402
    BLUEPRINT_ID,
    FORBIDDEN_CONFIDENT_VERDICTS,
    VERDICT_RULE_SATISFIED,
    VERDICT_UNKNOWN,
    evaluate,
    jurisdiction_is_uncertain,
)
from blueprints.registry import load_all  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0244.json"
SRC = REPO / "command-center/blueprints/legal_compliance.py"
FIX_U = HERE / "fixtures/legal-uncertain.json"
FIX_I = HERE / "fixtures/legal-internal-ok.json"
FIX_G = HERE / "fixtures/legal-external-gdpr.json"
UNIT = "IMP-0244"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def load_fix(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_fn(tree: ast.Module) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "evaluate":
            return node
    return None


def ast_evaluate_returns_no_forbidden(src: str) -> bool:
    """No Return inside evaluate() uses a forbidden confident-verdict constant."""
    tree = ast.parse(src)
    fn = evaluate_fn(tree)
    if fn is None:
        return False
    forbidden = set(FORBIDDEN_CONFIDENT_VERDICTS)
    for node in ast.walk(fn):
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        for child in ast.walk(node.value):
            if isinstance(child, ast.Constant) and child.value in forbidden:
                return False
    return True


def ast_uncertain_returns_unknown(src: str) -> bool:
    tree = ast.parse(src)
    fn = evaluate_fn(tree)
    if fn is None:
        return False
    for stmt in fn.body:
        if not isinstance(stmt, ast.If):
            continue
        if "jurisdiction_is_uncertain" not in ast.dump(stmt.test):
            continue
        for inner in stmt.body:
            if not isinstance(inner, ast.Return) or inner.value is None:
                continue
            dumped = ast.dump(inner.value)
            if "VERDICT_UNKNOWN" in dumped or (
                "UNKNOWN" in dumped and "verdict" in dumped
            ):
                return True
        return False
    return False


def main() -> int:
    loaded = load_all()
    ids = [b.id for b in loaded]
    if BLUEPRINT_ID not in ids:
        return fail(f"legal-compliance not registered: {ids}")

    uncertain_subj = load_fix(FIX_U)
    internal_subj = load_fix(FIX_I)
    gdpr_subj = load_fix(FIX_G)

    if not jurisdiction_is_uncertain(uncertain_subj.get("jurisdiction")):
        return fail("uncertain fixture not classified uncertain")
    if jurisdiction_is_uncertain(internal_subj.get("jurisdiction")):
        return fail("internal fixture classified uncertain")

    d_u = evaluate(uncertain_subj)
    d_i = evaluate(internal_subj)
    d_g = evaluate(gdpr_subj)

    src = SRC.read_text(encoding="utf-8")
    ast_clean = ast_evaluate_returns_no_forbidden(src)
    ast_gate = ast_uncertain_returns_unknown(src)

    print(
        json.dumps(
            {
                "uncertain": d_u,
                "internal": d_i,
                "gdpr": d_g,
                "ast_evaluate_no_forbidden_verdict": ast_clean,
                "ast_uncertain_returns_unknown": ast_gate,
            },
            sort_keys=True,
        )
    )

    if d_u.get("verdict") != VERDICT_UNKNOWN:
        return fail(f"uncertain verdict={d_u.get('verdict')} want=UNKNOWN")
    if d_u.get("verdict") in FORBIDDEN_CONFIDENT_VERDICTS:
        return fail("uncertain produced a forbidden confident verdict")
    if d_u.get("confidence") != "none":
        return fail(f"uncertain confidence={d_u.get('confidence')} want=none")
    if d_i.get("verdict") != VERDICT_RULE_SATISFIED:
        return fail(f"internal verdict={d_i.get('verdict')} want=RULE_SATISFIED")
    if d_i.get("verdict") == VERDICT_UNKNOWN:
        return fail("internal also UNKNOWN; UNKNOWN is vacuous")
    if d_g.get("verdict") != VERDICT_UNKNOWN:
        return fail(
            f"GDPR verdict={d_g.get('verdict')} want=UNKNOWN (program cannot support)"
        )
    if not ast_clean:
        return fail("evaluate() returns a forbidden confident-verdict literal")
    if not ast_gate:
        return fail("evaluate() uncertain branch does not return UNKNOWN")

    if not ART.is_file():
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0244" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    legal = doc.get("legal_compliance") or {}
    if legal.get("uncertain_verdict") != VERDICT_UNKNOWN:
        return fail("receipt did not record uncertain UNKNOWN")
    if legal.get("internal_verdict") != VERDICT_RULE_SATISFIED:
        return fail("receipt did not record internal RULE_SATISFIED")
    if legal.get("gdpr_verdict") != VERDICT_UNKNOWN:
        return fail("receipt did not record GDPR UNKNOWN")

    print(
        "uncertain_unknown=True internal_rule_satisfied=True gdpr_unknown=True "
        f"ast_clean={ast_clean} ast_gate={ast_gate}"
    )
    print(
        "SUCCESS:IMP-0244-probe2 jurisdictional uncertainty is UNKNOWN, "
        "not a confident verdict"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
