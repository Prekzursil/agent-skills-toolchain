#!/usr/bin/env python3
"""Named probe 1: promotion criteria, card schema, field-completeness.

Unit test required by IMP-0339. Also proves the maturity bar does not read
held-out quality labels (AST over the live module).
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE / "fixtures"))

from planted import EXPECTED_DROPPED, EXPECTED_PROMOTED, build_ideas  # noqa: E402
from tools.council.artifacts.option_cards import (  # noqa: E402
    CARD_REQUIRED_FIELDS,
    CHECK_ORDER,
    field_completeness_audit,
    inject_incomplete_card,
    promote,
    validate_card,
)

FORBIDDEN_ATTRS = frozenset(
    {
        "held_out_quality",
        "independent_quality",
        "actionability",
        "quality_rater",
        "downstream_utility",
    }
)
MODULE_PATH = REPO / "tools/council/artifacts/option_cards.py"


def assert_bar_ignores_held_out() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_ATTRS:
            hits.append(f"Name {node.id} line {node.lineno}")
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRS:
            hits.append(f"Attribute .{node.attr} line {node.lineno}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.endswith("quality_rater") or "quality_rater" in mod:
                hits.append(f"ImportFrom {mod} line {node.lineno}")
            for alias in node.names:
                if alias.name in FORBIDDEN_ATTRS:
                    hits.append(f"import {alias.name} line {node.lineno}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if "quality_rater" in alias.name:
                    hits.append(f"Import {alias.name} line {node.lineno}")
    if hits:
        raise AssertionError("maturity bar reads held-out rater state: " + "; ".join(hits))


def main() -> int:
    assert_bar_ignores_held_out()
    ideas = build_ideas()
    if len(ideas) != 24:
        print(f"FAILED:IMP-0339-probe1 planted n={len(ideas)} want=24")
        return 1
    result = promote(ideas, evidence_root=REPO)
    promoted_ids = [c["source_idea_id"] for c in result.cards]
    dropped_ids = [d["idea_id"] for d in result.dropped]
    if promoted_ids != EXPECTED_PROMOTED:
        print("FAILED:IMP-0339-probe1 promoted ids mismatch")
        print(json.dumps({"got": promoted_ids, "want": EXPECTED_PROMOTED}, indent=2))
        return 1
    if dropped_ids != sorted(EXPECTED_DROPPED):
        print("FAILED:IMP-0339-probe1 dropped ids mismatch")
        print(json.dumps({"got": dropped_ids, "want": sorted(EXPECTED_DROPPED)}, indent=2))
        return 1
    rate = result.promotion_rate
    if abs(rate - (8 / 24)) > 1e-12:
        print(f"FAILED:IMP-0339-probe1 promotion_rate={rate} want=8/24")
        return 1
    if rate in (0.0, 1.0):
        print(f"FAILED:IMP-0339-probe1 bar is not selective rate={rate}")
        return 1

    for card in result.cards:
        missing = [f for f in CARD_REQUIRED_FIELDS if f not in card]
        if missing:
            print(f"FAILED:IMP-0339-probe1 card {card.get('card_id')} missing {missing}")
            return 1
        errors = validate_card(card)
        if errors:
            print(f"FAILED:IMP-0339-probe1 schema {card.get('card_id')} {errors}")
            return 1

    audit = field_completeness_audit(result.cards)
    if not audit["all_complete"] or audit["n_incomplete"] != 0:
        print("FAILED:IMP-0339-probe1 completeness audit")
        print(json.dumps(audit, indent=2)[:2000])
        return 1

    reasons = {d["drop_reason"] for d in result.dropped}
    if not set(CHECK_ORDER).issubset(reasons):
        print(f"FAILED:IMP-0339-probe1 drop reasons {sorted(reasons)} missing a bar check")
        return 1

    fired = []
    for field_name in CARD_REQUIRED_FIELDS:
        broken = inject_incomplete_card(result.cards[0], drop_field=field_name)
        errs = validate_card(broken)
        if not errs:
            print(f"FAILED:IMP-0339-probe1 completeness silent after dropping {field_name}")
            return 1
        fired.append({"dropped_field": field_name, "errors": errs})

    payload = {
        "probe": "probe1-promotion-schema",
        "unit_id": "IMP-0339",
        "n_raw": result.n_raw,
        "n_promoted": result.n_promoted,
        "promotion_rate": rate,
        "dropped_by_reason": result.dropped_by_reason(),
        "promoted_ids": promoted_ids,
        "completeness": {
            "n_cards": audit["n_cards"],
            "n_complete": audit["n_complete"],
            "n_incomplete": audit["n_incomplete"],
            "all_complete": audit["all_complete"],
        },
        "negative_control_fired": fired,
        "bar_ignores_held_out": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"promotion_rate={rate:.6f} n_promoted={result.n_promoted}/{result.n_raw} "
        f"completeness_fail={audit['n_incomplete']} drop_reasons={result.dropped_by_reason()}"
    )
    print("SUCCESS:IMP-0339-probe1 promotion criteria, card schema, field-completeness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
