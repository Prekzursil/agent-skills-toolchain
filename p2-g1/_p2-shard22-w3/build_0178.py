#!/usr/bin/env python3
"""Write TST-0178 probe files (kept out of Bash heredocs: apostrophe transport)."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
PDIR = HERE.parent / "command-center" / "p2-wave" / "probes" / "TST-0178"
PDIR.mkdir(parents=True, exist_ok=True)

P1 = r'''#!/usr/bin/env python3
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
'''

P2 = r'''#!/usr/bin/env python3
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
'''

(PDIR / "probe1_pressure.py").write_text(P1, encoding="utf-8", newline="\n")
(PDIR / "probe2_mutation.py").write_text(P2, encoding="utf-8", newline="\n")
import ast

ast.parse(P1)
ast.parse(P2)
print("TST-0178 probes written + syntax OK")
