#!/usr/bin/env python3
"""Probe 2: coverage equals an independent object census (not a sample).

The sweep's coverage_count is the number of blobs it actually hashed. The
store object count is taken from a directory walk that does not call
BlobStore.list_object_paths. They must match, including unreferenced extras.

A max_objects=1 cap in the same process must fail the equality, proving the
check discriminates sampling from a full walk. An untouched store in that
same process still reports zero drift when the walk is complete.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

import integrity_sweep as sweep  # noqa: E402

PACKAGES = {
    "pkg.alpha": b"alpha-body-v1",
    "pkg.bravo": b"bravo-body-v1",
    "pkg.charlie": b"charlie-body-v1",
    "pkg.delta": b"delta-body-v1",
}
EXTRAS = [b"orphan-one", b"orphan-two", b"orphan-three"]


def independent_census(objects_root: Path) -> int:
    n = 0
    for dirpath, _, filenames in os.walk(objects_root):
        for name in filenames:
            if name.endswith(".tmp"):
                continue
            if (Path(dirpath) / name).is_file():
                n += 1
    return n


def single_threaded_source() -> bool:
    src = (REPO / "tools" / "marketplace" / "integrity_sweep.py").read_text(
        encoding="utf-8"
    )
    banned = (
        "ThreadPoolExecutor",
        "ProcessPoolExecutor",
        "multiprocessing",
        "concurrent.futures",
        "threading.Thread",
    )
    return not any(token in src for token in banned)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp-0123-p2-") as td:
        root = Path(td)
        store, index = sweep.plant_named_packages(
            root / "full", PACKAGES, extra_blobs=EXTRAS
        )
        clean_store, clean_index = sweep.plant_named_packages(root / "clean", PACKAGES)

        full = sweep.run_sweep(store, index)
        census = independent_census(store.objects)
        expected = len(PACKAGES) + len(EXTRAS)
        sampled = sweep.run_sweep(
            store,
            index,
            budget=sweep.SweepBudget(max_objects=1, max_seconds=30.0),
        )
        untouched = sweep.run_sweep(clean_store, clean_index)

        coverage_ok = (
            full.coverage_count == census == expected == full.store_object_count
            and full.coverage_equals_object_count
            and full.healthy
        )
        sample_discriminates = (
            sampled.coverage_count == 1
            and sampled.store_object_count == expected
            and not sampled.coverage_equals_object_count
            and not sampled.healthy
        )
        clean_ok = untouched.healthy and untouched.findings == []
        bounded = (
            full.workers == 1
            and sampled.workers == 1
            and full.elapsed_seconds < 30.0
            and single_threaded_source()
        )

        result = {
            "probe": "probe2-coverage-equals-object-count",
            "unit_id": "IMP-0123",
            "independent_census": census,
            "coverage_count": full.coverage_count,
            "store_object_count": full.store_object_count,
            "expected": expected,
            "coverage_ok": coverage_ok,
            "sample_discriminates": sample_discriminates,
            "untouched_zero_drift": clean_ok,
            "bounded_single_thread": bounded,
            "elapsed_seconds": full.elapsed_seconds,
            "pass": coverage_ok and sample_discriminates and clean_ok and bounded,
        }
        print(json.dumps(result, sort_keys=True))
        print(
            f"census={census} coverage={full.coverage_count} "
            f"objects={full.store_object_count} sample={sampled.coverage_count} "
            f"clean={clean_ok} bounded={bounded}"
        )
        if not result["pass"]:
            print("FAILED:IMP-0123-probe2 coverage/census mismatch or bound failed")
            return 1
        print(
            "SUCCESS:IMP-0123-probe2 coverage equals object count; sample is not clean"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
