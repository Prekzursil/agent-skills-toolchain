#!/usr/bin/env python3
"""Probe 1 / signal (a): destination listing with exact casing after case-only rename.

Live deploy/sync of a tracked case-only rename onto an NTFS-like destination.
PASS: dest holds exactly one of the pair, spelled with the new casing, and the
content hash matches the source blob. The sibling file is not dropped.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from sync import NEW_REL, OLD_REL, SIBLING, BLOB_A, run_case_only, sha256_bytes  # noqa: E402

OUT = HERE / "probe1-case-only-rename.raw.json"


def main() -> int:
    row = run_case_only()
    check = row["check"]
    listing = check["listing"]
    payload = {
        "probe": "probe1-case-only-rename",
        "unit_id": "TST-0196",
        "old_rel": OLD_REL,
        "new_rel": NEW_REL,
        "source_sha256": sha256_bytes(BLOB_A),
        "dest_listing_exact": listing,
        "dest_sha256": check["dest_sha256"],
        "pair": check["pair"],
        "exact_one_new_casing": check["exact_one_new_casing"],
        "hash_matches_source": check["hash_matches_source"],
        "sibling_present": check["sibling_present"],
        "old_casing_absent": OLD_REL not in listing,
        "new_casing_present": NEW_REL in listing,
        "file_count": len(listing),
        "ops": row["sync"]["ops"],
        "pass": bool(row["ok"]),
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    print(
        f"listing={listing} dest_sha={check['dest_sha256']} "
        f"src_sha={payload['source_sha256']} sibling={SIBLING in listing}"
    )
    if not row["ok"]:
        print("FAILED:TST-0196-probe1 case-only rename did not land new casing")
        return 1
    print("SUCCESS:TST-0196-probe1 destination listing with exact new casing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
