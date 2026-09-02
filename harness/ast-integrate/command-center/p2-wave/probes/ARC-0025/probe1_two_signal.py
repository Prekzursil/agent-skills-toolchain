#!/usr/bin/env python3
"""Probe 1: two-signal context (bytes AND tokens) plus 3-repeat latency.

Bytes from Python len(normalized file bytes); tokens from the pinned tokenizer.
Directions must agree: always-on > activated. Empty-inventory control must
reverse the token direction. Latency: three wall-clock repeats per class.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import measure as M  # noqa: E402

COST = REPO / "command-center" / "phase3" / "A4" / "COST.json"
OUT = HERE / "probe1-two-signal.raw.json"


def main() -> int:
    live = M.measure(include_latency=True)
    ts = live["two_signal"]
    lat = live["latency"]
    fail = False
    reasons: list[str] = []

    if not ts["agree_in_direction"]:
        fail = True
        reasons.append(
            f"two-signal disagree bytes={ts['bytes_direction']} "
            f"tokens={ts['tokens_direction']}"
        )
    if ts["bytes_direction"] != "gt" or ts["tokens_direction"] != "gt":
        fail = True
        reasons.append("always-on is not strictly larger than activated on both signals")
    if ts["empty_vs_activated_tokens_direction"] != "lt":
        fail = True
        reasons.append("empty-inventory control did not reverse token direction")
    if ts["empty_inventory_tokens"] != 0:
        fail = True
        reasons.append("empty inventory token count is not 0")

    for cls in ("skill", "workflow", "mcp_mount"):
        block = lat[cls]
        if len(block["runs_ms"]) < 3:
            fail = True
            reasons.append(f"{cls} fewer than 3 repeats")
        if block["median_ms"] < 0:
            fail = True
            reasons.append(f"{cls} negative median")
    if lat["mcp_mount"]["median_ms"] <= 0:
        fail = True
        reasons.append("mcp mount median_ms was not positive (spawn analogue)")

    cost_ok = None
    if COST.is_file():
        cost = json.loads(COST.read_text(encoding="utf-8"))
        if cost["always_on"]["bytes"] != live["always_on"]["bytes"]:
            fail = True
            reasons.append("COST always_on.bytes != live")
        if cost["always_on"]["tokens"] != live["always_on"]["tokens"]:
            fail = True
            reasons.append("COST always_on.tokens != live")
        if cost["activated_set"]["bytes"] != live["activated_set"]["bytes"]:
            fail = True
            reasons.append("COST activated bytes != live")
        if cost["activated_set"]["tokens"] != live["activated_set"]["tokens"]:
            fail = True
            reasons.append("COST activated tokens != live")
        if cost["two_signal"]["agree_in_direction"] is not True:
            fail = True
            reasons.append("COST two_signal.agree_in_direction is not true")
        cost_ok = not any(r.startswith("COST") for r in reasons)
        # latency is live wall-clock; do not require exact match

    raw = {
        "agree_in_direction": ts["agree_in_direction"],
        "bytes_direction": ts["bytes_direction"],
        "tokens_direction": ts["tokens_direction"],
        "always_on_bytes": ts["always_on_bytes"],
        "always_on_tokens": ts["always_on_tokens"],
        "activated_bytes": ts["activated_bytes"],
        "activated_tokens": ts["activated_tokens"],
        "empty_control": ts["empty_vs_activated_tokens_direction"],
        "latency": {
            "skill": lat["skill"],
            "workflow": lat["workflow"],
            "mcp_mount": lat["mcp_mount"],
        },
        "cost_compared": COST.is_file(),
        "cost_ok": cost_ok,
        "fail": fail,
        "reasons": reasons,
    }
    OUT.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"two_signal agree={ts['agree_in_direction']} "
        f"bytes {ts['always_on_bytes']}>{ts['activated_bytes']} ({ts['bytes_direction']}) "
        f"tokens {ts['always_on_tokens']}>{ts['activated_tokens']} ({ts['tokens_direction']}) "
        f"empty_control={ts['empty_vs_activated_tokens_direction']}"
    )
    print(
        f"latency_ms skill={lat['skill']['median_ms']} "
        f"workflow={lat['workflow']['median_ms']} "
        f"mcp={lat['mcp_mount']['median_ms']} repeats=3"
    )
    if fail:
        print("FAILED:ARC-0025-probe1 " + "; ".join(reasons))
        return 1
    print("SUCCESS:ARC-0025-probe1 two-signal context and 3-repeat latency")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
