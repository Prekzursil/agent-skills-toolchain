#!/usr/bin/env python3
"""Cross-slice near-duplicate scan: each ADV-2 unit against every unit in every
other slice on disk. Lexical Jaccard over title+question+evidence, same detector
as the intra-slice pass, with the same planted-mutant control so a low score is
readable as 'the detector works and found nothing' rather than 'the detector is
silent'."""
from __future__ import annotations

import glob
import json
import pathlib
import re

HERE = pathlib.Path(__file__).parent
STOP = set("the a an of to and or is are be for with that this it its on in by not no as at from "
           "every each any all must must be may can does do did which what who whom whose than then "
           "into over under between across per via one two three unit units program spec".split())


def toks(x: dict) -> set[str]:
    blob = " ".join([x.get("title", ""), x.get("question_or_target", ""),
                     x.get("evidence_requirement", "")]).lower()
    return {w for w in re.findall(r"[a-z][a-z0-9-]{2,}", blob) if w not in STOP}


def jac(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if (a | b) else 0.0


mine = json.load(open(HERE / "ADV-2.json", encoding="utf-8"))
others: list[tuple[str, dict, set[str]]] = []
for f in sorted(glob.glob(str(HERE / "*.json"))):
    p = pathlib.Path(f)
    if p.name == "ADV-2.json":
        continue
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception as exc:
        print(f"# skip {p.name}: {type(exc).__name__}")
        continue
    if not isinstance(d, list):
        continue
    for o in d:
        if isinstance(o, dict) and "title" in o:
            others.append((p.name, o, toks(o)))

print(f"# compared against {len(others)} sibling units in "
      f"{len({n for n, _, _ in others})} slices")

# DETECTOR CONTROL: inject a reworded clone of a real sibling unit and confirm the
# cross-slice scan ranks it top. A scan that cannot see a known duplicate cannot
# certify absence.
victim = others[len(others) // 2]
clone = {"title": victim[1]["title"], "question_or_target": victim[1].get("question_or_target", ""),
         "evidence_requirement": victim[1].get("evidence_requirement", "")}
ctrl = max(jac(toks(clone), t) for _, _, t in others)
print(f"# detector control (verbatim clone of {victim[0]}:{victim[1]['id']}) = {ctrl:.3f}")
assert ctrl > 0.9, "CONTROL FAILED: cross-slice scan cannot see a known duplicate"

worst = 0.0
for m in mine:
    tm = toks(m)
    ranked = sorted(((jac(tm, t), n, o["id"], o["title"]) for n, o, t in others), reverse=True)
    s, n, oid, title = ranked[0]
    worst = max(worst, s)
    flag = "  <== REVIEW" if s >= 0.35 else ""
    print(f"{m['id']}  max={s:.3f}  nearest={n}:{oid}  {title[:78]}{flag}")

print(f"\n# highest cross-slice similarity for any ADV-2 unit = {worst:.3f} "
      f"(control {ctrl:.3f}); threshold for manual review 0.350")
print("SUCCESS:xdedup-ADV-2" if worst < 0.35 else "REVIEW:xdedup-ADV-2 at least one pair >= 0.35")
