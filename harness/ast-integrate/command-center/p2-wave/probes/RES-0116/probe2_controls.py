#!/usr/bin/env python3
"""Probe 2: discarded-translation control and both-states quote check.

Independent of probe 1's printed verdict. Re-derives checks from the
artifact and the capture files.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from quotes import discards_not_promoted, quotes_ok, sentinel_ok
from register import DISCARDED_RETRANSLATIONS

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/research/RES-0116.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0116-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    ok, why = sentinel_ok(doc, text)
    print(f"sentinel_ok={ok} {why}")
    if not ok:
        return fail(why)

    n = int(doc.get("discarded_as_translations_of_english_sources") or -1)
    print(f"discarded_as_translations_of_english_sources={n}")
    if n != len(DISCARDED_RETRANSLATIONS) or n < 1:
        return fail(f"discard control n={n}")
    ok, why = discards_not_promoted(doc)
    print(f"discards_not_promoted={ok} {why}")
    if not ok:
        return fail(why)

    ok, why = quotes_ok(doc)
    print(f"quotes_live={ok} {why}")
    if not ok:
        return fail(why)

    stripped = copy.deepcopy(doc)
    for row in stripped["register"]:
        row["original_language_quote"] = ""
        row["secondary_quote"] = ""
    ok_dark, why_dark = quotes_ok(stripped)
    print(f"quotes_stripped={ok_dark} {why_dark}")
    if ok_dark:
        return fail("quote checker silent after stripping original-language quotes")

    e3 = [r["id"] for r in doc["register"] if r.get("evidence_grade") == "E3"]
    print(f"e3_rows={e3}")
    if "R-GIAN-GYEOLJAE" not in e3:
        return fail("korean single-rail row was not graded E3")
    measured = [
        r
        for r in doc["register"]
        if r.get("verdict") == "NO-ENGLISH-EQUIVALENT-IN-CORPUS"
        and r.get("evidence_grade") != "E3"
    ]
    for r in measured:
        kinds = {x.get("kind") for x in r.get("rails") or []}
        if "api" not in kinds or "prose" not in kinds:
            return fail(f"{r['id']} measured without api+prose")
    print("SUCCESS:RES-0116-probe2 discard-control both-states e3-guard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
