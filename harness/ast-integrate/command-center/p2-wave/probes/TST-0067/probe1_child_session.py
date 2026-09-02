#!/usr/bin/env python3
"""Probe 1: child in the same session observes the injected value.

Also records the setx-class persistent-store miss: setter self-read is NEW,
consumer process still sees unset. Agreement of the writer with itself is
not treated as a pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0067-probe1 {msg}")
    return 1


def main() -> int:
    doc = S.require_receipt()
    live = S.measure_persistent_miss_and_session_hit()
    print(json.dumps({"probe": "probe1-child-session", "unit_id": "TST-0067", **live}, sort_keys=True))
    if not live["pass"]:
        return fail("persistent-miss / session-hit measurement did not pass")
    hit = live["session_hit"]
    miss = live["persistent_miss"]
    if hit["consumer_userspace"] != S.NEW or hit["consumer_kernel"] != S.NEW:
        return fail("child did not observe NEW in both consumer signals")
    if miss["consumer_userspace"] is not None or miss["consumer_kernel"] is not None:
        return fail("persistent-store analog leaked into the session child")
    if miss["setter_self_read"] != S.NEW:
        return fail("setter did not persist NEW")
    if miss["writer_consumer_agree"]:
        return fail("writer-consumer falsely agreed on the persistent miss")
    pairs = S.pairs_from_receipt(doc)
    rec_hit = (pairs.get("session_hit") or {}).get("consumer_userspace")
    if rec_hit != hit["consumer_userspace"]:
        return fail(f"receipt session consumer {rec_hit!r} != live {hit['consumer_userspace']!r}")
    rec_miss = (pairs.get("persistent_miss") or {}).get("consumer_userspace")
    if rec_miss != miss["consumer_userspace"]:
        return fail(f"receipt persistent consumer {rec_miss!r} != live {miss['consumer_userspace']!r}")
    print(
        f"session_child_saw={hit['consumer_userspace']!r} "
        f"persistent_child_saw={miss['consumer_userspace']!r} "
        f"setter_self_read={miss['setter_self_read']!r} "
        f"signals_agree={hit['signals_agree']}"
    )
    print("SUCCESS:TST-0067-probe1 child observes NEW in-session; persistent analog misses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
