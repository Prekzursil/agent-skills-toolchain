#!/usr/bin/env python3
"""Probe 1: both-states control for the shard-set reducer.

All 4 shards present -> COMPLETE. 3 of 4 present -> INCOMPLETE with the
missing id enumerated. An independent directory listing diffed against the
shard manifest must name the same missing id as the reducer's status object.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools" / "command-center"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import shard_reducer as SR  # noqa: E402


def independent_listing_diff(set_root: Path, manifest_path: Path) -> dict:
    """Signal (b): listdir the set root and diff filenames against the manifest.

    Does not call reduce_shard_set. Reads the manifest from disk itself.
    """
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    expected_by_name = {
        Path(str(s["path"]).replace("\\", "/")).name: s["id"]
        for s in manifest["shards"]
    }
    if set_root.is_dir():
        on_disk = {p.name for p in set_root.iterdir() if p.is_file()}
    else:
        on_disk = set()
    missing_names = set(expected_by_name) - on_disk
    extra_names = on_disk - set(expected_by_name)
    missing_ids = []
    for shard in manifest["shards"]:
        name = Path(str(shard["path"]).replace("\\", "/")).name
        if name in missing_names:
            missing_ids.append(shard["id"])
    return {
        "on_disk": sorted(on_disk),
        "missing_ids": missing_ids,
        "extra_names": sorted(extra_names),
    }


def _ok_complete(status: dict, listing: dict) -> bool:
    return (
        status.get("status") == SR.COMPLETE
        and status.get("missing_ids") == []
        and listing.get("missing_ids") == []
        and status.get("computed_over_present") is False
        and status.get("score") is None
        and set(status.get("present_ids") or []) == set(F.SHARD_IDS)
    )


def _ok_incomplete(status: dict, listing: dict) -> bool:
    missing = status.get("missing_ids")
    return (
        status.get("status") == SR.INCOMPLETE
        and isinstance(missing, list)
        and F.MISSING_ID in missing
        and listing.get("missing_ids") == missing
        and status.get("computed_over_present") is False
        and status.get("score") is None
        and F.MISSING_ID not in (status.get("present_ids") or [])
    )


def main() -> int:
    F.materialize_ondisk()
    with tempfile.TemporaryDirectory(prefix="tst-0148-p1-") as tmp:
        tmp_path = Path(tmp)
        complete_root, complete_man = F.populate_tree(tmp_path / "all-four")
        incomplete_root, incomplete_man = F.populate_tree(
            tmp_path / "three-of-four", omit=F.MISSING_ID
        )

        complete_status = SR.reduce_shard_set(complete_root, complete_man)
        complete_listing = independent_listing_diff(complete_root, complete_man)
        incomplete_status = SR.reduce_shard_set(incomplete_root, incomplete_man)
        incomplete_listing = independent_listing_diff(incomplete_root, incomplete_man)

        # Also run against the on-disk fixture trees (second live read).
        disk_complete = SR.reduce_shard_set(F.FIX / "complete", F.FIX / F.MANIFEST_NAME)
        disk_incomplete = SR.reduce_shard_set(
            F.FIX / "incomplete", F.FIX / F.MANIFEST_NAME
        )
        disk_listing = independent_listing_diff(
            F.FIX / "incomplete", F.FIX / F.MANIFEST_NAME
        )

        ok = (
            _ok_complete(complete_status, complete_listing)
            and _ok_incomplete(incomplete_status, incomplete_listing)
            and _ok_complete(disk_complete, {"missing_ids": []})
            and _ok_incomplete(disk_incomplete, disk_listing)
            and incomplete_listing["missing_ids"] == [F.MISSING_ID]
            and disk_listing["missing_ids"] == [F.MISSING_ID]
        )
        report = {
            "probe": "probe1-both-states",
            "unit_id": "TST-0148",
            "pass": ok,
            "complete": {
                "reducer": complete_status,
                "listing_diff": complete_listing,
            },
            "incomplete_3_of_4": {
                "reducer": incomplete_status,
                "listing_diff": incomplete_listing,
                "missing_id_named": F.MISSING_ID in (incomplete_status.get("missing_ids") or []),
                "listing_agrees": incomplete_listing.get("missing_ids")
                == incomplete_status.get("missing_ids"),
            },
            "ondisk_incomplete_listing": disk_listing,
            "signals": [
                "reducer-status-object",
                "independent-directory-listing-diffed-against-shard-manifest",
            ],
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        if not ok:
            print("FAILED:TST-0148-probe1 both-states or listing mismatch")
            return 1
        print(
            "SUCCESS:TST-0148-probe1 all-4 COMPLETE; 3-of-4 INCOMPLETE names "
            + F.MISSING_ID
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
