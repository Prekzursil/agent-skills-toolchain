#!/usr/bin/env python3
"""Probe 1: per-file three-way classification after LF normalisation.

Does not call git, does not read mtimes, does not invoke sync.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import audit_common as A  # noqa: E402
import controls as C  # noqa: E402
import fixtures as F  # noqa: E402
import lib_classify as L  # noqa: E402

from audit_common import FIXTURE_LIVE, FIXTURE_REPO  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:ADV-0017-probe1 {msg}")
    return 1


def main() -> int:
    if not FIXTURE_REPO.is_dir() or not FIXTURE_LIVE.is_dir():
        return _fail("fixture trees missing (emit writes them; probes are read-only)")
    before = C.snapshot(FIXTURE_REPO, FIXTURE_LIVE)
    repo = A.iter_rel_files(FIXTURE_REPO)
    live = A.iter_rel_files(FIXTURE_LIVE)
    snap = L.classify_trees(repo, live)
    eol = C.eol_control(FIXTURE_REPO, FIXTURE_LIVE, F.EOL_PATH)
    nowrite = C.finish_no_write(FIXTURE_REPO, FIXTURE_LIVE, before)
    host = A.host_candidates()
    payload = {
        "probe": "probe1-three-way-line-set-lf",
        "unit_id": "ADV-0017",
        "instrument": "three-way line-set classification after LF normalisation",
        "disclosed_synthetic_fixtures": True,
        "not_windows_live_estate": True,
        "host_candidates": host,
        "host_live_present": A.host_live_present(),
        "repo_root": str(FIXTURE_REPO),
        "live_root": str(FIXTURE_LIVE),
        "union_files": snap["union_files"],
        "paired_files": snap["paired_files"],
        "counts": snap["counts"],
        "either_direction_destroy_n": snap["either_direction_destroy_n"],
        "either_direction_destroy_paths": snap["either_direction_destroy_paths"],
        "live_larger_paths": snap["live_larger_paths"],
        "repo_larger_paths": snap["repo_larger_paths"],
        "eol_control": eol,
        "no_write": {"result": nowrite["result"], "pass": nowrite["pass"]},
        "rows": [
            {
                k: r[k]
                for k in (
                    "path",
                    "classification",
                    "size_direction",
                    "repo_bytes",
                    "live_bytes",
                    "repo_only_line_n",
                    "live_only_line_n",
                    "shared_line_n",
                    "repo_only_lines",
                    "live_only_lines",
                    "destroy_if_either_direction",
                    "destroy_if_sync_live_to_repo",
                    "destroy_if_sync_repo_to_live",
                    "lf_identical",
                    "bytes_identical",
                )
            }
            for r in snap["rows"]
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not eol["pass"]:
        return _fail("EOL control classified as content divergence")
    if not nowrite["pass"]:
        return _fail("no-write control failed")
    if snap["either_direction_destroy_n"] < 1:
        return _fail("fixture has no BOTH-UNIQUE pair")
    if snap["counts"].get("EOL-ONLY", 0) + snap["counts"].get("BYTE-IDENTICAL-LF", 0) < 1:
        return _fail("no identical-after-LF pair")
    pinned_ok = True
    by_path = {r["path"]: r for r in snap["rows"]}
    for rel in A.CATALOG_PIN_LIVE_LARGER:
        row = by_path.get(rel)
        if not row or row["live_only_line_n"] < 1:
            pinned_ok = False
    if not pinned_ok:
        return _fail("catalog-pinned live-larger names lack live-only lines")
    print(
        "either_n="
        + str(snap["either_direction_destroy_n"])
        + " paired="
        + str(snap["paired_files"])
        + " eol="
        + eol["result"]
        + " host_live="
        + str(A.host_live_present())
    )
    print("SUCCESS:ADV-0017-probe1 three-way LF classification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
