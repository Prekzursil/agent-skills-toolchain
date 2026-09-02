#!/usr/bin/env python3
"""Probe 1: every observed job maps to exactly one entry surface.

Independent enumerator (text/regex) must match the author enumerator (AST).
Designed mapping in DESIGN.json must cover every observed job and no others.
Negative controls: unmapped job, invented persona, dual-map — must fire.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import coverage as C  # noqa: E402
import design_io as D  # noqa: E402
import jobs as J  # noqa: E402

DESIGN = REPO / "command-center/phase3/A8/DESIGN.json"


def main() -> int:
    author = J.enumerate_author(REPO)
    indep = J.enumerate_independent(REPO)
    ok, why = J.same_ids(author, indep)
    print(f"enumerators_agree={ok} why={why} n={len(author)}")
    if not ok:
        print("FAILED:ARC-0052-probe1 enumerator disagreement")
        return 1
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    designed = D.jobs(design)
    report = C.coverage(author, designed)
    print(
        f"coverage ok={report['ok']} observed={report['observed_count']} "
        f"designed={report['designed_count']} unmapped={report['unmapped']} "
        f"invented={report['invented_personas']} dual={report['dual_mapped']}"
    )
    for row in author:
        print(f"job id={row['id']} surface={row['surface']} count={row['count']}")
    if not report["ok"]:
        print("FAILED:ARC-0052-probe1 coverage gap")
        return 1

    unmapped = copy.deepcopy(designed)
    dropped = unmapped.pop()
    bad_unmapped = C.coverage(author, unmapped)
    persona = copy.deepcopy(designed) + [
        {
            "id": "power-user-delight",
            "surface": "command",
            "source": "invented-persona",
            "evidence": "none",
            "count": 0,
        }
    ]
    bad_persona = C.coverage(author, persona)
    dual = copy.deepcopy(designed)
    dual[0] = dict(dual[0])
    dual[0]["surfaces"] = ["command", "catalog"]
    bad_dual = C.coverage(author, dual)
    good = C.coverage(author, designed)
    fired = (
        (not bad_unmapped["ok"] and dropped["id"] in bad_unmapped["unmapped"])
        and (not bad_persona["ok"] and "power-user-delight" in bad_persona["invented_personas"])
        and (not bad_dual["ok"] and dual[0]["id"] in bad_dual["dual_mapped"])
        and good["ok"]
    )
    print(
        f"fired_on_unmapped={not bad_unmapped['ok']} "
        f"fired_on_persona={not bad_persona['ok']} "
        f"fired_on_dual={not bad_dual['ok']} "
        f"silent_on_good={good['ok']}"
    )
    if not fired:
        print("FAILED:ARC-0052-probe1 negative controls did not discriminate")
        return 1
    print("SUCCESS:ARC-0052-probe1 coverage assertion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
