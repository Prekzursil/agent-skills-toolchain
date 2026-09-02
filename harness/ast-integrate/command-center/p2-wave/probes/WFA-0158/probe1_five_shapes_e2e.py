#!/usr/bin/env python3
"""Probe 1: five-plus injection shapes through the live ingestion path.

Each hostile payload must be neutralized AND the candidate's legitimate
content must survive. Downstream prompt is captured verbatim. A drop
quarantine fails. Clean candidate is the silent-on-good control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import payloads as P  # noqa: E402
import quarantine as Q  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0158-probe1 {msg}")
    return 1


def main() -> int:
    hostiles = P.hostile()
    if len(hostiles) < 5:
        return fail(f"need >=5 hostile shapes, got {len(hostiles)}")

    rows = []
    for payload in P.PAYLOADS:
        cand = Q.ingest(payload)
        if payload["id"] != "clean" and Q.FENCE_CLOSE_PREFIX in cand["body"]:
            return fail(f"{payload['id']} forged fence closer survived neutralization")
        trial = Q.run_trial(payload, fence=True, drop=False, splitter=Q.split_channels)
        print(
            f"shape={trial['payload_id']} kind={trial['kind']} "
            f"neutralized={trial['neutralized']} survived={trial['content_survived']} "
            f"dropped={trial['dropped']} fired={trial['fired_canaries']} "
            f"canary_data={trial['canary_in_data']} canary_inst={trial['canary_in_instruction']}"
        )
        if not trial["prompt_verbatim"].strip():
            return fail(f"{payload['id']} prompt_verbatim empty")
        if payload["id"] == "clean":
            if trial["fired_canaries"] or trial["canary_in_instruction"]:
                return fail("clean candidate leaked a canary into instruction")
            if not trial["content_survived"] or trial["dropped"]:
                return fail("clean candidate content did not survive")
        else:
            if not Q.verdict_ok(trial):
                return fail(f"{payload['id']} quarantine verdict failed")
        rows.append(
            {
                "id": trial["payload_id"],
                "neutralized": trial["neutralized"],
                "content_survived": trial["content_survived"],
                "dropped": trial["dropped"],
                "fired": trial["fired_canaries"],
            }
        )

    drop = Q.run_trial(P.by_id("direct-override"), fence=True, drop=True)
    if drop["content_survived"] or not drop["dropped"]:
        return fail("drop mutant was not rejected by the survival predicate")
    print(
        "NEGATIVE_CONTROL_VERBATIM="
        "On drop=True ingest of direct-override, dropped=True and "
        f"content_survived={drop['content_survived']}. The check REJECTS a "
        "quarantine that discards the candidate instead of rendering it as DATA."
    )

    print(
        json.dumps(
            {
                "probe": "probe1-five-shapes-e2e",
                "unit_id": "WFA-0158",
                "hostile_shapes": len(hostiles),
                "rows": rows,
                "drop_mutant_rejected": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"fired_on_bad=True silent_on_good=True shapes={len(hostiles)} "
        "drop_rejected=True"
    )
    print("SUCCESS:WFA-0158-probe1 five shapes neutralized; content survived")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
