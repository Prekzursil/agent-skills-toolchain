#!/usr/bin/env python3
"""Probe 1: FIRE on true fixture, SILENT on false, AND-not-OR, planted-bad reject."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from evaluate import bound_eval  # noqa: E402
from fixtures import FIXTURES, REQUIRED  # noqa: E402

OUT = (
    REPO
    / "command-center/design/council/"
    / "CNL-0078-executable-stopping-example-unique-ideas-100-and-completen.schema.json"
)
EXPR = "unique_ideas >= 100 AND completeness_score >= 0.90"


def load_artifact() -> dict:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        print("FAILED:CNL-0078-probe1 artifact missing")
        raise SystemExit(1)
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0078-probe1 self-declared {doc.get('state')}")
        raise SystemExit(1)
    text = OUT.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0078" not in text:
        print("FAILED:CNL-0078-probe1 sentinel-absent")
        raise SystemExit(1)
    if doc.get("verbatim_expression") != EXPR:
        print(f"FAILED:CNL-0078-probe1 expression drifted {doc.get('verbatim_expression')!r}")
        raise SystemExit(1)
    return doc


def main() -> int:
    doc = load_artifact()
    cases = [
        ("fire", "FIRE", True),
        ("silent_incomplete", "SILENT", False),
        ("silent_low_unique", "SILENT", False),
        ("planted_bad", "SILENT", False),
    ]
    lines = []
    fail = False
    for name, verdict, fired in cases:
        run = bound_eval(FIXTURES[name](), REQUIRED)
        rec = (doc.get("fixture_runs") or {}).get(name) or {}
        match = (
            run["verdict"] == verdict
            and run["fired"] is fired
            and rec.get("verdict") == verdict
            and rec.get("unique_ideas") == run["unique_ideas"]
            and rec.get("completeness_score") == run["completeness_score"]
        )
        line = (
            f"{name}: verdict={run['verdict']} fired={run['fired']} "
            f"unique_ideas={run['unique_ideas']} "
            f"completeness_score={run['completeness_score']} "
            f"n_raw={run['n_raw']} bound={run['bound']}"
        )
        lines.append(line)
        print(line)
        if rec.get("verbatim") != line:
            print(f"  artifact verbatim drifted for {name}")
            print(f"  artifact={rec.get('verbatim')!r}")
            fail = True
        if not match:
            print(f"  mismatch expected {verdict}/{fired} rec={rec}")
            fail = True

    low = bound_eval(FIXTURES["silent_low_unique"](), REQUIRED)
    inc = bound_eval(FIXTURES["silent_incomplete"](), REQUIRED)
    and_not_or = (
        low["completeness_score"] >= 0.90
        and low["unique_ideas"] < 100
        and low["verdict"] == "SILENT"
        and inc["unique_ideas"] >= 100
        and inc["completeness_score"] < 0.90
        and inc["verdict"] == "SILENT"
    )
    print(
        f"and_not_or={and_not_or} "
        f"low_unique={low['unique_ideas']}/{low['completeness_score']} "
        f"incomplete={inc['unique_ideas']}/{inc['completeness_score']}"
    )
    if not and_not_or:
        print("FAILED:CNL-0078-probe1 AND behaved as OR under partial evidence")
        return 1

    planted = bound_eval(FIXTURES["planted_bad"](), REQUIRED)
    neg = (
        planted["verdict"] == "SILENT"
        and planted["n_raw"] == 104
        and planted["unique_ideas"] == 8
        and planted["completeness_score"] < 0.90
    )
    print(
        "negative control recorded verbatim: "
        "On the planted-bad ledger of 8 mechanisms × 13 wording variants "
        f"(n_raw={planted['n_raw']}) the bound evaluator reports "
        f"unique_ideas={planted['unique_ideas']} completeness_score="
        f"{planted['completeness_score']} verdict={planted['verdict']}. "
        "The check rejects quota-filling by trivial variants (the state it is "
        "meant to reject) by staying SILENT rather than firing."
    )
    if not neg:
        print(f"FAILED:CNL-0078-probe1 planted-bad did not reject: {planted}")
        return 1
    if fail:
        print("FAILED:CNL-0078-probe1 fixture/artifact disagreement")
        return 1
    print("SUCCESS:CNL-0078-probe1 fire/silent/negative-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
