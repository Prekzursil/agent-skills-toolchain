#!/usr/bin/env python3
"""Probe 2: unpartitioned control canary must be found by the SAME search.

Mechanically different from probe 1: this entry point only scores the
control token (paraphrase off) and refuses a vacuous empty haystack.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import detector as D  # noqa: E402
import partition_runtime as PR  # noqa: E402
import scenario as S  # noqa: E402
from canaries import CONTROL_CANARY, PARTITION_CANARY  # noqa: E402

OUT = HERE / "probe2-detector-control.raw.json"


def main() -> int:
    if not D.is_benign_token(CONTROL_CANARY) or not D.is_benign_token(PARTITION_CANARY):
        print("FAILED:CNF-0093-probe2 canary is credential-shaped or too short")
        return 1
    search = D.search_streams

    assembled = S.build_fixtures()
    holding = assembled["holding"]
    streams = PR.non_owning_streams(holding)
    control_rows = search(streams, CONTROL_CANARY, paraphrase=False)
    part_rows = search(streams, PARTITION_CANARY, paraphrase=True)

    nonempty = [r for r in control_rows if r["haystack_bytes"] > 0]
    control_hits = [r for r in control_rows if r["hit_count"] > 0]
    seat_b_ctx = [
        r
        for r in control_rows
        if r["participant"] == "seat-b" and r["stream"] == "private_context"
    ]
    part_in_b_ctx = [
        r
        for r in part_rows
        if r["participant"] == "seat-b"
        and r["stream"] == "private_context"
        and r["hit_count"] > 0
    ]

    payload = {
        "probe": "probe2-detector-control",
        "unit_id": "CNF-0093",
        "same_search": "detector.search_streams",
        "nonempty_haystacks": len(nonempty),
        "control_hit_streams": len(control_hits),
        "seat_b_private_context_control_hits": (
            seat_b_ctx[0]["hit_count"] if seat_b_ctx else 0
        ),
        "seat_b_private_context_partition_hits": (
            part_in_b_ctx[0]["hit_count"] if part_in_b_ctx else 0
        ),
        "pass": False,
    }

    if len(nonempty) < 6:
        payload["error"] = f"vacuous haystacks nonempty={len(nonempty)}"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:CNF-0093-probe2 vacuous search")
        return 1
    if not control_hits:
        payload["error"] = "unpartitioned control canary not found by same search"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:CNF-0093-probe2 detector-failure")
        return 1
    if not seat_b_ctx or seat_b_ctx[0]["hit_count"] < 1:
        payload["error"] = "control canary missing from seat-b unpartitioned context"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:CNF-0093-probe2 unpartitioned field miss")
        return 1
    if part_in_b_ctx:
        payload["error"] = "partitioned canary present in seat-b private context"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:CNF-0093-probe2 partition leak in control view")
        return 1

    payload["pass"] = True
    payload["control_rows"] = control_rows
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "control_hit_streams="
        + str(len(control_hits))
        + " nonempty_haystacks="
        + str(len(nonempty))
        + " seat_b_context_control_hits="
        + str(seat_b_ctx[0]["hit_count"])
        + " seat_b_context_partition_hits=0"
        + " same_search=detector.search_streams"
    )
    print("SUCCESS:CNF-0093-probe2 unpartitioned control found by same search")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
