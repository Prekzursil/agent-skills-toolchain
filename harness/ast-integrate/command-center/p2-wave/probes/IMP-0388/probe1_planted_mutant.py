#!/usr/bin/env python3
"""Probe 1: planted-mutant control for the lexical description linter.

Rename one capability and rewrite its description as a paraphrase of a sibling.
The linter must surface that pair in the top 5 confusable pairs.

A detector that ranks every pair identically, or that always inserts the
planted ids regardless of text, fails the distinct-rewrite control in probe 2.
This probe only asserts the required positive control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "router"))
import desc_lint as L  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0388.json"
INDEX = HERE / "fixtures/capability-index.json"
MUTANT = HERE / "fixtures/planted-mutant.json"
SENTINEL = "SENTINEL:IMP-0388:DESCRIPTION-LINT-COMPLETE"


def main() -> int:
    spec = json.loads(MUTANT.read_text(encoding="utf-8"))
    caps, _ = L.load_index(INDEX)
    mutated = L.apply_rename_paraphrase(
        caps,
        source_id=spec["source_id"],
        sibling_id=spec["sibling_id"],
        new_id=spec["new_id"],
        paraphrase=spec["paraphrase"],
    )
    ids = {L.cap_id(c) for c in mutated}
    if spec["source_id"] in ids:
        print("FAILED:IMP-0388-probe1 source id still present after rename")
        return 1
    if spec["new_id"] not in ids or spec["sibling_id"] not in ids:
        print("FAILED:IMP-0388-probe1 rename did not land")
        return 1
    report = L.lint(mutated, top_n=20)
    ranking = report["confusability"]["top_20"]
    hit = L.pair_in_top(ranking, spec["new_id"], spec["sibling_id"], k=5)
    payload = {
        "probe": "probe1-planted-mutant",
        "new_id": spec["new_id"],
        "sibling_id": spec["sibling_id"],
        "in_top_5": hit is not None,
        "rank": None
        if hit is None
        else 1
        + next(
            i
            for i, row in enumerate(ranking)
            if frozenset({row["id_a"], row["id_b"]})
            == frozenset({spec["new_id"], spec["sibling_id"]})
        ),
        "score": None if hit is None else hit["token_overlap_score"],
        "top_5": [
            {
                "id_a": r["id_a"],
                "id_b": r["id_b"],
                "token_overlap_score": r["token_overlap_score"],
            }
            for r in ranking[:5]
        ],
    }
    print(json.dumps(payload, sort_keys=True))
    if hit is None:
        print("FAILED:IMP-0388-probe1 planted paraphrase pair not in top 5")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0388-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0388":
        print("FAILED:IMP-0388-probe1 unit_id", doc.get("unit_id"))
        return 1
    if SENTINEL not in text:
        print("FAILED:IMP-0388-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:IMP-0388-probe1 self-declared", doc.get("state"))
        return 1
    planted = doc.get("planted_mutant") or {}
    if planted.get("in_top_5") is not True:
        print("FAILED:IMP-0388-probe1 receipt planted_mutant.in_top_5 is not true")
        return 1
    print(
        f"planted in_top_5=True rank={payload['rank']} "
        f"score={payload['score']}"
    )
    print("SUCCESS:IMP-0388-probe1 planted-mutant paraphrase pair in top 5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
