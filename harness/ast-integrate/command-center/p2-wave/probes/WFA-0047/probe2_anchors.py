#!/usr/bin/env python3
"""Named probe 2: frontmatter use-versus-mention + per-stage line citations.

Every extracted stage must cite a SKILL.md line whose text contains the
snippet. Frontmatter-only ordinals must not become stages. A whole-file
mutant must extract the trap (both-states on use-versus-mention).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from adapter import EXTRACTED, NOT_EXTRACTABLE, extract_skill  # noqa: E402
from gold import GOLD, REFUSE, skill_path  # noqa: E402
from mutants import mutant_whole_file  # noqa: E402

ART = REPO / "command-center" / "wfa" / "WFA-0047-adapter-skill-markdown.json"


def line_at(path: Path, n: int) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    if n < 1 or n > len(lines):
        return ""
    return lines[n - 1]


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0047-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "WFA-0047":
        print("FAILED:WFA-0047-probe2 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:WFA-0047" not in text:
        print("FAILED:WFA-0047-probe2 sentinel absent")
        return 1

    cited = 0
    for rec in GOLD:
        path = skill_path(rec["id"])
        got = extract_skill(path)
        if got.get("verdict") != EXTRACTED:
            print(f"FAILED:WFA-0047-probe2 {rec['id']} not extracted: {got.get('verdict')}")
            return 1
        stages = got.get("stages") or []
        if len(stages) != len(rec["titles"]):
            print(
                f"FAILED:WFA-0047-probe2 {rec['id']} n={len(stages)} want={len(rec['titles'])}"
            )
            return 1
        for st, title, snippet in zip(stages, rec["titles"], rec["snippets"]):
            if st.get("title") != title:
                print(f"FAILED:WFA-0047-probe2 {rec['id']} title {st.get('title')!r} != {title!r}")
                return 1
            anchor = st.get("source_anchor") or {}
            line = anchor.get("line")
            if not isinstance(line, int) or line < 1:
                print(f"FAILED:WFA-0047-probe2 {rec['id']} missing line cite")
                return 1
            live = line_at(path, line)
            if snippet not in live:
                print(
                    f"FAILED:WFA-0047-probe2 {rec['id']} line {line} {live!r} missing {snippet!r}"
                )
                return 1
            if snippet not in (anchor.get("snippet") or ""):
                print(f"FAILED:WFA-0047-probe2 {rec['id']} snippet not in anchor")
                return 1
            cited += 1
        for bad in rec.get("forbidden_titles") or []:
            if any(st.get("title") == bad for st in stages):
                print(f"FAILED:WFA-0047-probe2 {rec['id']} used frontmatter title {bad!r}")
                return 1

    trap = skill_path("refuse-frontmatter-trap")
    trap_got = extract_skill(trap)
    if trap_got.get("verdict") != NOT_EXTRACTABLE:
        print("FAILED:WFA-0047-probe2 frontmatter trap was extracted")
        print(json.dumps(trap_got, indent=2)[:1500])
        return 1
    mutant = mutant_whole_file(trap)
    if mutant.get("verdict") != EXTRACTED:
        print("FAILED:WFA-0047-probe2 whole-file mutant did not extract trap")
        return 1
    mutant_titles = [s["title"] for s in mutant.get("stages") or []]
    if "Inventory the cluster" not in " ".join(mutant_titles) and not any(
        "Inventory" in t for t in mutant_titles
    ):
        print("FAILED:WFA-0047-probe2 mutant did not pick frontmatter ordinals", mutant_titles)
        return 1

    fence = skill_path("refuse-codeblock-mention")
    fence_got = extract_skill(fence)
    if fence_got.get("verdict") != NOT_EXTRACTABLE:
        print("FAILED:WFA-0047-probe2 fenced mention was extracted")
        return 1
    fence_mut = mutant_whole_file(fence)
    if fence_mut.get("verdict") != EXTRACTED:
        print("FAILED:WFA-0047-probe2 whole-file mutant missed fenced ordinals")
        return 1

    if cited < 18:
        print(f"FAILED:WFA-0047-probe2 cited={cited} want>=18")
        return 1

    out = {
        "probe": "probe2-anchors",
        "unit_id": "WFA-0047",
        "stages_cited": cited,
        "frontmatter_trap_refused": True,
        "whole_file_mutant_extracted_trap": True,
        "fenced_mention_refused": True,
        "refuse_n": len(REFUSE),
        "pass": True,
    }
    print(json.dumps(out, indent=2))
    print("SUCCESS:WFA-0047-probe2 line citations and use-versus-mention")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
