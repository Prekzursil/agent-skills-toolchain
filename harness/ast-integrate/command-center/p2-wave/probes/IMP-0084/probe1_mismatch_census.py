#!/usr/bin/env python3
"""Probe 1: mutated blob refused; destination census unchanged.

Catalog signal (1): named digest mismatch. Signal (2) starts here: nothing
is written under dest. Negative control: unmutated blob installs in the
same process.
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
    DigestMismatch,
    filesystem_census,
    generate_lockfile,
    install_verified,
    sha256_hex,
)
from scenario import blob_map, sample_packages  # noqa: E402


def main() -> int:
    packages = sample_packages()
    blobs = blob_map(packages)
    lock_bytes = generate_lockfile(packages)
    pkg = packages[0]
    mutated = pkg.blob + b"\x00upstream-mutated"
    calls = {"n": 0}
    err_text = ""
    refused = False
    mismatch_named = False
    dest_unchanged = False
    expected_ok = False
    actual_ok = False
    wrote_on_mismatch = True

    def fetch_mutated(url: str) -> bytes:
        calls["n"] += 1
        if url != pkg.source_url:
            raise AssertionError(f"unexpected fetch {url}")
        return mutated

    def fetch_honest(url: str) -> bytes:
        return blobs[url]

    with tempfile.TemporaryDirectory(prefix="imp0084-p1-") as tmp:
        dest = Path(tmp) / "dest"
        dest.mkdir()
        marker = dest / "already-there.txt"
        marker.write_text("must-survive-mismatch\n", encoding="utf-8")
        before = filesystem_census(dest)
        try:
            install_verified(lock_bytes, name=pkg.name, dest=dest, fetch=fetch_mutated)
        except DigestMismatch as err:
            refused = True
            err_text = str(err)
            mismatch_named = "digest mismatch" in err_text.lower()
            dest_unchanged = err.dest_unchanged() and filesystem_census(dest) == before
            expected_ok = err.expected_hex == sha256_hex(pkg.blob)
            actual_ok = err.actual_hex == sha256_hex(mutated)
        wrote_on_mismatch = (dest / pkg.name / pkg.version / "payload").exists()
        marker_ok = marker.read_text(encoding="utf-8") == "must-survive-mismatch\n"
        honest = install_verified(
            lock_bytes, name=pkg.name, dest=dest, fetch=fetch_honest
        )
        payload = dest / pkg.name / pkg.version / "payload"
        negative_installed = (
            payload.is_file()
            and payload.read_bytes() == pkg.blob
            and honest.digest_hex == sha256_hex(pkg.blob)
        )

    ok = (
        refused
        and mismatch_named
        and dest_unchanged
        and not wrote_on_mismatch
        and calls["n"] == 1
        and expected_ok
        and actual_ok
        and negative_installed
        and marker_ok
    )
    print(
        json.dumps(
            {
                "actual_digest": sha256_hex(mutated),
                "dest_unchanged": dest_unchanged,
                "error": err_text[:400],
                "expected_digest": sha256_hex(pkg.blob),
                "fetch_count_on_mismatch": calls["n"],
                "marker_survived": marker_ok,
                "mismatch_named": mismatch_named,
                "negative_control_unmutated_installed": negative_installed,
                "pass": ok,
                "probe": "probe1-mismatch-census",
                "refused": refused,
                "unit_id": "IMP-0084",
                "wrote_on_mismatch": wrote_on_mismatch,
            },
            sort_keys=True,
        )
    )
    if not ok:
        print("FAILED:IMP-0084-probe1 mismatch/census/negative-control")
        return 1
    print(
        "SUCCESS:IMP-0084-probe1 mutated blob refused with named digest "
        "mismatch; census unchanged; unmutated blob installed in same run"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
