#!/usr/bin/env python3
"""Planted padding and saturation fixtures for CNL-0055.

Distinct ideas share no tokens. Padding variants keep the parent token
set (Jaccard >= 0.8) while remaining distinct as raw strings, so a naive
exact-string unique counter can be gamed to 100 while the Jaccard unique
count does not move.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

import detector as D  # noqa: E402


def distinct_idea(i: int) -> str:
    parts = [f"uniqueidea{i:03d}"]
    for lane in range(5):
        parts.append(f"t{i:03d}l{lane}x{(i * 11 + lane * 13) % 97:02d}")
    return " ".join(parts)


def paraphrase(text: str, kind: str) -> str:
    toks = text.split()
    if kind == "suffix":
        return text + " restated"
    if kind == "prefix":
        return "note " + text
    if kind == "swap" and len(toks) >= 2:
        toks[0], toks[1] = toks[1], toks[0]
        return " ".join(toks)
    if kind == "insert" and toks:
        return " ".join(toks[:-1] + ["again", toks[-1]])
    raise ValueError(kind)


def build(name: str) -> dict:
    quota = D.QUOTA
    if name == "padding":
        ledger = [distinct_idea(i) for i in range(40)]
        offered = [paraphrase(distinct_idea(i), "suffix") for i in range(40)]
        offered += [paraphrase(distinct_idea(i), "prefix") for i in range(20)]
        expected = "QUOTA_FILLING"
        stop = False
        note = (
            "40 genuine ideas; 60 near-duplicates offered to close the raw "
            "count toward 100. Naive exact-string unique rises; Jaccard unique does not."
        )
    elif name == "saturated":
        ledger = [distinct_idea(i) for i in range(100)]
        offered = [paraphrase(distinct_idea(i), "suffix") for i in range(3)]
        expected = "SATURATION"
        stop = True
        note = (
            "100 genuine unique ideas already in the ledger. Next round offers "
            "three restatements (low volume). Next round adds nothing unique."
        )
    elif name == "continue":
        ledger = [distinct_idea(i) for i in range(40)]
        offered = [distinct_idea(i) for i in range(40, 60)]
        expected = "CONTINUE"
        stop = False
        note = "20 genuinely new unique ideas; neither saturation nor padding."
    elif name == "early_saturation":
        ledger = [distinct_idea(i) for i in range(50)]
        offered = [paraphrase(distinct_idea(i), "swap") for i in range(2)]
        expected = "SATURATION"
        stop = True
        note = (
            "Idea space exhausted at 50 unique. Round stops for saturation; "
            "unique_ideas >= 100 stays unsatisfied."
        )
    else:
        raise KeyError(name)
    return {
        "name": name,
        "quota": quota,
        "ledger": ledger,
        "offered": offered,
        "expected_decision": expected,
        "expected_stop_round": stop,
        "note": note,
    }


def write_fixture_files() -> list[Path]:
    FIX.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in ("padding", "saturated", "continue", "early_saturation"):
        pack = build(name)
        path = FIX / f"{name}.json"
        path.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def self_test() -> dict:
    rows = []
    ok = True
    for name in ("padding", "saturated", "continue", "early_saturation"):
        pack = build(name)
        both = D.classify_both(pack["ledger"], pack["offered"], quota=pack["quota"])
        s1 = both["signal1_jaccard"]
        match = (
            s1["decision"] == pack["expected_decision"]
            and s1["stop_round"] is pack["expected_stop_round"]
            and both["methods_agree_on_decision"] is True
        )
        if name == "padding":
            match = match and s1["unique_yield"] == 0 and s1["naive_yield"] == 60
            match = match and s1["satisfy_unique_quota"] is False
        if name == "saturated":
            match = match and s1["unique_yield"] == 0 and s1["unique_before"] == 100
            match = match and s1["low_volume"] is True
            match = match and s1["satisfy_unique_quota"] is True
        if name == "early_saturation":
            match = match and s1["satisfy_unique_quota"] is False
        if not match:
            ok = False
        rows.append(
            {
                "fixture": name,
                "decision": s1["decision"],
                "expected": pack["expected_decision"],
                "stop_round": s1["stop_round"],
                "unique_yield": s1["unique_yield"],
                "naive_yield": s1["naive_yield"],
                "methods_agree": both["methods_agree_on_decision"],
                "match": match,
            }
        )
    padding = D.classify_both(*_pair("padding"))
    saturated = D.classify_both(*_pair("saturated"))
    told_apart = (
        padding["decision"] == "QUOTA_FILLING"
        and saturated["decision"] == "SATURATION"
        and padding["stop_round"] is False
        and saturated["stop_round"] is True
    )
    return {"pass": ok and told_apart, "told_apart": told_apart, "rows": rows}


def _pair(name: str) -> tuple[list[str], list[str]]:
    pack = build(name)
    return pack["ledger"], pack["offered"]


if __name__ == "__main__":
    report = self_test()
    write_fixture_files()
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["pass"] else 1)
