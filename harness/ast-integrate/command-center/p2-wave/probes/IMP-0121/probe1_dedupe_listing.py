#!/usr/bin/env python3
"""Named probe 1: storing the same blob twice yields one on-disk object.

Signal 1 is a directory listing of objects/ (not a store-internal counter).
Signal 2 is the persisted index.json refcount for the same digest, loaded
with json.loads so it is independent of BlobStore.refcount memory.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

from blob_store import (  # noqa: E402
    BlobStore,
    digest_bytes,
    list_object_files,
    refcount_from_index,
)

PAYLOAD = b"IMP-0121-probe1-identical-blob\n"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0121-p1-") as tmp:
        root = Path(tmp)
        store = BlobStore(root)
        d1 = store.put(PAYLOAD, "version:1.0.0")
        d2 = store.put(PAYLOAD, "collection:core")
        files = list_object_files(root)
        listing = [p.relative_to(root).as_posix() for p in files]
        index_raw = (root / "index.json").read_text(encoding="utf-8")
        index = json.loads(index_raw)
        derived = refcount_from_index(index, d1)
        expected = digest_bytes(PAYLOAD)

        result = {
            "probe": "probe1-dedupe-listing",
            "unit_id": "IMP-0121",
            "digest": d1,
            "put_twice_same_digest": d1 == d2 == expected,
            "directory_listing": listing,
            "object_file_count": len(files),
            "index_refcount": derived,
            "index_refs": sorted((index.get("objects") or {}).get(d1, {}).get("refs") or {}),
            "pass": False,
        }
        if d1 != d2 or d1 != expected:
            print(json.dumps(result, indent=2))
            print("FAILED:IMP-0121-probe1 digest mismatch")
            return 1
        if len(files) != 1:
            print(json.dumps(result, indent=2))
            print(f"FAILED:IMP-0121-probe1 object_file_count={len(files)} want=1")
            return 1
        if derived != 2:
            print(json.dumps(result, indent=2))
            print(f"FAILED:IMP-0121-probe1 index_refcount={derived} want=2")
            return 1
        other = store.put(b"IMP-0121-probe1-other\n", "version:other")
        files_after = list_object_files(root)
        if other == d1 or len(files_after) != 2:
            result["other_digest"] = other
            result["object_file_count_after_distinct"] = len(files_after)
            print(json.dumps(result, indent=2))
            print("FAILED:IMP-0121-probe1 distinct blob did not add a second object")
            return 1
        result["object_file_count_after_distinct"] = 2
        result["other_digest"] = other
        result["pass"] = True
        print(json.dumps(result, indent=2, sort_keys=True))
        print(
            f"listing={listing} files={len(files)} refs={result['index_refs']} "
            f"refcount={derived}"
        )
        print("SUCCESS:IMP-0121-probe1 one on-disk object for two puts of identical bytes")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
