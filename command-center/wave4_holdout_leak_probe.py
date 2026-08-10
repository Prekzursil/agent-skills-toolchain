#!/usr/bin/env python
"""Second, mechanically-different probe of the ONE holdout my reimplementation could not
verify: does the LANE'S OWN `queries.holdout_index` also leave the held-out sentence in
`command:compute-monitor`'s routing_text?

My probe and the lane's are different code paths reaching the same question, so if both
say the sentence survives, the finding is the lane's, not my reimplementation's.

Also runs the both-states control: a record whose strip DID verify must show the sentence
present BEFORE and absent AFTER. A checker that reports "absent" on both is measuring
nothing.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent.parent / "platform"
sys.path.insert(0, str(BUILD))

from routing import index as ridx  # noqa: E402
from routing import queries as rq  # noqa: E402


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


raw = ridx.discover()
qs = rq.build(raw)
held = rq.holdout_index(raw, qs.queries)  # THE LANE'S OWN implementation
by_raw = raw.by_id()
by_held = held.by_id()

rows = []
for q in qs.queries:
    if q.tier != "L1" or not q.holdout_id:
        continue
    rec_raw = by_raw[q.holdout_id]
    rec_held = by_held[q.holdout_id]
    frag = norm(q.holdout_text)
    cleaned = norm(re.sub(r"\s+", " ", q.holdout_text).strip(" .,;:-"))
    qtext = norm(q.text)
    rows.append(
        {
            "qid": q.qid,
            "holdout_id": q.holdout_id,
            "present_BEFORE_in_raw": frag in norm(rec_raw.routing_text),
            "present_AFTER_in_lane_holdout": frag in norm(rec_held.routing_text),
            "query_text_present_AFTER": qtext in norm(rec_held.routing_text),
            "cleaned_present_AFTER": cleaned in norm(rec_held.routing_text),
            "raw_len": len(rec_raw.routing_text),
            "held_len": len(rec_held.routing_text),
            "shrunk": len(rec_raw.routing_text) - len(rec_held.routing_text),
        }
    )

leaks = [
    r
    for r in rows
    if r["present_AFTER_in_lane_holdout"] or r["query_text_present_AFTER"]
]
before_ok = [r for r in rows if r["present_BEFORE_in_raw"]]

out = {
    "instrument": "routing.queries.holdout_index (the LANE'S OWN code), checked with "
    "whitespace-normalized case-insensitive containment - a different comparison than "
    "the raw str.replace the holdout itself performs",
    "l1_queries": len(rows),
    "BOTH_STATES_control": {
        "sentences_present_BEFORE_the_strip": len(before_ok),
        "of_total": len(rows),
        "meaning": "if a sentence were not present BEFORE, 'absent after' would prove "
        "nothing; this is the known-present control for the checker",
    },
    "LEAKED_after_lane_holdout": leaks,
    "n_leaked": len(leaks),
    "verdict": (
        f"{len(leaks)} of {len(rows)} L1 holdouts are NOT actually held out - those "
        "queries are circular (the router can still see the exact text it must retrieve)"
        if leaks
        else "0 leaks - every L1 holdout verified absent"
    ),
    "rows": rows,
}
print(json.dumps(out, indent=2))
Path(__file__).with_name("WAVE4-HOLDOUT-LEAK.json").write_text(
    json.dumps(out, indent=2), encoding="utf-8"
)
