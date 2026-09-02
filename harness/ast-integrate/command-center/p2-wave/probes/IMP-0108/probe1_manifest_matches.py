#!/usr/bin/env python3
"""IMP-0108 probe 1: manifest entry count equals extracted blob count.

Two listings, neither taken from the exporter's return value:
  1. zipfile.ZipFile.namelist() members under blobs/
  2. pathlib walk of the extracted tree under blobs/

Each blob's sha256 is recomputed and must match the manifest digest.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.digest import sha256_hex  # noqa: E402
from marketplace.offline_export import (  # noqa: E402
    extract_offline_bundle,
    extracted_blob_paths,
    export_offline_bundle,
    zip_blob_members,
)
from marketplace.testkit import diamond_registry  # noqa: E402


def main() -> int:
    fx = diamond_registry()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dest = tmp / "bundle.zip"
        man = export_offline_bundle(
            index=fx.index,
            blobs=fx.blobs,
            private_keys=fx.private_keys,
            package_key_id=fx.package_key_id,
            selection=[("app", "1.0.0")],
            dest=dest,
            created_at="2026-08-24T18:00:00+00:00",
            signed_at="2026-08-24T18:00:00+00:00",
        )
        zip_blobs = zip_blob_members(dest)
        extract = tmp / "out"
        extract_offline_bundle(dest, extract)
        disk_blobs = extracted_blob_paths(extract)
        claimed = sorted(e["blob_path"] for e in man["entries"])
        n_man = len(man["entries"])
        n_zip = len(zip_blobs)
        n_disk = len(disk_blobs)
        digest_ok = True
        for entry in man["entries"]:
            live = sha256_hex((extract / entry["blob_path"]).read_bytes())
            if live != entry["digest"]:
                digest_ok = False
        payload = {
            "probe": "probe1-manifest-matches-contents",
            "unit_id": "IMP-0108",
            "manifest_entries": n_man,
            "zip_blob_members": n_zip,
            "extracted_blob_files": n_disk,
            "claimed_paths": claimed,
            "zip_paths": zip_blobs,
            "disk_paths": disk_blobs,
            "counts_equal": n_man == n_zip == n_disk,
            "paths_equal": claimed == zip_blobs == disk_blobs,
            "digests_match": digest_ok,
            "pass": n_man == n_zip == n_disk
            and claimed == zip_blobs == disk_blobs
            and digest_ok
            and n_man == 4,
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            f"manifest={n_man} zip_blobs={n_zip} disk_blobs={n_disk} "
            f"digests_match={digest_ok}"
        )
        if not payload["pass"]:
            print("FAILED:IMP-0108-probe1 manifest/blob count mismatch")
            return 1
        print("SUCCESS:IMP-0108-probe1 manifest entry count equals extracted blob count")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
