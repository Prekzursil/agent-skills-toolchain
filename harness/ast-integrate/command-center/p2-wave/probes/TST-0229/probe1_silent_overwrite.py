#!/usr/bin/env python3
"""Probe 1: silent overwrite is refused (detector control).

Production store must refuse a second write without a re-baseline record and
leave the store digest unchanged. NaiveMutableStore must accept the same
overwrite (otherwise this detector is dead in both states).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.bench.baseline_store import (  # noqa: E402
    BaselineStore,
    BlobIntegrityError,
    NaiveMutableStore,
    SilentOverwriteRefused,
    sha256_bytes,
)

UID = "TST-0229"
CASE = "bench.case.alpha"
V1 = b"TST-0229-baseline-v1-nonzero"
V2 = b"TST-0229-silent-overwrite-v2"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0229-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0229-p1-") as tmp:
        tmp_path = Path(tmp)
        prod = BaselineStore(tmp_path / "prod")
        naive = NaiveMutableStore(tmp_path / "naive")

        d1 = prod.write(CASE, V1)
        if d1 != sha256_bytes(V1):
            return fail("initial digest is not content-addressed")
        h_before = prod.store_digest()

        refused = False
        silent_exc = ""
        try:
            prod.write(CASE, V2)
        except SilentOverwriteRefused as exc:
            refused = True
            silent_exc = type(exc).__name__
        h_after_refuse = prod.store_digest()
        still_v1 = prod.get(CASE) == V1
        pointer_unchanged = prod.digest_of(CASE) == d1

        naive.write(CASE, V1)
        nh_before = naive.store_digest()
        naive.write(CASE, V2)
        nh_after = naive.store_digest()
        naive_now_v2 = naive.get(CASE) == V2
        naive_digest_moved = nh_before != nh_after

        # In-place blob rewrite must not be served as the original digest.
        corrupt = BaselineStore(tmp_path / "corrupt")
        cd = corrupt.write(CASE, V1)
        (corrupt.blobs / cd).write_bytes(V2)
        integrity_caught = False
        try:
            corrupt.get(CASE)
        except BlobIntegrityError:
            integrity_caught = True

        payload = {
            "probe": "probe1-silent-overwrite",
            "unit_id": UID,
            "pass": False,
            "production": {
                "initial_digest": d1,
                "silent_overwrite_refused": refused,
                "exception": silent_exc,
                "store_digest_before": h_before,
                "store_digest_after": h_after_refuse,
                "store_digest_unchanged": h_before == h_after_refuse,
                "payload_unchanged": still_v1,
                "pointer_unchanged": pointer_unchanged,
            },
            "naive_mutant": {
                "silent_overwrite_accepted": naive_now_v2,
                "store_digest_before": nh_before,
                "store_digest_after": nh_after,
                "store_digest_changed": naive_digest_moved,
            },
            "blob_integrity": {
                "inplace_rewrite_caught": integrity_caught,
            },
            "detector_discriminates": refused and naive_now_v2 and naive_digest_moved,
        }
        payload["pass"] = bool(
            refused
            and still_v1
            and pointer_unchanged
            and h_before == h_after_refuse
            and naive_now_v2
            and naive_digest_moved
            and integrity_caught
        )
        print(json.dumps(payload, sort_keys=True))

        if not refused:
            return fail("production store accepted a silent overwrite")
        if h_before != h_after_refuse:
            return fail("production store digest moved after refused overwrite")
        if not still_v1 or not pointer_unchanged:
            return fail("production baseline bytes or pointer changed")
        if not naive_now_v2 or not naive_digest_moved:
            return fail("naive mutant did not silently overwrite (dead detector)")
        if not integrity_caught:
            return fail("corrupted blob was served under its digest")
        print(
            "SUCCESS:TST-0229-probe1 silent overwrite refused; "
            "naive mutant overwrites; store digest unchanged"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
