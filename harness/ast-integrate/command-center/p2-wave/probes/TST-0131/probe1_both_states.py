#!/usr/bin/env python3
"""Probe 1: both-states control for mid-stream truncation.

Known-good: a complete download of the same fixture installs cleanly.
Known-bad: reset after N of M bytes emits digest-mismatch and an independent
cache listing shows zero entries for the package id.

Negative control: a naive write-into-cache leaves a truncated remnant that
the independent listing CAN see — proving the listing is not stuck at zero.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

from harness import (  # noqa: E402
    PACKAGE_ID,
    TRUNCATE_AFTER,
    fixture_blob,
    full_url,
    listing_names_package,
    quarantine_is_outside_cache,
    serve_blob,
    truncate_url,
)
from package_download import (  # noqa: E402
    REASON_DIGEST_MISMATCH,
    independent_cache_listing,
    download_package,
    naive_write_partial_into_cache,
    sha256_hex,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0131-probe1 {msg}")
    return 1


def main() -> int:
    blob = fixture_blob()
    expected = sha256_hex(blob)
    n = TRUNCATE_AFTER
    m = len(blob)
    if not (0 < n < m):
        return fail(f"truncate N={n} not strictly inside M={m}")

    with tempfile.TemporaryDirectory(prefix="tst0131-p1-") as tmp:
        tmp_path = Path(tmp)
        cache = tmp_path / "cache"
        quarantine = tmp_path / "quarantine"
        install = tmp_path / "install"
        naive_cache = tmp_path / "naive-cache"
        with serve_blob(blob) as base:
            good = download_package(
                full_url(base),
                PACKAGE_ID,
                expected,
                cache,
                quarantine,
                install_root=install,
            )
            if not good.ok or good.classification != "ok":
                return fail(f"complete download did not install: {good.to_dict()}")
            installed = Path(good.installed_path or "")
            if not installed.is_file() or sha256_hex(installed.read_bytes()) != expected:
                return fail("installed payload digest != fixture digest")
            good_hits = independent_cache_listing(cache, PACKAGE_ID)
            if not listing_names_package(good_hits, PACKAGE_ID):
                return fail(f"good-state cache listing missed package: {good_hits}")

            cache_bad = tmp_path / "cache-trunc"
            q_bad = tmp_path / "quarantine-trunc"
            bad = download_package(
                truncate_url(base, n),
                PACKAGE_ID,
                expected,
                cache_bad,
                q_bad,
            )
            if bad.ok:
                return fail("truncated download was reported ok")
            if bad.classification != REASON_DIGEST_MISMATCH:
                return fail(
                    f"expected digest-mismatch, got {bad.classification}: {bad.message}"
                )
            if "digest-mismatch" not in bad.message:
                return fail(f"downloader message omitted digest-mismatch: {bad.message}")
            if bad.received_bytes != n:
                return fail(
                    f"received_bytes={bad.received_bytes} expected N={n} of M={m}"
                )
            if bad.claimed_bytes != m:
                return fail(f"claimed_bytes={bad.claimed_bytes} expected M={m}")
            if bad.received_digest == expected:
                return fail("truncated body hashed to the full-package digest")
            if not bad.quarantine_path:
                return fail("partial was not quarantined")
            qpath = Path(bad.quarantine_path)
            if not qpath.is_file():
                return fail(f"quarantine path missing: {qpath}")
            if not quarantine_is_outside_cache(qpath, cache_bad):
                return fail("quarantine path lives inside the cache")
            if qpath.read_bytes() != blob[:n]:
                return fail("quarantined bytes != truncated remnant")

            hits = independent_cache_listing(cache_bad, PACKAGE_ID)
            if listing_names_package(hits, PACKAGE_ID) or hits:
                return fail(f"cache listing not empty for package id: {hits}")
            if (cache_bad / PACKAGE_ID).exists():
                return fail("cache still has a package-id directory")

            naive_path = naive_write_partial_into_cache(
                truncate_url(base, n), PACKAGE_ID, naive_cache
            )
            naive_hits = independent_cache_listing(naive_cache, PACKAGE_ID)
            if not listing_names_package(naive_hits, PACKAGE_ID):
                return fail(
                    f"detector-control: naive remnant not visible in listing {naive_hits}"
                )
            if sha256_hex(naive_path.read_bytes()) == expected:
                return fail("naive remnant unexpectedly matched full digest")
            if naive_path.stat().st_size != n:
                return fail(f"naive remnant size {naive_path.stat().st_size} != N={n}")

            truncated_digest = bad.received_digest

    out = {
        "probe": "probe1-both-states",
        "unit_id": "TST-0131",
        "pass": True,
        "package_id": PACKAGE_ID,
        "n": n,
        "m": m,
        "expected_digest": expected,
        "truncated_digest": truncated_digest,
        "good_install_digest_ok": True,
        "digest_mismatch_emitted": True,
        "independent_cache_listing_empty": True,
        "quarantine_outside_cache": True,
        "naive_control_listing_sees_remnant": True,
        "classification": REASON_DIGEST_MISMATCH,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"good_install=True digest-mismatch=True cache_hits_after_trunc=[] "
        f"N={n} M={m} naive_control_fired=True"
    )
    print("SUCCESS:TST-0131-probe1 both-states: complete installs; truncation quarantined")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
