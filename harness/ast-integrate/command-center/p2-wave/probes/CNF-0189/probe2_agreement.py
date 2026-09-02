#!/usr/bin/env python3
"""Probe 2: both-flagged listed; xor-flagged body-adjudicated (no retune)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import scan as SC  # noqa: E402

ART = HERE.parents[3] / "command-center" / "receipts" / "CNF-0189.json"


def _key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0189-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("verdict") in {"BLOCKED", "FAILED"}:
        print("FAILED:CNF-0189-probe2 self-declared", doc.get("verdict"))
        return 1

    live = SC.run_scan()
    art_both = {_key(r["id_a"], r["id_b"]) for r in (doc.get("high_confidence_both") or [])}
    live_both = {_key(r["id_a"], r["id_b"]) for r in live["high_confidence_both"]}
    if art_both != live_both:
        print("FAILED:CNF-0189-probe2 high-confidence set mismatch")
        return 1

    art_xor = {
        _key(r["id_a"], r["id_b"]): r for r in (doc.get("disagreement_adjudicated") or [])
    }
    live_xor = {_key(r["id_a"], r["id_b"]): r for r in live["disagreement_adjudicated"]}
    if set(art_xor) != set(live_xor):
        print("FAILED:CNF-0189-probe2 disagreement set mismatch")
        return 1

    for key, row in live_xor.items():
        adj = row.get("adjudication") or {}
        if adj.get("verdict") not in {"same_mechanism", "distinct", "uncertain"}:
            print("FAILED:CNF-0189-probe2 missing body adjudication", key)
            return 1
        if (art_xor[key].get("adjudication") or {}).get("verdict") != adj.get("verdict"):
            print("FAILED:CNF-0189-probe2 adjudication drifted", key)
            return 1

    deep = next(r for r in live["planted_control"] if r["mutant_class"] == "deep_paraphrase")
    deep_key = _key(deep["id_a"], deep["id_b"])
    if deep_key in live_both:
        print("FAILED:CNF-0189-probe2 deep paraphrase also lexical-hit")
        return 1
    if deep_key not in live_xor:
        print("FAILED:CNF-0189-probe2 deep paraphrase not in disagreement set")
        return 1
    if live_xor[deep_key]["adjudication"]["verdict"] != "same_mechanism":
        print("FAILED:CNF-0189-probe2 deep not same_mechanism", live_xor[deep_key]["adjudication"])
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-agreement",
                "both": len(live_both),
                "xor": len(live_xor),
                "deep_adjudicated": "same_mechanism",
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0189-probe2 agreement listed; disagreement body-adjudicated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
