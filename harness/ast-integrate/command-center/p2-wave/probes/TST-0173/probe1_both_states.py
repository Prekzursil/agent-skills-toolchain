#!/usr/bin/env python3
"""Named probe 1: intact hit has no refetch; one bit-flip is caught and recovered."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    KEY,
    Origin,
    flip_bit,
    make_cache,
    patterned_payload,
    recovery_ok,
    sha256_bytes,
)

from artifact_cache.store import EVENT_CHECKSUM_MISMATCH  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0173-probe1 {msg}")
    return 1


def main() -> int:
    payload = patterned_payload()
    with tempfile.TemporaryDirectory(prefix="tst0173-p1-") as raw:
        tmp = Path(raw)
        origin = Origin(payload)
        cache = make_cache(tmp / "cache", origin)

        first = cache.get(KEY)
        if first.source != "fetch":
            return fail(f"first get source={first.source} want=fetch")
        if origin.fetch_count != 1:
            return fail(f"fill fetches={origin.fetch_count} want=1")
        if first.digest != origin.digest:
            return fail("fill digest mismatch vs origin")

        second = cache.get(KEY)
        if second.source != "cache":
            return fail(f"intact get source={second.source} want=cache")
        if second.mismatch:
            return fail("intact get reported mismatch")
        if origin.fetch_count != 1:
            return fail(f"intact refetch: fetches={origin.fetch_count} want=1")
        if second.payload != payload:
            return fail("intact get returned different bytes")
        if cache.stats["hits"] < 1:
            return fail("intact get did not increment hits")
        if cache.stats["mismatches"] != 0:
            return fail("intact path counted a mismatch")
        if cache.stats["quarantines"] != 0:
            return fail("intact path quarantined")

        path = cache.payload_path(KEY)
        plant = flip_bit(path, offset=17, bit=3)
        if not plant["changed"]:
            return fail("bit flip did not change bytes")
        corrupt_digest = plant["after_digest"]
        if corrupt_digest == origin.digest:
            return fail("planted flip collided with origin digest")

        fetches_before = origin.fetch_count
        crashed = False
        crash_exc = None
        try:
            recovered = cache.get(KEY)
        except Exception as exc:  # noqa: BLE001 — probe must record crash vs recover
            crashed = True
            crash_exc = type(exc).__name__
            return fail(f"corruption crashed reader: {crash_exc}")

        mismatches = [e for e in recovered.events if e.get("type") == EVENT_CHECKSUM_MISMATCH]
        if not mismatches:
            mismatches = [
                e for e in cache.events if e.get("type") == EVENT_CHECKSUM_MISMATCH
            ]
        verdict = recovery_ok(
            origin=origin,
            result_digest=recovered.digest,
            result_payload=recovered.payload,
            served_digest_before_recovery=corrupt_digest,
            mismatch_events=mismatches,
            fetches_before=fetches_before,
            fetches_after=origin.fetch_count,
            crashed=crashed,
        )
        if not verdict["ok"]:
            return fail(f"recovery assertions failed {verdict}")

        on_disk = sha256_bytes(cache.payload_path(KEY).read_bytes())
        if on_disk != origin.digest:
            return fail(f"post-recovery file hash {on_disk} != {origin.digest}")

        qdirs = list((tmp / "cache" / "quarantine").iterdir())
        if len(qdirs) < 1:
            return fail("quarantine directory empty after mismatch")
        q_payload = next(qdirs[0].rglob("payload"), None)
        if q_payload is None:
            return fail("quarantine missing original payload")
        q_digest = sha256_bytes(q_payload.read_bytes())
        if q_digest != corrupt_digest:
            return fail("quarantine did not preserve corrupt bytes")

        payload_out = {
            "pass": True,
            "probe": "probe1-both-states",
            "unit_id": "TST-0173",
            "intact": {
                "fill_source": first.source,
                "second_source": second.source,
                "fetches": origin.fetch_count,
                "hits": cache.stats["hits"],
                "no_refetch": True,
            },
            "corrupted": {
                "plant": plant,
                "mismatch_event": mismatches[0],
                "recovered_source": recovered.source,
                "recovered_digest": recovered.digest,
                "on_disk_digest": on_disk,
                "authoritative_digest": origin.digest,
                "quarantine_dirs": len(qdirs),
                "quarantine_preserved_corrupt": q_digest == corrupt_digest,
            },
            "stats": cache.stats,
            "recovery": verdict,
        }
        print(json.dumps(payload_out, sort_keys=True))
        print(
            "intact_no_refetch=True mismatch_event=True "
            f"recovered={recovered.digest[:12]} origin={origin.digest[:12]}"
        )
        print("SUCCESS:TST-0173-probe1 both-states intact-hit and bit-flip recovery")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
