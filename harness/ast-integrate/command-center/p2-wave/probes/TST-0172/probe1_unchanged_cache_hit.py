#!/usr/bin/env python3
"""Probe 1: unchanged package IS served from cache (both-states).

The AlwaysRefetch mutant never hits — if this probe could pass on that
mutant, the detector would be dead. The production CAS must hit.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import measure_unchanged_served_from_cache  # noqa: E402

ART = REPO / "command-center/receipts/TST-0172.json"
SENTINEL = "SUCCESS:TST-0172"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0172-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0172-p1-") as tmp:
        live = measure_unchanged_served_from_cache(Path(tmp))

    print(json.dumps(live, indent=2, sort_keys=True))

    if not live.get("served_from_cache"):
        return fail("unchanged package was not served from cache")
    if not live.get("always_refetch_never_hits"):
        return fail("always-refetch mutant hit (detector vacuous)")
    if not live.get("both_states"):
        return fail("both-states failed")
    if live.get("second_source") != "hit":
        return fail(f"second observe source={live.get('second_source')}")
    if not live.get("cache_key_equals_sha256_payload"):
        return fail("cache key is not sha256(payload)")
    if live.get("hits_after_second", 0) <= live.get("hits_after_first", 0):
        return fail("hits counter did not advance on second observe")
    if live.get("rebuilds") != 0:
        return fail("rebuilds advanced on unchanged observe")

    if ART.is_file() and ART.stat().st_size > 0:
        text = ART.read_text(encoding="utf-8")
        if SENTINEL not in text:
            return fail("receipt-sentinel-absent")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"receipt-self-declared {st}")
        if not doc.get("unchanged_package_served_from_cache"):
            return fail("receipt-flag-cache-hit-absent")

    print(
        f"cache_key={live['cache_key']} hits={live['hits_after_second']} "
        f"source={live['second_source']} always_refetch_hits=0"
    )
    print("SUCCESS:TST-0172-probe1 unchanged package is served from cache")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
