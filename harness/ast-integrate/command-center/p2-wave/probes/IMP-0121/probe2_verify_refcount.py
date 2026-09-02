#!/usr/bin/env python3
"""Named probe 2: verify-on-read, refuse referenced delete, crash-survivable refcount.

Independent of probe1's tempfile. Three claims, each with a both-states check:
  * a mutated object is detected on read (bad) and an intact object is served (good)
  * delete of a still-referenced blob is refused (bad) and delete after release
    succeeds (good)
  * after dropping the live BlobStore, refcount is re-derived from index.json
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
    CorruptedBlobError,
    ReferencedBlobError,
    digest_bytes,
    list_object_files,
    load_index_file,
    refcount_from_index,
)

PAYLOAD = b"IMP-0121-probe2-verify-me\n"
MUTATED = b"IMP-0121-probe2-MUTATED\n"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0121-p2-") as tmp:
        root = Path(tmp)

        # --- intact read (good state) ---
        store = BlobStore(root)
        digest = store.put(PAYLOAD, "install:pkg@1.0")
        served = store.get(digest)
        if served != PAYLOAD or digest_bytes(served) != digest:
            print("FAILED:IMP-0121-probe2 intact read did not round-trip")
            return 1

        # --- mutated read (bad state): must raise, must not return MUTATED ---
        files = list_object_files(root)
        if len(files) != 1:
            print(f"FAILED:IMP-0121-probe2 unexpected object count {len(files)}")
            return 1
        files[0].write_bytes(MUTATED)
        detected = False
        served_mutated = False
        actual = None
        try:
            leaked = store.get(digest)
            served_mutated = leaked == MUTATED
        except CorruptedBlobError as err:
            detected = True
            actual = err.actual
        if not detected or served_mutated or actual != digest_bytes(MUTATED):
            print(
                json.dumps(
                    {
                        "detected": detected,
                        "served_mutated": served_mutated,
                        "actual": actual,
                    }
                )
            )
            print("FAILED:IMP-0121-probe2 corruption not detected on read")
            return 1
        # Restore intact bytes so later checks use a real object.
        files[0].write_bytes(PAYLOAD)
        if store.get(digest) != PAYLOAD:
            print("FAILED:IMP-0121-probe2 restored object not served")
            return 1

        # --- referenced delete refused (bad) ---
        store.put(PAYLOAD, "install:pkg@2.0")
        refused = False
        try:
            store.delete(digest)
        except ReferencedBlobError as err:
            refused = err.refcount == 2
        still_there = bool(list_object_files(root))
        if not refused or not still_there:
            print("FAILED:IMP-0121-probe2 referenced delete was not refused")
            return 1

        # --- crash survival: drop instance, re-derive from index.json ---
        del store
        index = load_index_file(root)
        derived = refcount_from_index(index, digest)
        if derived != 2:
            print(f"FAILED:IMP-0121-probe2 crash-derived refcount={derived} want=2")
            return 1
        reopened = BlobStore(root)
        if reopened.refcount(digest) != 2:
            print("FAILED:IMP-0121-probe2 reopened store lost refcount")
            return 1
        try:
            reopened.delete(digest)
            print("FAILED:IMP-0121-probe2 reopened store allowed referenced delete")
            return 1
        except ReferencedBlobError:
            pass

        # --- unreferenced delete succeeds (good state of the negative control) ---
        reopened.release(digest, "install:pkg@1.0")
        reopened.release(digest, "install:pkg@2.0")
        if reopened.refcount(digest) != 0:
            print("FAILED:IMP-0121-probe2 release did not reach refcount 0")
            return 1
        reopened.delete(digest)
        if list_object_files(root):
            print("FAILED:IMP-0121-probe2 unreferenced delete left files")
            return 1

        result = {
            "probe": "probe2-verify-refcount",
            "unit_id": "IMP-0121",
            "intact_read": True,
            "corruption_detected": True,
            "mutated_not_served": True,
            "recomputed_digest": actual,
            "referenced_delete_refused": True,
            "refcount_from_index_after_drop": derived,
            "unreferenced_delete_removed_object": True,
            "pass": True,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        print(
            f"corruption_detected=True referenced_delete_refused=True "
            f"index_refcount_after_drop={derived}"
        )
        print("SUCCESS:IMP-0121-probe2 verify-on-read and crash-survivable refcount")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
