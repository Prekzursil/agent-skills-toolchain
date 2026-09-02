#!/usr/bin/env python3
"""Probe 2: follow-on install after truncation is not poisoned.

After a reset-after-N download (digest-mismatch, empty cache), a second
install of the same fixture succeeds and the installed bytes match the
full-package digest — not the quarantined remnant.

Independent of probe 1: new temp roots, new server, new process.
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
    CACHE_PAYLOAD_NAME,
    REASON_DIGEST_MISMATCH,
    download_package,
    independent_cache_listing,
    install_from_cache,
    naive_write_partial_into_cache,
    sha256_hex,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0131-probe2 {msg}")
    return 1


def main() -> int:
    blob = fixture_blob()
    expected = sha256_hex(blob)
    n = TRUNCATE_AFTER
    truncated_digest = sha256_hex(blob[:n])
    got = ""

    with tempfile.TemporaryDirectory(prefix="tst0131-p2-") as tmp:
        tmp_path = Path(tmp)
        cache = tmp_path / "cache"
        quarantine = tmp_path / "quarantine"
        install = tmp_path / "install"
        naive_cache = tmp_path / "naive-cache"
        naive_install = tmp_path / "naive-install"
        with serve_blob(blob) as base:
            first = download_package(
                truncate_url(base, n),
                PACKAGE_ID,
                expected,
                cache,
                quarantine,
            )
            if first.ok or first.classification != REASON_DIGEST_MISMATCH:
                return fail(
                    f"first (truncated) did not digest-mismatch: {first.to_dict()}"
                )
            hits_after_trunc = independent_cache_listing(cache, PACKAGE_ID)
            if hits_after_trunc:
                return fail(f"cache not empty after truncation: {hits_after_trunc}")
            qpath = Path(first.quarantine_path or "")
            if not qpath.is_file() or not quarantine_is_outside_cache(qpath, cache):
                return fail("partial not quarantined outside cache")
            remnant_digest = sha256_hex(qpath.read_bytes())
            if remnant_digest != truncated_digest:
                return fail("quarantined remnant digest drifted")

            second = download_package(
                full_url(base),
                PACKAGE_ID,
                expected,
                cache,
                quarantine,
                install_root=install,
            )
            if not second.ok:
                return fail(f"follow-on install failed: {second.to_dict()}")
            installed = Path(second.installed_path or "")
            got = sha256_hex(installed.read_bytes())
            if got != expected:
                return fail(f"follow-on digest {got} != expected {expected}")
            if got == truncated_digest:
                return fail("follow-on install used the truncated remnant digest")
            if installed.stat().st_size != len(blob):
                return fail(
                    f"installed size {installed.stat().st_size} != M={len(blob)}"
                )

            cache_payload = cache / PACKAGE_ID / CACHE_PAYLOAD_NAME
            if not cache_payload.is_file():
                return fail("cache payload missing after follow-on")
            cache_digest = sha256_hex(cache_payload.read_bytes())
            if cache_digest != expected:
                return fail("cache payload digest != fixture (poisoned?)")
            if cache_payload.stat().st_size == n:
                return fail("cache payload is still N bytes — remnant promoted")

            if not qpath.is_file():
                return fail("quarantine remnant vanished; cannot prove isolation")
            if sha256_hex(qpath.read_bytes()) == cache_digest:
                return fail("cache digest equals remnant — isolation failed")

            naive_write_partial_into_cache(
                truncate_url(base, n), PACKAGE_ID, naive_cache
            )
            poisoned = install_from_cache(naive_cache, PACKAGE_ID, naive_install)
            poisoned_digest = sha256_hex(poisoned.read_bytes())
            if poisoned_digest != truncated_digest:
                return fail("naive follow-on did not surface remnant poisoning")
            if poisoned_digest == expected:
                return fail("naive remnant unexpectedly matched full digest")

            hits_final = independent_cache_listing(cache, PACKAGE_ID)
            if not listing_names_package(hits_final, PACKAGE_ID):
                return fail(
                    f"honest cache missing package after follow-on: {hits_final}"
                )

    out = {
        "probe": "probe2-follow-on",
        "unit_id": "TST-0131",
        "pass": True,
        "package_id": PACKAGE_ID,
        "n": n,
        "m": len(blob),
        "expected_digest": expected,
        "truncated_digest": truncated_digest,
        "follow_on_digest": got,
        "follow_on_matches_full": True,
        "follow_on_not_remnant": True,
        "naive_follow_on_poisoned": True,
        "quarantine_still_present": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"follow_on_digest={got[:16]}... full={expected[:16]}... "
        f"remnant={truncated_digest[:16]}... naive_poisoned=True"
    )
    print(
        "SUCCESS:TST-0131-probe2 follow-on install after truncation has the correct digest"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
