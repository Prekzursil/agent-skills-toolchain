#!/usr/bin/env python3
"""Probe 1: a mutated blob is identified by the sweep, naming the index entry.

Both-states control in the same process: an untouched clone of the store
reports zero drift. A detector that is red on both, or green on both, fails.
"""
from __future__ import annotations

import json
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
}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp-0123-p1-") as td:
        root = Path(td)
        store, index = sweep.plant_named_packages(root / "dirty", PACKAGES)
        clean_store, clean_index = sweep.plant_named_packages(root / "clean", PACKAGES)

        before = sweep.run_sweep(store, index)
        untouched = sweep.run_sweep(clean_store, clean_index)
        if not before.healthy or not untouched.healthy:
            print("FAILED:IMP-0123-probe1 pre-mutation not healthy")
            print(
                json.dumps(
                    {"before": before.as_dict(), "untouched": untouched.as_dict()}
                )
            )
            return 1

        bravo = next(e for e in index.entries if e["id"] == "pkg.bravo")
        store.mutate_in_place(bravo["digest"])

        after = sweep.run_sweep(store, index)
        still_clean = sweep.run_sweep(clean_store, clean_index)

        named = after.named_drift_entries
        fired_on_bad = "pkg.bravo" in named
        silent_on_good = still_clean.findings == [] and still_clean.healthy
        blob_named = any(
            f.kind == "blob-digest-mismatch" and "pkg.bravo" in f.named_entries
            for f in after.findings
        )
        index_named = any(
            f.kind == "index-blob-mismatch" and "pkg.bravo" in f.named_entries
            for f in after.findings
        )

        result = {
            "probe": "probe1-mutated-blob-named",
            "unit_id": "IMP-0123",
            "fired_on_bad": fired_on_bad,
            "silent_on_good": silent_on_good,
            "named_entries": named,
            "blob_walk_named_pkg_bravo": blob_named,
            "index_walk_named_pkg_bravo": index_named,
            "dirty_coverage": after.coverage_count,
            "dirty_object_count": after.store_object_count,
            "clean_findings": len(still_clean.findings),
            "pass": fired_on_bad and silent_on_good and blob_named and index_named,
        }
        print(json.dumps(result, sort_keys=True))
        print(
            f"named={named} fired_on_bad={fired_on_bad} "
            f"silent_on_good={silent_on_good} blob={blob_named} index={index_named}"
        )
        if not result["pass"]:
            print("FAILED:IMP-0123-probe1 mutated blob not named or control fired")
            return 1
        print("SUCCESS:IMP-0123-probe1 mutated blob is named; untouched store silent")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
