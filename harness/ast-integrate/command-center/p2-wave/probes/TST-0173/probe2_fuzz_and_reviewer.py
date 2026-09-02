#!/usr/bin/env python3
"""Named probe 2: 500 fuzz corruptions + SilentCache detector liveness.

Independent of probe 1: re-hashes origin bytes and the post-recovery file
without trusting IntegrityCache.report() for the digest equality claim.
"""

from __future__ import annotations

import json
import random
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    FUZZ_N,
    SEED,
    Origin,
    SilentCache,
    flip_bit,
    make_cache,
    multi_byte,
    patterned_payload,
    recovery_ok,
    sha256_bytes,
)

from artifact_cache.store import EVENT_CHECKSUM_MISMATCH  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0173-probe2 {msg}")
    return 1


def run_one(cache, origin: Origin, key: str, plant: dict) -> dict:
    path = cache.payload_path(key)
    corrupt_digest = plant["after_digest"]
    fetches_before = origin.fetch_count
    crashed = False
    crash_exc = None
    try:
        recovered = cache.get(key)
    except Exception as exc:  # noqa: BLE001
        crashed = True
        crash_exc = type(exc).__name__
        return {
            "ok": False,
            "crashed": True,
            "crash_exc": crash_exc,
            "key": key,
            "plant": plant,
        }
    mismatches = [e for e in recovered.events if e.get("type") == EVENT_CHECKSUM_MISMATCH]
    if not mismatches:
        mismatches = [e for e in cache.events if e.get("type") == EVENT_CHECKSUM_MISMATCH and e.get("key") == key]
    independent_file = sha256_bytes(cache.payload_path(key).read_bytes())
    independent_origin = sha256_bytes(origin.payload)
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
    file_matches = independent_file == independent_origin == origin.digest
    ok = bool(verdict["ok"] and file_matches and not crashed)
    return {
        "ok": ok,
        "key": key,
        "plant": plant,
        "crashed": crashed,
        "crash_exc": crash_exc,
        "independent_file_digest": independent_file,
        "independent_origin_digest": independent_origin,
        "mismatch_event": mismatches[0] if mismatches else None,
        "recovery": verdict,
        "file_matches_authoritative": file_matches,
        "path": str(path),
    }


def main() -> int:
    payload = patterned_payload()
    rng = random.Random(SEED)
    with tempfile.TemporaryDirectory(prefix="tst0173-p2-") as raw:
        tmp = Path(raw)

        origin_silent = Origin(payload)
        silent_inner = make_cache(tmp / "silent", origin_silent)
        silent = SilentCache(silent_inner)
        silent.fill("silent-pkg")
        plant_s = flip_bit(silent.payload_path("silent-pkg"), offset=9, bit=1)
        silent_got = silent.get_silent("silent-pkg")
        silent_served_corrupt = silent_got["payload"] != origin_silent.payload
        silent_no_refetch = origin_silent.fetch_count == 1
        silent_no_mismatch = not silent_got["events"]
        detector_fires = silent_served_corrupt and silent_no_refetch and silent_no_mismatch
        if not detector_fires:
            return fail(
                "SilentCache did not serve corrupt bytes; detector control is dead"
            )
        silent_verdict = recovery_ok(
            origin=origin_silent,
            result_digest=silent_got["digest"],
            result_payload=silent_got["payload"],
            served_digest_before_recovery=plant_s["after_digest"],
            mismatch_events=[],
            fetches_before=1,
            fetches_after=origin_silent.fetch_count,
            crashed=False,
        )
        if silent_verdict["ok"]:
            return fail("recovery_ok passed SilentCache; assertions are vacuous")

        origin = Origin(payload)
        cache = make_cache(tmp / "cache", origin)
        rows = []
        n_bit = 0
        n_multi = 0
        for i in range(FUZZ_N):
            key = f"pkg-{i:04d}"
            filled = cache.get(key)
            if filled.digest != origin.digest:
                return fail(f"{key} fill digest mismatch")
            path = cache.payload_path(key)
            if i % 2 == 0:
                plant = flip_bit(path, offset=rng.randrange(len(payload)), bit=rng.randrange(8))
                n_bit += 1
            else:
                plant = multi_byte(path, rng)
                n_multi += 1
            if not plant["changed"]:
                return fail(f"{key} corruption did not change bytes")
            row = run_one(cache, origin, key, plant)
            if not row["ok"]:
                return fail(f"trial {i} {key} failed {json.dumps(row, sort_keys=True)[:800]}")
            if i < 5 or i in (249, 499):
                rows.append(
                    {
                        "i": i,
                        "key": key,
                        "kind": plant["kind"],
                        "offset": plant["offset"],
                        "corrupt_digest": plant["after_digest"],
                        "recovered_digest": row["independent_file_digest"],
                        "mismatch_type": (row["mismatch_event"] or {}).get("type"),
                    }
                )

        qn = len(list((tmp / "cache" / "quarantine").iterdir()))
        if qn < FUZZ_N:
            return fail(f"quarantine count {qn} < {FUZZ_N}")
        if cache.stats["mismatches"] < FUZZ_N:
            return fail(f"mismatch stats {cache.stats['mismatches']} < {FUZZ_N}")
        if cache.stats["refetches"] < FUZZ_N:
            return fail(f"refetch stats {cache.stats['refetches']} < {FUZZ_N}")

        payload_out = {
            "pass": True,
            "probe": "probe2-fuzz-and-reviewer",
            "unit_id": "TST-0173",
            "fuzz_n": FUZZ_N,
            "n_single_bit": n_bit,
            "n_multi_byte": n_multi,
            "all_recovered": True,
            "crashes": 0,
            "silent_serves": 0,
            "quarantine_dirs": qn,
            "stats": cache.stats,
            "sample": rows,
            "silent_cache_control": {
                "served_corrupt": silent_served_corrupt,
                "no_refetch": silent_no_refetch,
                "recovery_ok_on_silent": silent_verdict["ok"],
                "detector_fires": True,
                "corrupt_digest": plant_s["after_digest"],
            },
            "authoritative_digest": origin.digest,
        }
        print(json.dumps(payload_out, sort_keys=True))
        print(
            f"fuzz={FUZZ_N} bit={n_bit} multi={n_multi} "
            f"quarantine={qn} silent_detector=True"
        )
        print("SUCCESS:TST-0173-probe2 fuzz-500 plus SilentCache negative control")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
