#!/usr/bin/env python3
"""Probe 2: byte-identical lockfile, missing-entry refuse, stale warn, reviewer mutation.

The reviewer independently mutates a blob (XOR first byte, not probe-1's
suffix) and confirms the refusal happens before any destination write.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3] / "tools"))

from marketplace.lockfile import (  # noqa: E402
    CURRENT_RESOLVER_VERSION,
    DigestMismatch,
    MissingLockfileEntry,
    filesystem_census,
    generate_lockfile,
    install_verified,
    load_lockfile,
)
from scenario import blob_map, sample_packages  # noqa: E402


def reviewer_mutate(blob: bytes) -> bytes:
    if not blob:
        return b"\xff"
    return bytes((blob[0] ^ 0xFF,)) + blob[1:]


def main() -> int:
    packages = sample_packages()
    blobs = blob_map(packages)
    lock_a = generate_lockfile(packages)
    lock_b = generate_lockfile(list(reversed(packages)))
    identical = lock_a == lock_b
    doc = load_lockfile(lock_a)
    names = [(p["name"], p["version"]) for p in doc["packages"]]
    sorted_ok = names == sorted(names)

    pkg = packages[1]
    reviewer_blob = reviewer_mutate(pkg.blob)
    fetch_calls = {"n": 0}

    def fetch_reviewer(url: str) -> bytes:
        fetch_calls["n"] += 1
        if url != pkg.source_url:
            return blobs[url]
        return reviewer_blob

    reviewer_refused = False
    reviewer_err = ""
    reviewer_unchanged = False
    missing_refused = False
    stale_warned = False

    with tempfile.TemporaryDirectory(prefix="imp0084-p2-") as tmp:
        dest = Path(tmp) / "dest"
        dest.mkdir()
        before = filesystem_census(dest)
        try:
            install_verified(lock_a, name=pkg.name, dest=dest, fetch=fetch_reviewer)
        except DigestMismatch as err:
            reviewer_refused = True
            reviewer_err = str(err)
            reviewer_unchanged = (
                err.dest_unchanged() and filesystem_census(dest) == before
            )

        missing_fetch = {"n": 0}

        def fetch_should_not_run(url: str) -> bytes:
            missing_fetch["n"] += 1
            return b"should-not-fetch"

        try:
            install_verified(
                lock_a, name="absent-pkg", dest=dest, fetch=fetch_should_not_run
            )
        except MissingLockfileEntry as err:
            missing_refused = err.fetch_count == 0 and missing_fetch["n"] == 0

        stale_bytes = generate_lockfile(
            packages, resolver_version="marketplace-resolver/0.9.0"
        )
        stale = install_verified(
            stale_bytes,
            name=packages[0].name,
            dest=dest,
            fetch=lambda u: blobs[u],
            current_resolver_version=CURRENT_RESOLVER_VERSION,
        )
        stale_warned = any("stale resolver version" in w for w in stale.warnings)

    ok = (
        identical
        and sorted_ok
        and reviewer_refused
        and reviewer_unchanged
        and "digest mismatch" in reviewer_err.lower()
        and fetch_calls["n"] == 1
        and missing_refused
        and stale_warned
    )
    print(
        json.dumps(
            {
                "lockfile_byte_identical": identical,
                "missing_entry_refused_before_fetch": missing_refused,
                "packages_sorted": sorted_ok,
                "pass": ok,
                "probe": "probe2-determinism-reviewer",
                "reviewer_digest_mismatch_named": "digest mismatch"
                in reviewer_err.lower(),
                "reviewer_dest_unchanged": reviewer_unchanged,
                "reviewer_fetch_count": fetch_calls["n"],
                "reviewer_mutation": "xor-first-byte",
                "reviewer_refused": reviewer_refused,
                "stale_resolver_warned": stale_warned,
                "unit_id": "IMP-0084",
            },
            sort_keys=True,
        )
    )
    if not ok:
        print("FAILED:IMP-0084-probe2 determinism/reviewer/missing/stale")
        return 1
    print(
        "SUCCESS:IMP-0084-probe2 lockfile byte-identical; reviewer mutation "
        "refused before write; missing entry refuses; stale resolver warns"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
