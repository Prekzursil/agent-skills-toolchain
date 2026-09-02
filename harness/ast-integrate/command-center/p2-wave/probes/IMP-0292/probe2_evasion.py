#!/usr/bin/env python3
"""Named probe 2: non-answer stays OPEN; byte-count control is defeated.

Independent of probe 1. Starts from the labelled corpus and the public
classify_reply / SocraticProtocol API, not from an author's summary.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.protocol.socratic import (  # noqa: E402
    LABEL_ANSWER,
    STATE_OPEN,
    SocraticProtocol,
    classify_reply,
    load_corpus,
    naive_any_bytes_discharge,
    score_corpus,
)

CORPUS = HERE / "fixtures" / "evasion-corpus.json"
SCORE_OUT = HERE / "evasion-corpus-score.json"
MIN_RATE = 0.9


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0292-probe2 {msg}")
    return 1


def main() -> int:
    if not CORPUS.is_file():
        return fail("labelled corpus missing")
    items = load_corpus(CORPUS)
    if len(items) < 16:
        return fail(f"corpus too small n={len(items)}")

    golds = {str(it.get("gold") or "").upper() for it in items}
    if LABEL_ANSWER not in golds or not (golds & {"EVASION", "NON_ANSWER"}):
        return fail(f"corpus not labelled with both classes: {golds}")

    scored = score_corpus(items)
    rate = float(scored["discrimination_rate"])
    if scored["fp"] or scored["fn"]:
        # Honest: print misses, still fail below MIN_RATE.
        misses = [r for r in scored["rows"] if r["bucket"] in {"fp", "fn"}]
        print(json.dumps({"misses": misses}, indent=2)[:4000])
    if rate < MIN_RATE:
        return fail(
            f"discrimination_rate={rate:.3f} < {MIN_RATE} "
            f"tp={scored['tp']} tn={scored['tn']} fp={scored['fp']} fn={scored['fn']}"
        )

    byte_beating = []
    for it in items:
        gold = str(it["gold"]).upper()
        if gold == LABEL_ANSWER:
            continue
        reply = str(it["reply"])
        naive = naive_any_bytes_discharge(reply)
        cls = classify_reply(str(it["question"]), reply)
        if naive and not cls.is_answer:
            byte_beating.append(
                {
                    "id": it["id"],
                    "reply_bytes": cls.reply_bytes,
                    "pred": cls.label,
                    "reason": cls.reason,
                }
            )
    if len(byte_beating) < 5:
        return fail(f"need >=5 non-answers that beat a byte counter, got {len(byte_beating)}")

    # Live ledger: a 4kB non-answer must remain OPEN.
    proto = SocraticProtocol(default_due_in_turns=5, auto_escalate=False)
    ob = proto.ask("alice", "bob", "Does an empty reply discharge a socratic obligation?")
    flood = "sure " + ("lorem " * 800)
    if not naive_any_bytes_discharge(flood):
        return fail("flood fixture has zero bytes; cannot refute byte counting")
    rec = proto.record_turn("bob", flood)
    live = proto.get(ob.id)
    if live.state != STATE_OPEN:
        return fail(f"non-answer discharged live ledger: {live.state} {live.last_reason}")
    if rec["evaluations"][0]["classification"]["naive_bytes_would_discharge"] is not True:
        return fail("naive control did not fire on the flood")
    if rec["evaluations"][0]["classification"]["label"] == LABEL_ANSWER:
        return fail("flood classified as ANSWER")

    # Empty stays OPEN and naive control is silent — different from the byte flood.
    proto2 = SocraticProtocol(default_due_in_turns=5, auto_escalate=False)
    empty_ob = proto2.ask("alice", "bob", "Does an empty reply discharge a socratic obligation?")
    proto2.record_turn("bob", "")
    if proto2.get(empty_ob.id).state != STATE_OPEN:
        return fail("empty reply discharged")
    if naive_any_bytes_discharge(""):
        return fail("naive control must be silent on empty (both-states)")

    payload = {
        "probe": "probe2-evasion",
        "unit_id": "IMP-0292",
        "pass": True,
        "n": scored["n"],
        "tp": scored["tp"],
        "tn": scored["tn"],
        "fp": scored["fp"],
        "fn": scored["fn"],
        "discrimination_rate": rate,
        "precision": scored["precision"],
        "recall": scored["recall"],
        "byte_counter_defeated_n": len(byte_beating),
        "byte_counter_defeated_ids": [b["id"] for b in byte_beating],
        "live_non_answer_remained_open": True,
        "empty_remained_open": True,
        "rows": scored["rows"],
    }
    SCORE_OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    summary = {k: v for k, v in payload.items() if k != "rows"}
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:IMP-0292-probe2 non-answer remains OPEN; discrimination rate reported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
