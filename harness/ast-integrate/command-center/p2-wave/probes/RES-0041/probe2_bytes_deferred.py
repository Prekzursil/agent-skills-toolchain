#!/usr/bin/env python3
"""Probe 2: independent UTF-8 byte signal + deferred vs eager.

Different data field from probe 1 (bytes, not tokenizer tokens) and a second
question (deferred catalog vs eager full schemas). Not a re-run of probe 1.
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


def main() -> int:
    live = M.measure()
    disable = live["disable_and_remeasure"]
    dve = live["deferred_vs_eager"]
    two = live["two_signal"]
    table = live["ranked_per_server_token_table"]

    fail = False
    reasons: list[str] = []

    if not disable["bytes_match"]:
        fail = True
        reasons.append(
            f"byte drop {disable['measured_drop_bytes']} != predicted {disable['predicted_drop_bytes']}"
        )
    if not dve["deferred_cheaper_tokens"] or not dve["deferred_cheaper_bytes"]:
        fail = True
        reasons.append("deferred is not cheaper than eager on both fields")
    if dve["token_savings"] <= 0 or dve["byte_savings"] <= 0:
        fail = True
        reasons.append("zero or negative deferred savings")
    if not two["dominator_agrees"]:
        fail = True
        reasons.append("token dominator != byte dominator")
    if not two["every_row_tokenizer_ne_chars_div_4"]:
        fail = True
        reasons.append("tokenizer collapsed to chars/4")
    bytes_order = [r["bytes"] for r in sorted(table, key=lambda r: -r["bytes"])]
    if bytes_order != sorted(bytes_order, reverse=True):
        fail = True
        reasons.append("byte ranking broken")

    if not ART.is_file():
        fail = True
        reasons.append("artifact missing")
    else:
        doc = json.loads(ART.read_text(encoding="utf-8"))
        art_dve = doc.get("deferred_vs_eager") or {}
        if art_dve.get("eager_tokens") != dve["eager_tokens"]:
            fail = True
            reasons.append("artifact eager_tokens mismatch")
        if art_dve.get("deferred_tokens") != dve["deferred_tokens"]:
            fail = True
            reasons.append("artifact deferred_tokens mismatch")
        if art_dve.get("deferred_cheaper_tokens") is not True:
            fail = True
            reasons.append("artifact did not record deferred cheaper")
        art_two = doc.get("two_signal") or {}
        if art_two.get("dominator_agrees") is not True:
            fail = True
            reasons.append("artifact two_signal dominator_agrees is not true")
        if (doc.get("disable_and_remeasure") or {}).get("bytes_match") is not True:
            fail = True
            reasons.append("artifact bytes_match is not true")

    payload = {
        "probe": "probe2-bytes-deferred",
        "unit_id": "RES-0041",
        "byte_disable": {
            "server": disable["disabled_server"],
            "predicted": disable["predicted_drop_bytes"],
            "measured": disable["measured_drop_bytes"],
            "match": disable["bytes_match"],
        },
        "deferred_vs_eager": {
            "eager_tokens": dve["eager_tokens"],
            "deferred_tokens": dve["deferred_tokens"],
            "token_savings": dve["token_savings"],
            "eager_bytes": dve["eager_bytes"],
            "deferred_bytes": dve["deferred_bytes"],
            "byte_savings": dve["byte_savings"],
        },
        "dominator_agrees": two["dominator_agrees"],
        "fail": fail,
        "reasons": reasons,
    }
    print(json.dumps(payload, sort_keys=True))
    if fail:
        print("FAILED:RES-0041-probe2 " + "; ".join(reasons))
        return 1
    print(
        f"bytes_drop={disable['measured_drop_bytes']} "
        f"deferred={dve['deferred_tokens']}<eager={dve['eager_tokens']} "
        f"savings={dve['token_savings']}"
    )
    print("SUCCESS:RES-0041-probe2 byte signal and deferred-vs-eager")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
