#!/usr/bin/env python3
"""IMP-0040 probe 2: TTL negative control + concurrent read/write.

NEGATIVE CONTROL (both-states): TimeBasedPluginCache must FAIL the source-change
oracle inside its TTL window (serves stale artefact). Content-addressed cache
must PASS the same oracle.

Also: concurrent readers/writers must not tear a payload.
Independent reviewer signal: cache_key includes plugin version AND source hash;
implementation lives in plugin-cache-reaper (facade does not reimplement layout).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TEST_DIR = REPO / "tools" / "plugin" / "tests"
CACHE_PY = REPO / "tools" / "plugin" / "cache.py"
REAP_PY = REPO / "tools" / "plugin-cache-reaper" / "reap.py"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(REPO / "tools" / "plugin"))

import test_cache_content_addressing as T  # noqa: E402


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    try:
        ttl_result = T.test_time_based_cache_fails_within_ttl()
        T.test_concurrent_read_write_does_not_corrupt()
        ca_result = T.test_source_change_forces_new_key()
        T.ContentAddressingTests().test_key_includes_version_and_source_hash()
    except AssertionError as exc:
        print(f"FAILED:IMP-0040-probe2 {exc}")
        return 1

    facade = CACHE_PY.read_text(encoding="utf-8")
    reap_src = REAP_PY.read_text(encoding="utf-8")
    facade_is_import_only = (
        "ContentAddressedPluginCache = _MOD.ContentAddressedPluginCache" in facade
        and "def get_or_compute" not in facade
    )
    reap_defines_layout = "PAYLOAD_NAME" in reap_src and "def cache_key" in reap_src
    duplicated_layout = facade.count("payload.bin") > 0
    key_has_version = "plugin_version" in reap_src and "source_digest" in reap_src

    report = {
        "probe": "IMP-0040-probe2",
        "ttl_negative_control": {
            "served_stale_inside_ttl": ttl_result["served_new_equals_expected_old"],
            "did_not_serve_new_artefact": not ttl_result["served_new_equals_expected_new"],
            "keys_after_old": ttl_result["keys_after_old"],
            "keys_after_new": ttl_result["keys_after_new"],
        },
        "content_addressed_same_oracle": {
            "served_new_equals_expected_new": ca_result["served_new_equals_expected_new"],
            "on_disk_key_changed": ca_result["on_disk_key_changed"],
        },
        "concurrent_read_write_uncorrupted": True,
        "reviewer": {
            "cache_key_includes_plugin_version_and_source_hash": key_has_version,
            "reaper_extended_not_duplicated": facade_is_import_only and reap_defines_layout,
            "facade_reimplements_layout": duplicated_layout,
            "reap_sha256": _sha(REAP_PY),
            "facade_sha256": _sha(CACHE_PY),
        },
    }
    print(json.dumps(report, indent=1, sort_keys=True))
    ok = (
        ttl_result["served_new_equals_expected_old"]
        and not ttl_result["served_new_equals_expected_new"]
        and ca_result["served_new_equals_expected_new"]
        and ca_result["on_disk_key_changed"]
        and facade_is_import_only
        and reap_defines_layout
        and key_has_version
        and not duplicated_layout
    )
    if not ok:
        print("FAILED:IMP-0040-probe2 negative control or reviewer checks")
        return 1
    print(
        "ttl_stale=True ca_fresh=True concurrent_ok=True "
        "reaper_extended=True key_has_version_and_hash=True"
    )
    print("SUCCESS:IMP-0040-probe2 ttl-negative-control and concurrency")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
