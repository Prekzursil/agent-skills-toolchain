#!/usr/bin/env python3
"""Live fault-injection scenarios for TST-0097."""
from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Callable

from cache import (
    DETECT_INTACT,
    DETECT_LEFTOVER_TMP,
    DETECT_TRUNCATED,
    DETECT_UNREADABLE,
    DETECT_WRONG_HASH,
    INTACT,
    LEFTOVER_TMP,
    TRUNCATED,
    UNREADABLE,
    WRONG_HASH,
    InPlaceWriteCache,
    IntegrityCache,
    SilentServeCache,
    cache_key,
    render_payload,
    sha256_bytes,
)

SOURCE_A = b"plugin-source-A:fixed-package-v2\n" + (b"X" * 4096)
SOURCE_B = b"plugin-source-B:sibling-intact\n" + (b"Y" * 2048)


def _plant(cache: IntegrityCache, source: bytes) -> dict:
    return cache.put(source)


def inject_truncated(cache: IntegrityCache, key: str) -> dict:
    path = cache.payload_path(key)
    data = path.read_bytes()
    path.write_bytes(data[: max(1, len(data) // 4)])
    return {"mode": TRUNCATED, "path": path.as_posix(), "new_size": path.stat().st_size}


def inject_wrong_hash(cache: IntegrityCache, key: str) -> dict:
    path = cache.payload_path(key)
    data = bytearray(path.read_bytes())
    data[0] = data[0] ^ 0xFF
    path.write_bytes(bytes(data))
    return {
        "mode": WRONG_HASH,
        "path": path.as_posix(),
        "new_sha256": sha256_bytes(bytes(data)),
    }


def inject_unreadable(cache: IntegrityCache, key: str) -> dict:
    path = cache.payload_path(key)
    os.chmod(path, 0o000)
    mode = stat.S_IMODE(path.stat().st_mode)
    return {"mode": UNREADABLE, "path": path.as_posix(), "mode": oct(mode)}


def inject_leftover_tmp(cache: IntegrityCache, source: bytes) -> dict:
    result = cache.put(source, interrupt_before_replace=True)
    orphans = cache.list_orphans()
    return {
        "mode": LEFTOVER_TMP,
        "published": cache.payload_path(result["key"]).exists(),
        "leftover_tmp": result["leftover_tmp"],
        "orphan_count": len(orphans),
    }


INJECTORS: dict[str, Callable] = {
    TRUNCATED: inject_truncated,
    WRONG_HASH: inject_wrong_hash,
    UNREADABLE: inject_unreadable,
}


def run_one_mode(root: Path, mode: str) -> dict:
    cache = IntegrityCache(root / mode)
    planted_b = _plant(cache, SOURCE_B)
    expected = render_payload(SOURCE_A)
    expected_sha = sha256_bytes(expected)

    if mode == LEFTOVER_TMP:
        inj = inject_leftover_tmp(cache, SOURCE_A)
        key_a = cache_key(SOURCE_A)
        got = cache.get(SOURCE_A)
        served = got["served"]
        leftover_exists_after = Path(inj["leftover_tmp"]).exists()
        orphans_after = cache.list_orphans()
        swept = got.get("orphans_swept") or []
        return {
            "corruption_mode": LEFTOVER_TMP,
            "detection_mechanism": DETECT_LEFTOVER_TMP,
            "injected": inj,
            "served_corrupt": served != expected,
            "rebuilt": bool(got.get("rebuilt")),
            "payload_sha256_match": sha256_bytes(served) == expected_sha,
            "served_sha256": sha256_bytes(served),
            "expected_sha256": expected_sha,
            "quarantined": bool(swept),
            "quarantine_listing": sorted(p.name for p in cache.quarantine.iterdir()),
            "leftover_cleared": not leftover_exists_after and not orphans_after,
            "published_after_interrupt": inj["published"],
            "sibling_intact": cache.inspect(planted_b["key"]).get("ok") is True,
            "key": key_a,
        }

    planted_a = _plant(cache, SOURCE_A)
    key_a = planted_a["key"]
    inj = INJECTORS[mode](cache, key_a)
    inspected = cache.inspect(key_a)
    got = cache.get(SOURCE_A)
    served = got["served"]
    # After get(), payload must equal expected render, never the planted corrupt bytes.
    return {
        "corruption_mode": mode,
        "detection_mechanism": inspected.get("detection_mechanism") or got.get("detection_mechanism"),
        "inspect_mode": inspected.get("corruption_mode"),
        "injected": inj,
        "served_corrupt": served != expected and not got.get("rebuilt"),
        "rebuilt": bool(got.get("rebuilt")),
        "payload_sha256_match": sha256_bytes(served) == expected_sha,
        "served_sha256": sha256_bytes(served),
        "expected_sha256": expected_sha,
        "quarantined": bool(got.get("quarantined")),
        "quarantine_path": got.get("quarantine_path"),
        "quarantine_listing": sorted(p.name for p in cache.quarantine.iterdir()),
        "inspect_ok_before_get": inspected.get("ok"),
        "sibling_intact": cache.inspect(planted_b["key"]).get("ok") is True,
        "key": key_a,
        "inspect_detail": inspected.get("detail"),
    }


def run_all_modes(root: Path) -> list[dict]:
    rows = []
    for mode in (TRUNCATED, WRONG_HASH, UNREADABLE, LEFTOVER_TMP):
        rows.append(run_one_mode(root / "modes", mode))
    return rows


def run_intact_negative_control(root: Path) -> dict:
    cache = IntegrityCache(root / "intact-control")
    planted = _plant(cache, SOURCE_A)
    before = list(cache.quarantine.iterdir())
    got = cache.get(SOURCE_A)
    after = list(cache.quarantine.iterdir())
    expected = render_payload(SOURCE_A)
    return {
        "corruption_mode": INTACT,
        "detection_mechanism": DETECT_INTACT,
        "served_corrupt": False,
        "rebuilt": bool(got.get("rebuilt")),
        "hit": bool(got.get("hit")),
        "payload_sha256_match": sha256_bytes(got["served"]) == sha256_bytes(expected),
        "quarantined": bool(got.get("quarantined")) or len(after) != len(before),
        "key": planted["key"],
    }


def run_atomic_interrupt(root: Path) -> dict:
    cache = IntegrityCache(root / "atomic")
    planted = cache.put(SOURCE_A, interrupt_before_replace=True)
    key = planted["key"]
    published_payload = cache.payload_path(key).exists()
    published_meta = cache.meta_path(key).exists()
    orphans = cache.list_orphans()
    # Reader must not observe a partial published entry.
    inspect = cache.inspect(key)
    got = cache.get(SOURCE_A)
    expected = render_payload(SOURCE_A)
    return {
        "published_payload_after_interrupt": published_payload,
        "published_meta_after_interrupt": published_meta,
        "orphan_tmp_count": len(orphans),
        "inspect_present": inspect.get("present"),
        "inspect_ok": inspect.get("ok"),
        "partial_published": bool(published_payload or published_meta),
        "rebuilt": bool(got.get("rebuilt")),
        "payload_sha256_match": sha256_bytes(got["served"]) == sha256_bytes(expected),
        "served_corrupt": False,
        "leftover_cleared": len(cache.list_orphans()) == 0,
        "key": key,
        "detection_mechanism": DETECT_LEFTOVER_TMP,
    }


def run_inplace_mutant(root: Path) -> dict:
    """Detector control: in-place write MUST leave a readable partial on the publish path."""
    mutant: InPlaceWriteCache = InPlaceWriteCache(root / "inplace-mutant")
    planted = mutant.put_inplace_partial(SOURCE_A)
    key = planted["key"]
    on_disk = mutant.payload_path(key).read_bytes()
    expected = render_payload(SOURCE_A)
    inspect = mutant.inspect(key)
    return {
        "mutant": "in-place-write",
        "partial_on_publish_path": len(on_disk) != len(expected) and len(on_disk) > 0,
        "on_disk_bytes": len(on_disk),
        "declared_bytes": planted["declared_bytes"],
        "inspect_ok": inspect.get("ok"),
        "inspect_mode": inspect.get("corruption_mode"),
        "detector_fires": inspect.get("ok") is False,
        "key": key,
    }


def run_silent_serve_mutant(root: Path) -> dict:
    """Detector control: silent-serve MUST return corrupt bytes (proves probe can go red)."""
    good = IntegrityCache(root / "silent-setup")
    planted = good.put(SOURCE_A)
    inject_wrong_hash(good, planted["key"])
    corrupt_disk = good.payload_path(planted["key"]).read_bytes()
    expected = render_payload(SOURCE_A)
    mutant = SilentServeCache(root / "silent-setup")  # same root as good
    got = mutant.get(SOURCE_A)
    return {
        "mutant": "silent-serve",
        "served_equals_corrupt_disk": got["served"] == corrupt_disk,
        "served_equals_expected": got["served"] == expected,
        "served_corrupt": got["served"] != expected,
        "detector_fires": got["served"] != expected,
        "p0": "serving a corrupt entry silently is a P0",
        "key": planted["key"],
    }


def run_rebuild_correct(root: Path) -> dict:
    cache = IntegrityCache(root / "rebuild")
    planted = cache.put(SOURCE_A)
    inject_truncated(cache, planted["key"])
    expected = render_payload(SOURCE_A)
    got = cache.get(SOURCE_A)
    after = cache.inspect(planted["key"])
    return {
        "rebuilt": bool(got.get("rebuilt")),
        "payload_sha256_match": sha256_bytes(got["served"]) == sha256_bytes(expected),
        "post_rebuild_inspect_ok": after.get("ok") is True,
        "served_sha256": sha256_bytes(got["served"]),
        "expected_sha256": sha256_bytes(expected),
        "quarantined": bool(got.get("quarantined")),
        "key": planted["key"],
    }


def verdict_modes(rows: list[dict]) -> tuple[bool, str]:
    want = {TRUNCATED, WRONG_HASH, UNREADABLE, LEFTOVER_TMP}
    seen = {r["corruption_mode"] for r in rows}
    if seen != want:
        return False, f"modes={sorted(seen)} want={sorted(want)}"
    for r in rows:
        if r.get("served_corrupt"):
            return False, f"P0 silent-serve mode={r['corruption_mode']}"
        if not r.get("payload_sha256_match"):
            return False, f"rebuild-hash-mismatch mode={r['corruption_mode']}"
        if not r.get("rebuilt"):
            return False, f"not-rebuilt mode={r['corruption_mode']}"
        if r["corruption_mode"] == LEFTOVER_TMP and not r.get("leftover_cleared"):
            return False, "leftover-tmp-not-cleared"
        if r.get("detection_mechanism") in (None, ""):
            return False, f"unnamed-detection mode={r['corruption_mode']}"
        if r.get("sibling_intact") is not True:
            return False, f"sibling-quarantined mode={r['corruption_mode']}"
        if r["corruption_mode"] == TRUNCATED and r.get("inspect_mode") != TRUNCATED:
            return False, f"truncated-not-classified {r.get('inspect_mode')}"
        if r["corruption_mode"] == WRONG_HASH and r.get("inspect_mode") != WRONG_HASH:
            return False, f"wrong-hash-not-classified {r.get('inspect_mode')}"
        if r["corruption_mode"] == UNREADABLE and r.get("inspect_mode") != UNREADABLE:
            return False, f"unreadable-not-classified {r.get('inspect_mode')}"
    return True, "ok"
