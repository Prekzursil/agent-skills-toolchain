#!/usr/bin/env python3
"""Probe 1: known-present control must pass before scarcity is interpreted.

Both states: the query that returns langchain-ai/langgraph may interpret volume.
The query that misses it must refuse a scarcity claim (empty is detector-failure).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sweep as S  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0024-probe1 {msg}")
    return 1


def load(name: str) -> dict:
    return json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))


def main() -> int:
    present = load("search_known_present.json")
    missing = load("search_control_miss.json")

    good = S.interpret_volume(present["items"], S.KNOWN_PRESENT_REPO)
    if not good["known_present_found"]:
        return fail("known-present query did not return langchain-ai/langgraph")
    if not good["scarcity_claim_allowed"]:
        return fail("known-present pass must admit a volume interpretation")
    if good["verdict"] != "CONTROL-PASS":
        return fail(f"good verdict={good['verdict']}")
    if good["volume"] != 1:
        return fail(f"expected unique count 1 got {good['volume']}")

    bad = S.interpret_volume(missing["items"], S.KNOWN_PRESENT_REPO)
    if bad["known_present_found"]:
        return fail("control-miss fixture must not contain known-present")
    if bad["scarcity_claim_allowed"]:
        return fail("empty result must not be interpreted as scarcity")
    if bad["sparse"] is not None or bad["volume"] is not None:
        return fail("refused interpretation must leave sparse/volume null")
    if bad["interpretation"] != "REFUSED":
        return fail(f"missing interpretation={bad['interpretation']}")

    print(json.dumps({"good": good, "bad": bad, "pass": True}, indent=1, sort_keys=True))
    print(
        "known_present_found=True volume_admitted=True "
        "empty_refused=True scarcity_not_claimed_on_miss=True"
    )
    print("SUCCESS:WFA-0024-probe1 known-present control both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
