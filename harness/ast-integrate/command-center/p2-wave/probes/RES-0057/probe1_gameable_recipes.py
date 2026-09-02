#!/usr/bin/env python3
"""Probe 1: every GAMEABLE/MIXED row names a cheap-satisfaction recipe.

Re-hashes captures, requires dual rails, and proves a mutant that strips
recipes goes red (both-states).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from contract import (  # noqa: E402
    ART_REL,
    GAMEABLE_GRADES,
    REPO,
    evaluate_all,
    load_json,
    mutant_strip_recipes,
    verify_artifact,
    verify_captures,
    verify_taxonomy,
)
from taxonomy import SENTINEL, gameable_rows  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:RES-0057-probe1 {msg}")
    return 1


def main() -> int:
    cap_fail = verify_captures()
    tax_fail = verify_taxonomy()
    if cap_fail or tax_fail:
        print(json.dumps({"captures": cap_fail[:12], "taxonomy": tax_fail[:12]}, indent=2))
        return fail("captures/taxonomy")

    art = REPO / ART_REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact missing")
    doc = load_json(art)
    text = art.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    art_fail = verify_artifact(doc)
    if art_fail:
        print(json.dumps({"artifact_failures": art_fail[:20]}, indent=2))
        return fail("artifact")

    grades = {g["id"]: g for g in doc.get("gameability_grades") or [] if isinstance(g, dict)}
    missing_recipe = []
    for src in gameable_rows():
        got = grades.get(src["id"]) or {}
        recipe = got.get("cheap_satisfaction_recipe") or ""
        if len(recipe) < 40:
            missing_recipe.append(src["id"])
        if got.get("grade") not in GAMEABLE_GRADES:
            return fail(f"{src['id']} expected gameable/mixed")
    if missing_recipe:
        return fail(f"recipes missing {missing_recipe[:8]}")

    mutant = mutant_strip_recipes(doc)
    mutant_fail = verify_artifact(mutant)
    if not mutant_fail:
        return fail("strip-recipes mutant stayed green")

    report = evaluate_all(doc)
    print(
        json.dumps(
            {
                "probe": "probe1-gameable-recipes",
                "unit_id": "RES-0057",
                "gameable_n": report["gameable_n"],
                "mutant_strip_recipes_red": True,
                "mutant_fail_n": len(mutant_fail),
                "ok": report["ok"],
            },
            sort_keys=True,
        )
    )
    if not report["ok"]:
        print(json.dumps(report["failures"][:12], indent=2))
        return fail("evaluate_all")
    print(
        f"gameable_rows={report['gameable_n']} "
        f"mutant_strip_recipes_red={len(mutant_fail)}"
    )
    print("SUCCESS:RES-0057-probe1 every gameable row names a cheap-satisfaction recipe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
