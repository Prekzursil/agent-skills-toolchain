"""IMP-0229: content-addressed artifact cache - bit-flip refetch, counters, staleness."""
from __future__ import annotations

import json
from pathlib import Path

from agentspec.artifact_cache import ArtifactCache, PackageCache, sha256_hex
from agentspec.cache_key import CACHE_KEY_FIELDS, derive_cache_key


def _inputs(digest: str) -> dict:
    return {
        "workflow_id": "wf-1",
        "spec_version": "1",
        "unit_id": "unit-cache",
        "resolved_prompt": "prompt-v1",
        "param_values": {},
        "tool_policy": "read-only",
        "input_artifact_hashes": [digest],
    }


def test_bit_flipped_entry_detected_and_refetched_both_states() -> None:
    good = b"artifact-bytes-v1"
    key = derive_cache_key(_inputs(sha256_hex(good)))
    with tempfile_dir() as root:
        cache = ArtifactCache(root)
        # MISS path: fetched and stored
        assert cache.get(key, lambda: good, expected_artifact_hash=sha256_hex(good)) == good
        assert cache.counters.misses == 1
        # CLEAN entry: served from cache (measured hit, not inference)
        assert cache.get(key, lambda: good, expected_artifact_hash=sha256_hex(good)) == good
        assert cache.counters.hits == 1
        # BIT-FLIP the stored entry: detected on read, refetched, NEVER served
        path = cache.payload_path(key)
        corrupt = bytes([data ^ 0xFF for data in path.read_bytes()])
        path.write_bytes(corrupt)
        refetched = cache.get(key, lambda: good, expected_artifact_hash=sha256_hex(good))
        assert refetched == good, "corrupt bytes must never be served"
        assert cache.counters.corrupt_refetches == 1
        # the repaired entry is back on disk
        assert path.read_bytes() == good


def test_hit_miss_counters_measured() -> None:
    payload = b"counted"
    key = derive_cache_key(_inputs(sha256_hex(payload)))
    with tempfile_dir() as root:
        cache = ArtifactCache(root)
        cache.get(key, lambda: payload, expected_artifact_hash=sha256_hex(payload))
        cache.get(key, lambda: payload, expected_artifact_hash=sha256_hex(payload))
        cache.get(key, lambda: payload, expected_artifact_hash=sha256_hex(payload))
        d = cache.counters.as_dict()
        assert d == {"hits": 2, "misses": 1, "corrupt_refetches": 0, "stale_rejects": 0}


def test_stale_entry_never_masks_fixed_artifact() -> None:
    v1, v2 = b"package-v1", b"package-v2-FIXED"
    with tempfile_dir() as root:
        cache = PackageCache(root, inputs={"workflow_id": "wf-1", "spec_version": "1",
                                           "unit_id": "u", "resolved_prompt": "p",
                                           "param_values": {}, "tool_policy": "ro"})
        # install v1 under its digest
        got1 = cache.get_package("pkg", sha256_hex(v1), fetcher=lambda: v1)
        assert got1 == v1
        # THE PACKAGE IS FIXED: v2 content, v2 digest. The stale v1 entry must not mask it.
        got2 = cache.get_package("pkg", sha256_hex(v2), fetcher=lambda: v2)
        assert got2 == v2, "stale cache masked the fixed package"
        assert cache.cas.counters.misses >= 1


def tempfile_dir():
    import tempfile

    return tempfile.TemporaryDirectory()
