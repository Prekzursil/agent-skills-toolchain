#!/usr/bin/env python3
"""Probe 1: mapping table + both-states gap vs free-text fallback."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import mapper as M  # noqa: E402
import reviewer as R  # noqa: E402
from vocab import GAP, vocab_ids  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0058-mechanism-vocabulary.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0058-probe1 {msg}")
    return 1


def main() -> int:
    print("detector_control_first=True")
    data = C.load_corpus()
    texts = C.distinct_texts(data)
    rows = M.map_all(texts)
    leaks = M.closed_ids(rows)
    multi = M.unique_mapping(rows)
    print(
        f"origin={data['origin']} live_present={data['live_present']} "
        f"n_distinct={len(texts)}"
    )
    print(f"closed_leaks={sorted(leaks)} multi_mapped={len(multi)}")
    if leaks:
        return fail(f"open vocab ids {sorted(leaks)}")
    if multi:
        return fail(f"source mapped to multiple ids {multi}")

    alias_n = 0
    for row in data["rows"]:
        if row["kind"] != "alias":
            continue
        alias_n += 1
        got = M.map_one(row["text"])
        if got["vocab_id"] != row["source"] or got["gap"]:
            return fail(
                f"alias {row['text']!r} -> {got['vocab_id']} want {row['source']}"
            )
    print(f"aliases_exact n={alias_n}")

    gap_n = 0
    for row in data["rows"]:
        if row["kind"] != "gap":
            continue
        gap_n += 1
        got = M.map_one(row["text"])
        print(f"gap {row['text']!r} -> {got['vocab_id']} rule={got['rule']}")
        if got["vocab_id"] != GAP:
            return fail("planted gap was not NEW-MECHANISM")
    print(f"gaps_are_NEW_MECHANISM n={gap_n}")

    planted = "planted-unknown-mechanism-xyzzy"
    closed = M.map_one(planted)
    fallback = M.fallback_mutant(planted)
    invented = M.invent_id_mutant(planted)
    print(
        f"planted closed={closed['vocab_id']} fallback={fallback!r} "
        f"invent={invented}"
    )
    if closed["vocab_id"] != GAP:
        return fail("unmapped string was not recorded as a gap")
    if fallback != planted:
        return fail("fallback mutant did not return free text (control broken)")
    if fallback in vocab_ids() or fallback == GAP:
        return fail("fallback mutant collapsed into vocab")
    if invented in vocab_ids():
        return fail("invented id landed in frozen vocab")
    if invented == planted:
        return fail("invent mutant returned free text")

    empty = M.map_one("")
    missing = M.map_one("   ")
    print(f"empty={empty['vocab_id']} whitespace={missing['vocab_id']}")
    if empty["vocab_id"] != GAP or missing["vocab_id"] != GAP:
        return fail("empty string was not rejected as a gap")

    both = R.mapping_both_states()
    print(
        f"both_states good_ok={both['known_good']['ok']} "
        f"planted_ok={both['planted_gap']['ok']}"
    )
    if not both["ok"]:
        return fail("mapping both-states failed")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0058" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    table = doc.get("mapping_table") or []
    if len(table) != len(texts):
        return fail(f"mapping_table n={len(table)} corpus n={len(texts)}")
    print("detector_control_found_known_present=True")
    print("SUCCESS:WFA-0058-probe1 mapping both-states closed-gap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
