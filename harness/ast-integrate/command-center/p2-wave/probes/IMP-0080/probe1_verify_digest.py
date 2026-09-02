#!/usr/bin/env python3
"""Named probe 1 (IMP-0080): stored provenance verifies against the artifact digest.

Independent of probe 2: this path hashes the artifact bytes itself and compares
them to the stored record. It does not run git.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "tools" / "marketplace"))
sys.path.insert(0, str(HERE))

import provenance_store as ps  # noqa: E402
from scenario import PACKAGE, VERSION, planted  # noqa: E402


def main() -> int:
    with planted() as world:
        return _run(world)


def _run(world) -> int:
    independent = hashlib.sha256(world.artifact).hexdigest()
    if independent != world.digest:
        print("FAILED:IMP-0080-probe1 helper digest drifted from hashlib")
        return 1
    verified = world.store.verify_against_artifact(PACKAGE, VERSION, world.artifact)
    if not verified.get("verified"):
        print("FAILED:IMP-0080-probe1 store verify returned false")
        return 1
    if verified["artifact_digest_sha256"] != independent:
        print("FAILED:IMP-0080-probe1 stored digest != independent hashlib")
        return 1
    payload = ps.interpret_query(world.store.query(PACKAGE, VERSION))
    if payload.status != "PRESENT" or payload.record is None:
        print(f"FAILED:IMP-0080-probe1 query status={payload.status}")
        return 1
    if payload.record["artifact_digest_sha256"] != independent:
        print("FAILED:IMP-0080-probe1 query record digest mismatch")
        return 1
    try:
        world.store.verify_against_artifact(PACKAGE, VERSION, world.artifact + b"flip")
        print("FAILED:IMP-0080-probe1 tamper did not fail")
        return 1
    except ps.DigestMismatchError:
        pass
    out = {
        "probe": "probe1-verify-digest",
        "unit_id": "IMP-0080",
        "verified": True,
        "independent_sha256": independent,
        "stored_sha256": payload.record["artifact_digest_sha256"],
        "package": PACKAGE,
        "version": VERSION,
        "tamper_rejected": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:IMP-0080-probe1 stored provenance verifies against artifact digest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
