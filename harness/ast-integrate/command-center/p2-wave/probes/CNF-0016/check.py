#!/usr/bin/env python3
"""Shared checkers: no blank rows, sufficiency math, both-states, schema garbage."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import schema_local as SL  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/repro-report.schema.json"
OUT_REL = "command-center/confirmation/CNF-0016-repro-sufficiency.json"
SUFFICIENT_ID = "P0-CNF0016-DIVZERO"
INSUFFICIENT_IDS = ("P0-CNF0016-ENV", "P0-CNF0016-CWD", "P0-CNF0016-BLANK")
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def load_schema() -> dict:
    return json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))


def validator():
    return SL.validator()


def report_of(doc: dict) -> dict:
    rep = doc.get("report")
    return rep if isinstance(rep, dict) else {}


def recipes_of(doc: dict) -> list[dict]:
    """Recipe rows live under report (receipt_core additionalProperties=false)."""
    rep = report_of(doc)
    for key in ("recipes", "defects"):
        rows = rep.get(key)
        if isinstance(rows, list) and rows:
            return [r for r in rows if isinstance(r, dict)]
    rows = doc.get("defects")
    if isinstance(rows, list):
        # Top-level defects are receipt_core defect objects, not recipe rows.
        recipe_like = [
            r
            for r in rows
            if isinstance(r, dict) and "verdict" in r
        ]
        if recipe_like:
            return recipe_like
    return []


def sufficiency_obj(doc: dict) -> dict:
    rep = report_of(doc)
    got = rep.get("sufficiency") or doc.get("sufficiency") or {}
    return got if isinstance(got, dict) else {}


def record_defects_of(doc: dict) -> list[dict]:
    rep = report_of(doc)
    rows = rep.get("record_defects") or doc.get("record_defects") or []
    return [r for r in rows if isinstance(r, dict)]


def validate_doc(doc: dict) -> list[str]:
    return SL.errors(doc)


def schema_rejects_garbage() -> tuple[bool, str]:
    v = validator()
    garbage = (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"x": "x" * 2000},
    )
    for g in garbage:
        if v.is_valid(g):
            return False, f"schema accepted garbage {g!r:.80}"
    return True, "3/3 garbage rejected"


def no_blank_rows(defects: list[dict]) -> tuple[bool, str]:
    if not defects:
        return False, "empty defects array (vacuous)"
    for i, row in enumerate(defects):
        ident = str(row.get("id") or "").strip()
        if not ident:
            return False, f"blank id at index {i}"
        verdict = str(row.get("verdict") or "")
        if verdict not in {"PASS", "INSUFFICIENT"}:
            return False, f"{ident} blank/unknown verdict {verdict!r}"
        observed = str(row.get("observed_output") or "").strip()
        if not observed:
            return False, f"{ident} blank observed_output"
        if verdict == "PASS":
            cmds = [c for c in (row.get("commands") or []) if str(c).strip()]
            if not cmds:
                return False, f"{ident} PASS without verbatim commands"
            if row.get("missing_step") not in (None,):
                return False, f"{ident} PASS must have missing_step=null"
        else:
            step = str(row.get("missing_step") or "").strip()
            if not step:
                return False, f"{ident} INSUFFICIENT without named missing step"
    return True, f"no blank rows n={len(defects)}"


def sufficiency_from_rows(defects: list[dict]) -> dict:
    attempted = len(defects)
    pass_count = sum(1 for r in defects if r.get("verdict") == "PASS")
    insufficient_count = attempted - pass_count
    rate = (pass_count / attempted) if attempted else 0.0
    return {
        "attempted": attempted,
        "pass_count": pass_count,
        "insufficient_count": insufficient_count,
        "rate": rate,
        "computed_not_asserted": True,
    }


def sufficiency_matches(doc: dict) -> tuple[bool, str]:
    got = sufficiency_obj(doc)
    want = sufficiency_from_rows(recipes_of(doc))
    for key in ("attempted", "pass_count", "insufficient_count"):
        if got.get(key) != want[key]:
            return False, f"sufficiency.{key} got={got.get(key)} want={want[key]}"
    if not got.get("computed_not_asserted"):
        return False, "sufficiency.computed_not_asserted is not true"
    try:
        rate = float(got.get("rate"))
    except (TypeError, ValueError):
        return False, "sufficiency.rate unreadable"
    if abs(rate - want["rate"]) > 1e-9:
        return False, f"sufficiency.rate got={rate} want={want['rate']}"
    return True, f"rate={want['rate']} = {want['pass_count']}/{want['attempted']}"


def both_states(defects: list[dict]) -> tuple[bool, str]:
    by_id = {r.get("id"): r for r in defects}
    good = by_id.get(SUFFICIENT_ID)
    if not good or good.get("verdict") != "PASS":
        return False, f"{SUFFICIENT_ID} must PASS on verbatim recipe"
    if not (good.get("commands") or []):
        return False, f"{SUFFICIENT_ID} PASS missing commands"
    if good.get("verbatim") is not True:
        return False, f"{SUFFICIENT_ID} was not a zero-improvisation run"
    bad_ok = 0
    for iid in INSUFFICIENT_IDS:
        row = by_id.get(iid)
        if not row:
            return False, f"missing insufficient control {iid}"
        if row.get("verdict") != "INSUFFICIENT":
            return False, f"{iid} must be INSUFFICIENT, got {row.get('verdict')}"
        if not str(row.get("missing_step") or "").strip():
            return False, f"{iid} missing named step"
        bad_ok += 1
    if bad_ok < 1:
        return False, "no insufficient control"
    return True, f"both-states: {SUFFICIENT_ID}=PASS vs {bad_ok} INSUFFICIENT"


def record_defects_ok(doc: dict) -> tuple[bool, str]:
    defects = recipes_of(doc)
    records = record_defects_of(doc)
    insufficient = [d for d in defects if d.get("verdict") == "INSUFFICIENT"]
    if len(records) != len(insufficient):
        return False, f"record_defects {len(records)} != insufficient {len(insufficient)}"
    src = {r.get("source_defect") for r in records}
    for d in insufficient:
        if d.get("id") not in src:
            return False, f"no RECORD defect filed for {d.get('id')}"
    for r in records:
        if r.get("against") != "RECORD":
            return False, f"{r.get('id')} against={r.get('against')} want=RECORD"
        if "CODE" in str(r.get("against") or "").upper() and r.get("against") != "RECORD":
            return False, "record defect filed against CODE"
    return True, f"filed {len(records)} defects against RECORD"


def reject_blank_mutant(doc: dict) -> tuple[bool, str]:
    """Blank recipe rows must fail the unit invariant (no blank rows).

    Recipe rows live under report, which the receipt schema does not constrain
    beyond kind/observations/control_ids. The unit's own no-blank-rows checker
    is the load-bearing control; the schema still rejects envelope garbage.
    """
    rows = recipes_of(doc)
    if not rows:
        return False, "no defects to mutate"
    mutant = copy.deepcopy(rows)
    mutant[0]["verdict"] = ""
    ok, _ = no_blank_rows(mutant)
    if ok:
        return False, "blank verdict mutant accepted"
    mutant2 = copy.deepcopy(rows)
    stripped = False
    for row in mutant2:
        if row.get("verdict") == "INSUFFICIENT":
            row["missing_step"] = ""
            stripped = True
            break
    if not stripped:
        return False, "no INSUFFICIENT row to strip"
    ok2, _ = no_blank_rows(mutant2)
    if ok2:
        return False, "empty missing_step mutant accepted"
    return True, "blank-row mutants rejected"


def load_artifact() -> dict:
    path = REPO / OUT_REL
    if not path.is_file() or path.stat().st_size <= 0:
        raise FileNotFoundError(OUT_REL)
    return json.loads(path.read_text(encoding="utf-8"))
