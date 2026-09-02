#!/usr/bin/env python3
"""Probe 1: clean install into a throwaway HOME matches the projection.

Two independent signals:
  (1) set equality of live paths vs projection.live paths
  (2) per-file sha256 of live bytes vs payload source bytes (not the stored
      projection digest — recomputed from the payload files themselves)
Plus idempotency: a second install mutates zero files (mtime+hash census).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.install import (  # noqa: E402
    install_plugin,
    live_file_census,
    mtime_hash_census,
    plugin_root,
    predicted_live_paths,
    sha256_file,
)
from plugin.tests.harness import (  # noqa: E402
    expected_census,
    projection_for,
    v1_files,
    write_tree,
)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0023-p1-") as tmp:
        tmp_path = Path(tmp)
        home = tmp_path / "home"
        payload = tmp_path / "payload"
        files = v1_files()
        write_tree(payload, files)
        projection = projection_for(payload)
        predicted = predicted_live_paths(projection)
        payload_hashes = expected_census(files)
        # Signal 2: recompute from payload files with hashlib, independently
        # of expected_census() encoding — walk the directory.
        walked: dict[str, str] = {}
        for entry in projection["entries"]:
            walked[entry["source"]] = sha256_file(payload / entry["source"])

        result = install_plugin(home=home, payload=payload, projection=projection)
        if result.status != "installed" or not result.mutated:
            print(f"FAILED:IMP-0023-probe1 first install status={result.status}")
            return 1
        root = plugin_root(home, projection["plugin_id"])
        live = live_file_census(root)
        if set(live) != predicted:
            print(
                json.dumps(
                    {
                        "error": "live-set-mismatch",
                        "live": sorted(live),
                        "predicted": sorted(predicted),
                    },
                    sort_keys=True,
                )
            )
            return 1
        extra = set(live) - predicted
        missing = predicted - set(live)
        if extra or missing:
            print(f"FAILED:IMP-0023-probe1 extra={sorted(extra)} missing={sorted(missing)}")
            return 1
        for rel, digest in live.items():
            if digest != payload_hashes[rel]:
                print(f"FAILED:IMP-0023-probe1 hash mismatch vs encoded body {rel}")
                return 1
            if digest != walked[rel]:
                print(f"FAILED:IMP-0023-probe1 hash mismatch vs walked payload {rel}")
                return 1
            if digest != next(e["sha256"] for e in projection["entries"] if e["live"] == rel):
                print(f"FAILED:IMP-0023-probe1 hash mismatch vs projection {rel}")
                return 1

        census_before = mtime_hash_census(root)
        second = install_plugin(home=home, payload=payload, projection=projection)
        if second.status != "already-current" or second.mutated:
            print(f"FAILED:IMP-0023-probe1 second install not a no-op: {second.to_dict()}")
            return 1
        census_after = mtime_hash_census(root)
        if census_after != census_before:
            print("FAILED:IMP-0023-probe1 second install mutated mtime/hash census")
            print(json.dumps({"before": census_before, "after": census_after}, sort_keys=True))
            return 1

        summary = {
            "probe": "probe1-clean-install",
            "unit_id": "IMP-0023",
            "live_paths": sorted(live),
            "predicted_paths": sorted(predicted),
            "set_equal": True,
            "payload_hashes_match": True,
            "walked_payload_hashes_match": True,
            "file_count": len(live),
            "second_install_status": second.status,
            "mtime_hash_census_unchanged": True,
            "pass": True,
        }
        print(json.dumps(summary, sort_keys=True))
        print(
            f"set_equal=True files={len(live)} idempotent=True "
            f"census_entries={len(census_after)}"
        )
        print("SUCCESS:IMP-0023-probe1 clean install matches projection")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
