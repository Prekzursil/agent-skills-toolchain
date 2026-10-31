#!/usr/bin/env python3
"""IMP-0068 probe1: index rebuilt from blobs is semantically the original.

Independent of the unittest file: builds a fresh registry, corrupts the
index (truncate AND delete), rebuilds from the stored package blobs alone,
and requires normalised semantic equality. Includes an orphan blob (a
package the index forgot) to prove rebuild handles an inconsistent set.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

from storage import RegistryStorage, indexes_semantically_equal  # noqa: E402

PACKAGES = [
    {"name": "probe-alpha", "version": "1.0.0", "summary": "a"},
    {"name": "probe-beta", "version": "2.0.0", "summary": "b"},
    {"name": "probe-gamma", "version": "3.0.0", "summary": "c"},
]


def main() -> int:
    checks = {}
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        st = RegistryStorage(root)
        for p in PACKAGES:
            st.put_package(p, ("blob-" + p["name"]).encode() + b"\n")
        original = st.read_index()
        r1 = st.rebuild_from_blobs()
        checks["rebuild_equals_original"] = indexes_semantically_equal(original, r1)
        raw_idx = st.index_path.read_bytes()
        st.index_path.write_bytes(raw_idx[: len(raw_idx) // 3])
        checks["rebuild_after_truncate"] = indexes_semantically_equal(
            original, st.rebuild_from_blobs())
        st.index_path.unlink()
        checks["rebuild_after_delete"] = indexes_semantically_equal(
            original, st.rebuild_from_blobs())
        stem = "e" * 64
        (st.blob_dir / (stem + ".json")).write_text(
            json.dumps({"name": "orphan-pkg", "version": "0.1.0"},
                       sort_keys=True) + "\n", encoding="utf-8")
        (st.blob_dir / (stem + ".bin")).write_bytes(b"orphan\n")
        rebuilt = st.rebuild_from_blobs()
        names = {p["name"] for p in rebuilt["plugins"]}
        checks["orphan_recovered"] = "orphan-pkg" in names
        checks["orphan_absent_before"] = "orphan-pkg" not in {
            p["name"] for p in original["plugins"]}
        checks["index_readable"] = st.read_index() == rebuilt
    out = {
        "probe": "probe1-rebuild-from-blobs",
        "unit_id": "IMP-0068",
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, sort_keys=True))
    if not all(checks.values()):
        bad = [k for k, v in checks.items() if not v]
        print("FAILED:IMP-0068-probe1 %s" % bad)
        return 1
    print("SUCCESS:IMP-0068-probe1 rebuild from blobs is semantically the original")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
