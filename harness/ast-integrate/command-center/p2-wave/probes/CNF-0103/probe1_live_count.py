#!/usr/bin/env python3
"""Probe 1: live known-count walk/hash/install. No silent zero. Prefix exercised."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from measure import OUT, SENTINEL, UNIT, live, payload_from_doc, verdict  # noqa: E402

ART = REPO / OUT


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print(f"FAILED:{UNIT}-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        print(f"FAILED:{UNIT}-probe1 unit_id {doc.get('unit_id')}")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print(f"FAILED:{UNIT}-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:{UNIT}-probe1 self-declared {doc.get('state')}")
        return 1

    measured = live()
    bundle = measured["bundle"]
    det = measured["both_states"]
    state, why = verdict(bundle, det)
    print(
        json.dumps(
            {
                "probe": "probe1-live-count",
                "state": state,
                "why": why,
                "known_count": bundle["inventory"]["known_count"],
                "long_chars": bundle["inventory"]["long_full_chars"],
                "prefix_invocation_count": bundle["prefix_invocation_count"],
                "silent_zero_ids": bundle["silent_zero_ids"],
                "precedent_raised": bundle["naive_device"].get("raised"),
                "outcomes": {r["id"]: r["outcome"] for r in bundle["results"]},
            },
            sort_keys=True,
        )
    )
    if state != "SUCCESS":
        print(f"FAILED:{UNIT}-probe1 {why}")
        return 1
    payload = payload_from_doc(doc)
    if int(payload.get("known_fixture_count") or 0) != int(bundle["inventory"]["known_count"]):
        print("FAILED:CNF-0103-probe1 known_fixture_count drift vs live")
        return 1
    if not payload.get("tests", {}).get("extended_length_prefix_exercised"):
        print("FAILED:CNF-0103-probe1 artifact did not record prefix exercise")
        return 1
    art_outcomes = {r["id"]: r["outcome"] for r in payload.get("results") or []}
    live_outcomes = {r["id"]: r["outcome"] for r in bundle["results"]}
    if art_outcomes != live_outcomes:
        print("FAILED:CNF-0103-probe1 outcome drift")
        print(" artifact", art_outcomes)
        print(" live", live_outcomes)
        return 1
    print(
        f"known={bundle['inventory']['known_count']} "
        f"prefix_calls={bundle['prefix_invocation_count']} "
        f"silent_zero={bundle['silent_zero_ids']}"
    )
    print(f"SUCCESS:{UNIT}-probe1 live named tools reported known count or explicit error")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
