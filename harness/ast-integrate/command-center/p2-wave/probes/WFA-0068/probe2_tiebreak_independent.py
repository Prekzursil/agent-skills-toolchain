#!/usr/bin/env python3
"""Probe 2: tie-break totality, overlap, independent argmin-rank replay.

Both-states on totality: the live rule list must be a unique 0..n-1 covering
all 15 values (silent on the good state). A mutant that assigns the same rank
to REJECT and RETIRE must go red.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from decide import decide  # noqa: E402
from gold_set import gold_records, overlap_reject_retire, overlap_repair_extend  # noqa: E402
from independent import decide_independent  # noqa: E402
from vocabulary import RULES, VOCABULARY, ranks_are_total, tie_break_order  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0068-disposition-decision-procedure.json"
SENTINEL = "SUCCESS:WFA-0068"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0068-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    live_total = ranks_are_total()
    print(f"tie_break_total={live_total} order={tie_break_order()}")
    if not live_total:
        return fail("live ranks are not a total order")
    if doc.get("tie_break_order") != tie_break_order():
        return fail("artifact tie-break drifted")
    if set(tie_break_order()) != set(VOCABULARY):
        return fail("tie-break does not cover vocabulary")

    mutant = [copy.copy(r) for r in RULES]
    reject = next(r for r in mutant if r["value"] == "REJECT")
    retire = next(r for r in mutant if r["value"] == "RETIRE")
    retire["rank"] = reject["rank"]
    mutant_total = ranks_are_total(mutant)
    print(
        f"mutant_shared_rank REJECT=RETIRE={reject['rank']} "
        f"total={mutant_total}"
    )
    if mutant_total:
        return fail("shared-rank mutant stayed total")
    if not live_total or mutant_total:
        return fail("totality both-states")

    overlap = overlap_reject_retire()
    a = decide(overlap)
    b = decide_independent(overlap)
    print(
        f"overlap {overlap['id']} author={a['disposition']} fired={a['fired']} "
        f"independent={b['disposition']} independent_fired={b['fired']}"
    )
    if a["disposition"] != "REJECT" or b["disposition"] != "REJECT":
        return fail("overlap winner")
    if set(a["fired"]) != {"REJECT", "RETIRE"}:
        return fail("overlap must fire two rules")
    if len(a["fired"]) < 2:
        return fail("two rules fired with no ordering")
    if a["fired"][0] != "REJECT":
        return fail("tie-break did not prefer REJECT")

    gaps = overlap_repair_extend()
    g = decide(gaps)
    print(f"repair-vs-extend {gaps['id']} pred={g['disposition']} fired={g['fired']}")
    if g["disposition"] != "REPAIR":
        return fail("defects+gaps must REPAIR not EXTEND")
    if "EXTEND" in g["fired"]:
        return fail("EXTEND must not fire when defects are present")

    disagree = []
    for rec in gold_records():
        au = decide(rec)
        ind = decide_independent(rec)
        print(
            f"independent {rec['id']} author={au['disposition']} "
            f"independent={ind['disposition']} method={ind['method']}"
        )
        if au["disposition"] != ind["disposition"]:
            disagree.append(rec["id"])
        if au["disposition"] != rec["gold"]:
            return fail(f"author {rec['id']}")
        if ind["disposition"] != rec["gold"]:
            return fail(f"independent {rec['id']}")
        if "gold" in ind["method"]:
            return fail("independent method names gold labels")
    if disagree:
        return fail(f"author/independent disagree {disagree}")

    stored = doc.get("independent_replay") or {}
    if stored.get("method") != "argmin-rank-over-firing-set":
        return fail("artifact independent method")
    if stored.get("agree_with_author") is not True:
        return fail("artifact independent agree flag")

    print("SUCCESS:WFA-0068-probe2 tie-break total, overlap, independent replay")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
