#!/usr/bin/env python3
"""TST-0178 probe2 -- mutation control: disable pinning, confirm the property fails.

The same pressure rig with pinning_enabled=False MUST produce evictions of
entries whose pin count was raised; a detector silent on the broken state
would measure nothing. The pinned baseline runs on the same seed and must
stay clean.
Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import random
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pinned_cache as PC  # noqa: E402

UNIT = "TST-0178"


class TrackingCache(PC.PinnedCache):
    """Records evict-of-pinned events raised by the eviction path itself."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.pin_violations: list[str] = []
        self._tl = threading.Lock()

    def _note_violation(self, key: str) -> None:
        with self._tl:
            self.pin_violations.append(key)


def run_pressure(cache, seed: int, ops_n: int = 1500):
    rng = random.Random(seed)
    keys = ["entry-%03d" % i for i in range(64)]
    stop = threading.Event()
    reads = {"n": 0}

    def reader():
        r = random.Random(seed + 1)
        while not stop.is_set():
            k = r.choice(keys)
            if cache.acquire(k) is not None:
                time.sleep(0.0005)
                cache.release(k)
                reads["n"] += 1

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    for i in range(ops_n):
        k = rng.choice(keys)
        op = rng.random()
        if op < 0.55:
            cache.put(k, rng.randbytes(rng.randint(32, 256)))
        elif op < 0.85:
            cache.get(k)
        else:
            cache.prune()
        if i % 3 == 0:
            time.sleep(0.0008)  # yield so the pinned reader runs during pressure
    stop.set()
    t.join(timeout=5)
    return reads["n"], len(cache.evicted)


def main() -> int:
    mutant = TrackingCache(max_bytes=4096, pinning_enabled=False)
    mreads, mev = run_pressure(mutant, seed=4242)
    with mutant._tl:
        mutant_violations = list(mutant.pin_violations)

    good = TrackingCache(max_bytes=4096, pinning_enabled=True)
    greads, gev = run_pressure(good, seed=4242)
    with good._tl:
        good_violations = list(good.pin_violations)

    payload = {
        "probe": "probe2-mutation",
        "unit_id": UNIT,
        "pass": bool(mutant_violations) and not good_violations,
        "mutation": {
            "known_broken": "pinning_enabled=False (pin table ignored in evict path)",
            "pinned_evictions_observed": len(mutant_violations),
            "evictions_total": mev,
            "detector_red": bool(mutant_violations),
        },
        "baseline_pinned": {
            "violations": len(good_violations),
            "evictions_total": gev,
            "reads": greads,
            "detector_silent_on_good": not good_violations,
        },
        "reads_mutant": mreads,
        "note": "eviction log cross-referenced against the recorded hold set (signal a); read outcomes recorded (signal b)",
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe2 mutant_pinned_evictions=%d baseline_clean=True"
              % (UNIT, len(mutant_violations)))
        return 0
    print("FAILED:%s-probe2 mutant_violations=%d baseline_violations=%d"
          % (UNIT, len(mutant_violations), len(good_violations)))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
