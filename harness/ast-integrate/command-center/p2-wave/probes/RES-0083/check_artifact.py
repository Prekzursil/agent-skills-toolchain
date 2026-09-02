#!/usr/bin/env python3
"""Structural checks for command-center/research/RES-0083.json."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Callable

from scoring import brier_binary, mellers_worked_example

REPO = Path(__file__).resolve().parents[4]
ART = REPO / "command-center/research/RES-0083.json"
SENTINEL = "SUCCESS:RES-0083"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
REQUIRED_RULE_IDS = {
    "brier-quadratic",
    "log-score",
    "extremizing-karmarkar",
    "recency-top20-in-bundle",
    "team-vs-independent",
}


def load_doc(path: Path | None = None) -> dict:
    return json.loads((path or ART).read_text(encoding="utf-8"))


def fail(msg: str) -> None:
    raise AssertionError(msg)


def rule_table(doc: dict) -> list[dict]:
    table = doc.get("rule_table")
    if not isinstance(table, list) or len(table) < 5:
        n = len(table) if isinstance(table, list) else "n/a"
        fail(f"rule_table too small: {type(table).__name__} n={n}")
    return table


def named_resolution(row: dict) -> str:
    src = str(row.get("resolution_source") or "").strip()
    if not src or src.upper() in {"NONE", "NA", "N/A", "UNNAMED", "UNKNOWN"}:
        fail(f"row {row.get('id')} missing named resolution_source")
    return src


def check_sentinel_and_state(doc: dict) -> None:
    blob = json.dumps(doc, ensure_ascii=False)
    if SENTINEL not in blob:
        fail("sentinel SUCCESS:RES-0083 absent")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        fail(f"self-declared {st}")
    if st != "SUCCESS":
        fail(f"state {st} is not SUCCESS")


def check_rule_table(doc: dict) -> list[str]:
    table = rule_table(doc)
    ids = []
    for i, row in enumerate(table):
        if not isinstance(row, dict):
            fail(f"rule_table[{i}] not an object")
        rid = str(row.get("id") or "")
        if not rid:
            fail(f"rule_table[{i}] missing id")
        named_resolution(row)
        if not str(row.get("resolution_horizon") or "").strip():
            fail(f"row {rid} missing resolution_horizon")
        rec = str(row.get("recommendation") or "")
        tier = str(row.get("evidence_tier") or "")
        if rec == "RECOMMENDED" and tier == "E3":
            fail(f"row {rid} E3 cannot promote (recommendation=RECOMMENDED)")
        if rec == "RECOMMENDED":
            effect = row.get("effect_size")
            baseline = row.get("baseline")
            if not isinstance(effect, dict) or effect.get("value") is None:
                fail(f"row {rid} RECOMMENDED without effect_size.value")
            if not isinstance(baseline, dict) or baseline.get("value") is None:
                fail(f"row {rid} RECOMMENDED without baseline.value")
        ids.append(rid)
    missing = REQUIRED_RULE_IDS - set(ids)
    if missing:
        fail(f"rule_table missing required ids {sorted(missing)}")
    return ids


def check_unscoreable(doc: dict) -> dict:
    u = doc.get("unscoreable_output_type")
    if not isinstance(u, dict):
        fail("unscoreable_output_type missing")
    for k in ("id", "name", "why_unscoreable", "council_examples", "contrast_scoreable"):
        if not u.get(k):
            fail(f"unscoreable_output_type.{k} empty")
    examples = u.get("council_examples")
    if not isinstance(examples, list) or len(examples) < 1:
        fail("unscoreable_output_type.council_examples empty")
    blob = json.dumps(u).lower()
    if u.get("is_control") is not True and "control" not in blob:
        fail("unscoreable_output_type is not marked as the required control")
    return u


def check_e3_cannot_promote(doc: dict) -> None:
    found_e3 = False
    for row in rule_table(doc):
        if str(row.get("evidence_tier") or "") == "E3":
            found_e3 = True
            if str(row.get("recommendation") or "") == "RECOMMENDED":
                fail(f"E3 row {row.get('id')} was promoted")
    if not found_e3:
        fail("no E3 row recorded (need a headline-without-baseline control)")


def check_mellers_arithmetic() -> None:
    ex = mellers_worked_example()
    if abs(ex["brier_if_occurs"] - ex["expected_hit"]) > 1e-12:
        fail(f"Mellers hit example {ex['brier_if_occurs']} != {ex['expected_hit']}")
    if abs(ex["brier_if_not"] - ex["expected_miss"]) > 1e-12:
        fail(f"Mellers miss example {ex['brier_if_not']} != {ex['expected_miss']}")
    if abs(brier_binary(0.5, 1) - 0.5) > 1e-12:
        fail("coin-flip Brier is not 0.5 under two-component form")


def mutant_missing_resolution(doc: dict) -> dict:
    m = copy.deepcopy(doc)
    m["rule_table"][0]["resolution_source"] = ""
    return m


def mutant_e3_promoted(doc: dict) -> dict:
    m = copy.deepcopy(doc)
    for row in m["rule_table"]:
        if str(row.get("evidence_tier") or "") == "E3":
            row["recommendation"] = "RECOMMENDED"
            return m
    fail("no E3 row to promote in mutant")
    return m


def mutant_drop_unscoreable(doc: dict) -> dict:
    m = copy.deepcopy(doc)
    m["unscoreable_output_type"] = {}
    return m


def expect_fail(fn: Callable[[dict], Any], doc: dict, label: str) -> None:
    try:
        fn(doc)
    except AssertionError:
        return
    fail(f"{label} did not go red")


def check_live(doc: dict | None = None) -> dict[str, Any]:
    d = doc if doc is not None else load_doc()
    check_sentinel_and_state(d)
    ids = check_rule_table(d)
    u = check_unscoreable(d)
    check_e3_cannot_promote(d)
    check_mellers_arithmetic()
    expect_fail(check_rule_table, mutant_missing_resolution(d), "missing-resolution mutant")
    expect_fail(check_e3_cannot_promote, mutant_e3_promoted(d), "E3-promoted mutant")
    expect_fail(check_unscoreable, mutant_drop_unscoreable(d), "drop-unscoreable mutant")
    return {
        "ok": True,
        "n_rules": len(ids),
        "rule_ids": ids,
        "unscoreable_id": u.get("id"),
    }
