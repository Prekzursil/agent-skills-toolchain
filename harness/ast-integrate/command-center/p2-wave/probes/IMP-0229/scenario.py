"""Shared IMP-0229 scenarios: bit-flip both-states, stale-package, key mutations.

Imports the live tools/agentspec backend. Probes do not reimplement the store.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path
from typing import Any


def _load(name: str, rel: str):
    path = Path(__file__).resolve().parents[4] / rel
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


REPO = Path(__file__).resolve().parents[4]
_cache = _load(
    "imp0229_artifact_cache",
    "tools/agentspec/agentspec/artifact_cache.py",
)
_key = _load(
    "imp0229_cache_key",
    "tools/agentspec/agentspec/cache_key.py",
)
FAILURE_CLASSES = _cache.FAILURE_CLASSES
ArtifactCache = _cache.ArtifactCache
PackageCache = _cache.PackageCache
sha256_hex = _cache.sha256_hex
CACHE_KEY_FIELDS = _key.CACHE_KEY_FIELDS
InvalidCacheKey = _key.InvalidCacheKey
derive_cache_key = _key.derive_cache_key

UNIT = "IMP-0229"
PACKAGE_ID = "pkg.fixture.cache-backend"


def base_inputs(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "workflow_id": "wf.cas-cache",
        "spec_version": "1.0.0",
        "unit_id": UNIT,
        "resolved_prompt": "content-addressed artifact cache",
        "param_values": {"mode": "cas", "integrity": "required"},
        "tool_policy": {"network": "deny", "write": "cache-root-only"},
        "input_artifact_hashes": ["ab" * 32],
    }
    data.update(overrides)
    return data


def flip_one_bit(path: Path) -> bytes:
    raw = bytearray(path.read_bytes())
    if not raw:
        raise AssertionError("cannot bit-flip an empty payload")
    raw[0] ^= 0x01
    path.write_bytes(bytes(raw))
    return bytes(raw)


def run_bitflip_both_states() -> dict[str, Any]:
    """Clean entry is a measured hit; bit-flipped entry is refetched, never served."""
    origin = b"IMP-0229-clean-artifact-v1\npayload-bytes-for-integrity\n"
    fetches = {"n": 0}

    def fetcher() -> bytes:
        fetches["n"] += 1
        return origin

    with tempfile.TemporaryDirectory(prefix="imp0229-bitflip-") as tmp:
        cache = ArtifactCache(Path(tmp) / "cas")
        key = derive_cache_key(base_inputs(input_artifact_hashes=[sha256_hex(origin)]))

        first = cache.get(key, fetcher, expected_artifact_hash=sha256_hex(origin))
        miss_after_first = dict(cache.counters.as_dict())
        second = cache.get(key, fetcher, expected_artifact_hash=sha256_hex(origin))
        hit_after_second = dict(cache.counters.as_dict())

        flipped = flip_one_bit(cache.payload_path(key))
        after_corrupt = cache.get(
            key, fetcher, expected_artifact_hash=sha256_hex(origin)
        )
        final = dict(cache.counters.as_dict())

        served_flipped = after_corrupt == flipped
        clean_ok = first == origin and second == origin
        refetch_ok = after_corrupt == origin and not served_flipped
        both_states = (
            miss_after_first["misses"] == 1
            and hit_after_second["hits"] == 1
            and hit_after_second["corrupt_refetches"] == 0
            and final["corrupt_refetches"] == 1
            and refetch_ok
            and clean_ok
        )
        return {
            "probe": "probe1-bitflip-both-states",
            "unit_id": UNIT,
            "failure_class": "corrupted-cache tests",
            "origin_sha256": sha256_hex(origin),
            "flipped_sha256": sha256_hex(flipped),
            "flipped_equals_origin": flipped == origin,
            "served_flipped": served_flipped,
            "clean_served": clean_ok,
            "corrupt_refetched_original": refetch_ok,
            "fetcher_calls": fetches["n"],
            "counters_after_miss": miss_after_first,
            "counters_after_clean_hit": hit_after_second,
            "counters_after_corrupt": final,
            "both_states": both_states,
            "pass": both_states and not served_flipped,
        }


class NameOnlyCache:
    """Mutant: indexes by package id only. A republished fix stays masked."""

    def __init__(self) -> None:
        self._by_name: dict[str, bytes] = {}
        self.hits = 0
        self.misses = 0

    def get_package(self, package_id: str, current: bytes) -> bytes:
        if package_id in self._by_name:
            self.hits += 1
            return self._by_name[package_id]
        self.misses += 1
        self._by_name[package_id] = current
        return current


def run_stale_fixed_package() -> dict[str, Any]:
    """After publishing a fix, the CAS serves the new bytes on the next get.

    A name-only mutant still serves v1 — that is the negative control for
    'stale cache masks a fixed package'.
    """
    v1 = b"package-v1-vulnerable\n"
    v2 = b"package-v2-fixed-payload\n"
    h1 = sha256_hex(v1)
    h2 = sha256_hex(v2)
    origin = {"current": v1}
    fetches = {"n": 0}

    def fetcher() -> bytes:
        fetches["n"] += 1
        return origin["current"]

    with tempfile.TemporaryDirectory(prefix="imp0229-stale-") as tmp:
        store = ArtifactCache(Path(tmp) / "cas")
        pkg = PackageCache(store, base_inputs())

        got_v1 = pkg.get_package(PACKAGE_ID, h1, fetcher)
        after_v1 = dict(store.counters.as_dict())
        hit_v1 = pkg.get_package(PACKAGE_ID, h1, fetcher)
        after_hit = dict(store.counters.as_dict())

        origin["current"] = v2
        got_v2 = pkg.get_package(PACKAGE_ID, h2, fetcher)
        after_fix = dict(store.counters.as_dict())
        hit_v2 = pkg.get_package(PACKAGE_ID, h2, fetcher)
        after_fix_hit = dict(store.counters.as_dict())

        mutant = NameOnlyCache()
        mutant.get_package(PACKAGE_ID, v1)
        origin["current"] = v2
        mutant_after_fix = mutant.get_package(PACKAGE_ID, v2)

        cas_unmasked = got_v2 == v2 and hit_v2 == v2 and got_v1 == v1 and hit_v1 == v1
        mutant_masked = mutant_after_fix == v1
        counters_ok = (
            after_v1["misses"] == 1
            and after_hit["hits"] == 1
            and after_fix["misses"] == 2
            and after_fix["stale_rejects"] >= 1
            and after_fix_hit["hits"] == 2
        )
        key_v1 = derive_cache_key(base_inputs(input_artifact_hashes=[h1]))
        key_v2 = derive_cache_key(base_inputs(input_artifact_hashes=[h2]))
        return {
            "probe": "probe2-stale-fixed-package",
            "unit_id": UNIT,
            "failure_class": "stale cache masks a fixed package",
            "named_failure_classes": list(FAILURE_CLASSES),
            "v1_sha256": h1,
            "v2_sha256": h2,
            "key_v1": key_v1,
            "key_v2": key_v2,
            "keys_differ": key_v1 != key_v2,
            "cas_served_v1_then_v2": cas_unmasked,
            "name_only_mutant_still_served_v1": mutant_masked,
            "fetcher_calls": fetches["n"],
            "counters_after_first_miss": after_v1,
            "counters_after_warm_hit": after_hit,
            "counters_after_publish_fix": after_fix,
            "counters_after_fix_hit": after_fix_hit,
            "hits_measured": after_fix_hit["hits"],
            "misses_measured": after_fix_hit["misses"],
            "stale_rejects_measured": after_fix_hit["stale_rejects"],
            "pass": cas_unmasked and mutant_masked and counters_ok and key_v1 != key_v2,
        }


def run_seven_key_mutations() -> dict[str, Any]:
    """Changing any of the seven IMP-0141 inputs must change the key."""
    baseline = derive_cache_key(base_inputs())
    mutations: list[dict[str, Any]] = []
    variants: list[tuple[str, dict[str, Any]]] = [
        ("workflow_id", base_inputs(workflow_id="wf.other")),
        ("spec_version", base_inputs(spec_version="1.0.1")),
        ("unit_id", base_inputs(unit_id="IMP-0000")),
        ("resolved_prompt", base_inputs(resolved_prompt="other prompt")),
        ("param_values", base_inputs(param_values={"mode": "cas", "integrity": "off"})),
        ("tool_policy", base_inputs(tool_policy={"network": "allow"})),
        (
            "input_artifact_hashes",
            base_inputs(input_artifact_hashes=["cd" * 32]),
        ),
    ]
    keys = {baseline}
    for field, inp in variants:
        k = derive_cache_key(inp)
        distinct = k != baseline and k not in keys
        keys.add(k)
        mutations.append(
            {"field": field, "key": k, "changed": k != baseline, "unique": distinct}
        )
    invalid_named = None
    try:
        derive_cache_key(base_inputs(workflow_id=""))
    except InvalidCacheKey as exc:
        invalid_named = {"field": exc.field, "reason": exc.reason}
    all_changed = all(m["changed"] and m["unique"] for m in mutations)
    return {
        "baseline": baseline,
        "mutations": mutations,
        "distinct_count": len(keys),
        "fields": list(CACHE_KEY_FIELDS),
        "invalid_blank_workflow_named": invalid_named,
        "pass": all_changed and len(keys) == 8 and invalid_named is not None,
    }


def source_has_no_clock(rel: str) -> bool:
    """True when the module does not import clock/entropy/host sources."""
    banned = {"datetime", "time", "random", "uuid", "socket", "platform"}
    text = (REPO / rel).read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.split("#", 1)[0].strip()
        if not (stripped.startswith("import ") or stripped.startswith("from ")):
            continue
        tokens = {
            t.strip()
            for t in stripped.replace(",", " ").replace(".", " ").split()
            if t.strip()
        }
        if tokens & banned:
            return False
    return True
