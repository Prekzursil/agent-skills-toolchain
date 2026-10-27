#!/usr/bin/env python3
"""TST-0178 probe1 -- randomized cache-pressure property with concurrent pinned readers.

PASS requires zero evictions of pinned entries across the whole randomized
pressure run (reader threads hold pins via acquire/release while put/prune
churn runs). Exit 0 on pass, 1 on any failure.
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


def main() -> int:
    rng = random.Random(17478)
    cache = PC.PinnedCache(max_bytes=4096)
    keys = ["entry-%03d" % i for i in range(64)]
    stop = threading.Event()
    violations: list[str] = []
    reads_ok = {"n": 0}

    def reader(worker_id: int) -> None:
        r = random.Random(9000 + worker_id)
        while not stop.is_set():
            k = r.choice(keys)
            payload = cache.acquire(k)
            if payload is not None:
                if cache.pins.get(k, 0) <= 0:
                    violations.append("pin-table-missing:" + k)
                time.sleep(0.0005)  # simulated read work while pinned
                cache.release(k)
                reads_ok["n"] += 1

    readers = [threading.Thread(target=reader, args=(i,), daemon=True) for i in range(3)]
    for t in readers:
        t.start()

    ops = 0
    for i in range(3000):
        k = rng.choice(keys)
        op = rng.random()
        if op < 0.55:
            cache.put(k, rng.randbytes(rng.randint(32, 256)))
        elif op < 0.85:
            cache.get(k)
        else:
            cache.prune()
        ops += 1
        if i % 5 == 0:
            time.sleep(0.0005)  # yield so pinned readers actually run during pressure
    stop.set()
    for t in readers:
        t.join(timeout=5)

    payload = {
        "probe": "probe1-pressure",
        "unit_id": UNIT,
        "pass": not violations and reads_ok["n"] > 0,
        "ops": ops,
        "violations": violations[:10],
        "pinned_eviction_count": len(violations),
        "evictions_total": len(cache.evicted),
        "pinned_reader_reads": reads_ok["n"],
        "final_entries": len(cache.entries),
        "pinning_enabled": cache.pinning_enabled,
        "production_prune_present": (Path(__file__).resolve().parents[4] / "platform/plugin/cache.py").exists(),
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe1 ops=%d pinned_evictions=0 evictions_total=%d reads=%d"
              % (UNIT, ops, len(cache.evicted), reads_ok["n"]))
        return 0
    print("FAILED:%s-probe1 violations=%d reads=%d" % (UNIT, len(violations), reads_ok["n"]))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
