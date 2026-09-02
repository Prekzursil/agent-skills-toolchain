#!/usr/bin/env python3
"""Probe 1: 100-gamed must not satisfy unique>=100; 100-distinct must.

Both-states control: the gate FIRES on the known-broken fixture and is
SILENT on the known-good one. The naive string-equality counter is silent
in both states (accepts both), proving the semantic layer contributes.
Recorded artifact numbers must match this live re-run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import measure as M  # noqa: E402
from payload import payload  # noqa: E402

ART = REPO / "command-center/research/RES-0084.json"
FLOOR = 100


def main() -> int:
    live = M.run()
    gamed = live["known_broken"]["run"]
    distinct = live["known_good"]["run"]
    bs = live["both_states"]

    print(bs["planted_bad"]["verbatim"])
    print(bs["known_good"]["verbatim"])
    print(bs["naive_counter"]["verbatim"])

    if gamed["n_strings"] != FLOOR or distinct["n_strings"] != FLOOR:
        print("FAILED:RES-0084-probe1 fixture size != 100")
        return 1
    if gamed["naive_unique"] != FLOOR:
        print("FAILED:RES-0084-probe1 gamed strings are not 100-unique at the surface")
        return 1
    if gamed["author_union_find"] >= FLOOR:
        print(
            "FAILED:RES-0084-probe1 gamed corpus satisfied unique>=100 "
            f"(count={gamed['author_union_find']})"
        )
        return 1
    if distinct["author_union_find"] < FLOOR:
        print(
            "FAILED:RES-0084-probe1 distinct corpus missed unique>=100 "
            f"(count={distinct['author_union_find']})"
        )
        return 1
    if not bs["discriminates"]:
        print("FAILED:RES-0084-probe1 detector silent in both states")
        return 1
    if not bs["naive_counter"]["silent_in_both_states"]:
        print("FAILED:RES-0084-probe1 naive counter did not accept both corpora")
        return 1
    if gamed["author_union_find"] == gamed["naive_unique"]:
        print("FAILED:RES-0084-probe1 semantic layer did not change the gamed count")
        return 1
    if not live["reviewer_agreement"]:
        print("FAILED:RES-0084-probe1 author/reviewer disagree")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0084-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:RES-0084-probe1 self-declared {doc.get('state')}")
        return 1
    pay = payload(doc)
    rec_g = (pay.get("recorded_runs") or {}).get("known_broken") or {}
    rec_d = (pay.get("recorded_runs") or {}).get("known_good") or {}
    if rec_g.get("author_union_find") != gamed["author_union_find"]:
        print("FAILED:RES-0084-probe1 artifact gamed unique drifted from live")
        return 1
    if rec_d.get("author_union_find") != distinct["author_union_find"]:
        print("FAILED:RES-0084-probe1 artifact distinct unique drifted from live")
        return 1
    fx = pay.get("fixtures") or {}
    if len((fx.get("known_broken") or {}).get("ideas") or []) != FLOOR:
        print("FAILED:RES-0084-probe1 known-broken fixture not inline (100)")
        return 1
    if len((fx.get("known_good") or {}).get("ideas") or []) != FLOOR:
        print("FAILED:RES-0084-probe1 known-good fixture not inline (100)")
        return 1
    if not (pay.get("both_states") or {}).get("discriminates"):
        print("FAILED:RES-0084-probe1 artifact both_states.discriminates is not true")
        return 1

    print(
        json.dumps(
            {
                "gamed_unique": gamed["author_union_find"],
                "distinct_unique": distinct["author_union_find"],
                "gamed_naive": gamed["naive_unique"],
                "fires_on_gamed": True,
                "silent_on_distinct": True,
                "naive_silent_in_both": True,
                "threshold": live["measured_threshold"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:RES-0084-probe1 gamed rejected, distinct accepted, both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
