#!/usr/bin/env python3
"""Probe 1: decision-log check before ask; planted SETTLED is not re-asked.

Both-states: an owner utterance that names the controversial-source class
files SETTLED with path:line. Replacing that utterance with agent inference
flips the same action to ASK. Live artifact must carry SUCCESS:WFA-0077
and every classification row must record decision_log_checked=true.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import gates as G  # noqa: E402

ART = REPO / G.OUT_REL
ACTION = "controversial_source_classes"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0077-probe1 {msg}")
    return 1


def row_for(result: dict, action: str) -> dict:
    return next(r for r in result["action_rows"] if r["action"] == action)


def main() -> int:
    settled_text = (HERE / "fixtures/settled/OWNER-DECISIONS.md").read_text(
        encoding="utf-8"
    )
    unsettled_text = (HERE / "fixtures/unsettled/OWNER-DECISIONS.md").read_text(
        encoding="utf-8"
    )
    extra_s = [
        {
            "path": "command-center/p2-wave/probes/WFA-0077/fixtures/settled/OWNER-DECISIONS.md",
            "text": settled_text,
            "source": "fixture",
        }
    ]
    extra_u = [
        {
            "path": "command-center/p2-wave/probes/WFA-0077/fixtures/unsettled/OWNER-DECISIONS.md",
            "text": unsettled_text,
            "source": "fixture",
        }
    ]
    s = G.classify(REPO, extra_docs=extra_s)
    u = G.classify(REPO, extra_docs=extra_u)
    live = G.classify(REPO)

    rs = row_for(s, ACTION)
    ru = row_for(u, ACTION)
    rl = row_for(live, ACTION)
    print(
        f"settled_disposition={rs['disposition']} "
        f"anchor={None if not rs['settlement'] else rs['settlement']['anchor']}"
    )
    print(f"unsettled_disposition={ru['disposition']}")
    print(
        f"live_disposition={rl['disposition']} "
        f"binding_present={live['live_binding_records_present']}"
    )

    if rs["disposition"] != "SETTLED":
        return fail(f"planted owner utterance not SETTLED: {rs['disposition']}")
    if not rs["settlement"] or ":" not in str(rs["settlement"].get("anchor")):
        return fail("SETTLED missing path:line citation")
    quote = rs["settlement"]["quote"].lower()
    if "onion" not in quote and "controversial" not in quote:
        return fail("settlement quote does not name the class")
    if rs["id"] not in {r["id"] for r in s["settled"]}:
        return fail("SETTLED row missing from settled list")
    if rs["id"] in s["deferred_ask_ids"]:
        return fail("SETTLED id still in deferred ask queue")
    if s["presented_now"] and s["presented_now"]["id"] == rs["id"]:
        return fail("SETTLED question presented as the live ask")

    if ru["disposition"] != "ASK":
        return fail(
            f"agent-inference fixture still {ru['disposition']} (both-states silent)"
        )
    if ru["settlement"]:
        return fail("agent inference minted a settlement citation")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("live artifact missing")
    raw = ART.read_text(encoding="utf-8")
    if G.SENTINEL not in raw:
        return fail("sentinel absent")
    doc = json.loads(raw)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("record_type") != "AuditReport":
        return fail("record_type is not AuditReport")

    rows = doc.get("classifications") or []
    if len(rows) != 7:
        return fail(f"expected 7 classification rows, got {len(rows)}")
    for row in rows:
        if row.get("decision_log_checked") is not True:
            return fail(f"{row.get('id')} decision_log_checked is not true")
    search = doc.get("decision_record_search") or {}
    if search.get("checked_before_ask") is not True:
        return fail("checked_before_ask is not true")

    ask_ids = [r["id"] for r in rows if r["disposition"] == "ASK"]
    queue = doc.get("ask_queue") or {}
    presented = queue.get("presented_now") or {}
    deferred = queue.get("deferred_ids") or []
    if presented.get("id") not in ask_ids:
        return fail("presented_now is not an ASK row")
    if presented.get("id") in deferred:
        return fail("presented_now also listed as deferred")
    if set(deferred) | {presented.get("id")} != set(ask_ids):
        return fail("ask queue does not partition ASK ids")

    print(
        "live_ask_ids="
        + json.dumps(ask_ids)
        + " presented="
        + str(presented.get("id"))
        + " settled_fixture_anchor="
        + str(rs["settlement"]["anchor"])
    )
    print("SUCCESS:WFA-0077-probe1 settled-not-reasked both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
