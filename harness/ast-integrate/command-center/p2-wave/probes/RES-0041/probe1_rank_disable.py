#!/usr/bin/env python3
"""Probe 1: ranked per-server tokenizer table + disable-and-remeasure control.

Recomputes the fleet live from fixtures (not by re-reading a cached total) and
checks the artifact table matches. Tokens come from the pinned tokenizer.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import measure as M  # noqa: E402

ART = REPO / "command-center" / "research" / "RES-0041.json"
SENTINEL = (
    "SUCCESS:RES-0041 in the receipt AND a ranked per-server token table plus a "
    "disable-and-remeasure delta matching the predicted drop"
)


def main() -> int:
    live = M.measure()
    table = live["ranked_per_server_token_table"]
    disable = live["disable_and_remeasure"]
    tok = live["tokenizer"]

    fail = False
    reasons: list[str] = []
    if tok["id"] != "res-0041-gpt2-regex-unigram" or tok["version"] != "v1":
        fail = True
        reasons.append(f"tokenizer pin drifted {tok}")
    if tok.get("not_chars_div_4") is not True:
        fail = True
        reasons.append("tokenizer did not declare not_chars_div_4")
    if len(table) < 2:
        fail = True
        reasons.append("ranked table shorter than 2")
    tokens = [r["tokens"] for r in table]
    if tokens != sorted(tokens, reverse=True):
        fail = True
        reasons.append("table is not rank-sorted by tokens")
    if not disable["tokens_match"]:
        fail = True
        reasons.append(
            f"token drop {disable['measured_drop_tokens']} != predicted {disable['predicted_drop_tokens']}"
        )
    if disable["disabled_server"] != table[0]["id"]:
        fail = True
        reasons.append("did not disable the dominating server")
    if disable["measured_drop_tokens"] != table[0]["tokens"]:
        fail = True
        reasons.append("predicted share is not the disabled row")
    if not all(r["tokenizer_ne_chars_div_4"] for r in table):
        fail = True
        reasons.append("at least one row tokenizer == chars/4")
    if live["eager_total"]["tokens"] != sum(r["tokens"] for r in table):
        fail = True
        reasons.append("eager total != sum of ranked tokens")

    if not ART.is_file() or ART.stat().st_size <= 0:
        fail = True
        reasons.append("artifact missing")
    else:
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if SENTINEL not in text:
            fail = True
            reasons.append("sentinel absent")
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            fail = True
            reasons.append(f"self-declared {doc.get('state')}")
        art_table = doc.get("ranked_per_server_token_table") or []
        live_pairs = [(r["id"], r["tokens"]) for r in table]
        art_pairs = [(r["id"], r["tokens"]) for r in art_table]
        if live_pairs != art_pairs:
            fail = True
            reasons.append(f"artifact table mismatch {art_pairs} vs {live_pairs}")
        art_dis = (doc.get("disable_and_remeasure") or {})
        if art_dis.get("measured_drop_tokens") != disable["measured_drop_tokens"]:
            fail = True
            reasons.append("artifact disable drop mismatch")
        if art_dis.get("tokens_match") is not True:
            fail = True
            reasons.append("artifact tokens_match is not true")

    payload = {
        "probe": "probe1-rank-disable",
        "unit_id": "RES-0041",
        "tokenizer": tok["pin"],
        "ranked": [{"id": r["id"], "tokens": r["tokens"]} for r in table],
        "disable": {
            "server": disable["disabled_server"],
            "predicted": disable["predicted_drop_tokens"],
            "measured": disable["measured_drop_tokens"],
            "match": disable["tokens_match"],
        },
        "fail": fail,
        "reasons": reasons,
    }
    print(json.dumps(payload, sort_keys=True))
    if fail:
        print("FAILED:RES-0041-probe1 " + "; ".join(reasons))
        return 1
    print(
        f"rank0={table[0]['id']} tokens={table[0]['tokens']} "
        f"disable_drop={disable['measured_drop_tokens']} match=True"
    )
    print("SUCCESS:RES-0041-probe1 ranked table and disable-remeasure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
