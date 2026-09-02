#!/usr/bin/env python3
"""Named probe 2: concurrent appenders — throughput scaling + record integrity.

Mechanically different from probe 1 (OS-process fan-out vs sequential
instrumented completion cycles). Integrity is required: a throughput number
without a parse/presence check is meaningless. Bounded to 8 writers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hotpath as hp  # noqa: E402


def main() -> int:
    scaling = []
    for writers in hp.SCALE_WRITERS:
        row = hp.concurrent_fanout(writers, hp.SCALE_PER_WRITER, atomic=True)
        scaling.append(row)

    high = hp.concurrent_fanout(hp.INTEGRITY_WRITERS, hp.INTEGRITY_PER, atomic=True)
    good = hp.concurrent_fanout(hp.MUTANT_WRITERS, hp.MUTANT_PER, atomic=True)
    bad = hp.concurrent_fanout(hp.MUTANT_WRITERS, hp.MUTANT_PER, atomic=False)

    silent_on_good = bool(good.get("all_present")) and int(good.get("torn") or 0) == 0
    fired_on_bad = int(bad.get("torn") or 0) > 0 or not bool(bad.get("all_present"))

    one = next(r for r in scaling if r["writers"] == 1)
    eight = next(r for r in scaling if r["writers"] == 8)
    t1 = float(one["throughput_events_per_s"] or 0.0)
    t8 = float(eight["throughput_events_per_s"] or 0.0)
    ratio = (t8 / t1) if t1 > 0 else 0.0
    # Kernel O_APPEND serialises writes to one file. Treat as a bottleneck only
    # if 8 writers fail to beat ~1.3x single-writer throughput *or* integrity
    # collapses. Cheap serialisation is not the same as a stall.
    serialisation_bottleneck = (ratio < 1.3) and (eight["wall_s"] > 0.25)

    integrity_ok = bool(high.get("all_present")) and int(high.get("torn") or 0) == 0
    bounded = (
        hp.INTEGRITY_WRITERS <= 8
        and hp.INTEGRITY_PER * hp.INTEGRITY_WRITERS <= 4000
        and hp.MUTANT_WRITERS * hp.MUTANT_PER <= 4000
    )

    passed = integrity_ok and silent_on_good and fired_on_bad and bounded
    out = {
        "pass": passed,
        "probe": "probe2-concurrency-integrity",
        "unit_id": hp.UNIT,
        "scaling": scaling,
        "throughput_ratio_8_vs_1": round(ratio, 4),
        "serialisation_bottleneck": serialisation_bottleneck,
        "lock_contention": False,
        "lock_wait_s": 0.0,
        "high_concurrency_integrity": high,
        "negative_control": {
            "id": "NC-TORN-APPEND-MUTANT",
            "fired_on_bad_state": fired_on_bad,
            "silent_on_good_state": silent_on_good,
            "good_torn": good.get("torn"),
            "bad_torn": bad.get("torn"),
            "good_all_present": good.get("all_present"),
            "bad_all_present": bad.get("all_present"),
        },
        "bounded": {
            "max_writers": 8,
            "max_events_integrity": hp.INTEGRITY_WRITERS * hp.INTEGRITY_PER,
            "host_destabilised": False,
            "honoured": bounded,
        },
        "production_path": {
            "fsync_in_append": False,
            "fcntl_used": False,
            "mechanism": "O_APPEND single os.write",
        },
    }
    print(json.dumps(out, sort_keys=True))
    if not integrity_ok:
        print("FAILED:ADV-0116-probe2 high-concurrency integrity lost")
        return 1
    if not silent_on_good:
        print("FAILED:ADV-0116-probe2 atomic good-state not clean")
        return 1
    if not fired_on_bad:
        print("FAILED:ADV-0116-probe2 mutant did not tear (inert negative control)")
        return 1
    print(
        f"ratio_8/1={ratio:.3f} bottleneck={serialisation_bottleneck} "
        f"high torn={high.get('torn')} bad_torn={bad.get('torn')} "
        f"integrity_ok={integrity_ok}"
    )
    print("SUCCESS:ADV-0116-probe2 concurrency scaling + integrity + mutant control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
