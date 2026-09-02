#!/usr/bin/env python3
"""Hermetic scenarios for TST-0080 stale-cache-masks-fixed-package."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from package_cache import (
    BROKEN,
    FIXED,
    OMIT_PATH,
    PKG,
    VERSION,
    Client,
    NameVersionClient,
    Registry,
    broken_package,
    derive_cache_key,
    derive_cache_key_name_version,
    derive_cache_key_omitting,
    extra_mutant,
    fixed_package,
    mutate_shipped_byte,
)


def _estate(tmp: Path, mutant: bool = False) -> dict[str, Any]:
    registry = Registry(tmp / "registry")
    cls = NameVersionClient if mutant else Client
    client = cls(registry, tmp / "cache", tmp / "profile")
    layout = client.enumerated_cache_paths()
    if not layout:
        raise RuntimeError("implementation-returned-empty-cache-layout")
    for spec in layout:
        if not spec.get("path"):
            raise RuntimeError("cache-path-missing-from-implementation")
        if not str(spec["path"]).startswith(str(client.cache_root.resolve())):
            raise RuntimeError("cache-path-outside-client-root")
    return {"registry": registry, "client": client, "layout": layout}


def test_fixed_package_is_observed_after_reinstall(
    tmp: Path | None = None,
) -> dict[str, Any]:
    own = tempfile.TemporaryDirectory(prefix="tst0080-reinstall-") if tmp is None else None
    root = Path(own.name) if own else Path(tmp)  # type: ignore[union-attr]
    try:
        est = _estate(root)
        registry: Registry = est["registry"]
        client: Client = est["client"]
        broken = broken_package()
        fixed = fixed_package()
        key_broken = broken.cache_key()
        key_fixed = fixed.cache_key()
        registry.publish(broken)
        first = client.install(PKG)
        registry.publish(fixed)
        second = client.install(PKG)
        ok = (
            first["behavior"] == BROKEN
            and first["source"] == "registry"
            and first["cache_key"] == key_broken
            and second["behavior"] == FIXED
            and second["source"] == "registry"
            and second["cache_key"] == key_fixed
            and key_broken != key_fixed
            and first["version"] == second["version"] == VERSION
        )
        return {
            "pass": ok,
            "probe": "test_fixed_package_is_observed_after_reinstall",
            "package": PKG,
            "version": VERSION,
            "key_broken": key_broken,
            "key_fixed": key_fixed,
            "keys_differ": key_broken != key_fixed,
            "first": first,
            "second": second,
            "cache_paths_enumerated": est["layout"],
        }
    finally:
        if own is not None:
            own.cleanup()


def test_cache_key_changes_when_any_shipped_byte_changes() -> dict[str, Any]:
    base = fixed_package()
    base_key = base.cache_key()
    rows: list[dict[str, Any]] = []
    all_changed = True
    for rel in sorted(base.files):
        mutant = mutate_shipped_byte(base, rel)
        new_key = mutant.cache_key()
        changed = new_key != base_key
        all_changed = all_changed and changed
        omit_same = False
        if rel.replace("\\", "/") != OMIT_PATH:
            # Mutating a non-omitted file still changes the sound key; the
            # omit-hash of extra.dat is checked in the collision scenario.
            omit_same = (
                derive_cache_key_omitting(
                    mutant.name,
                    mutant.version,
                    mutant.spec_version,
                    mutant.files,
                    OMIT_PATH,
                )
                != derive_cache_key_omitting(
                    base.name,
                    base.version,
                    base.spec_version,
                    base.files,
                    OMIT_PATH,
                )
            )
        rows.append(
            {
                "path": rel.replace("\\", "/"),
                "base_key": base_key,
                "mutant_key": new_key,
                "changed": changed,
                "omit_extra_key_also_changed": omit_same if rel != OMIT_PATH else None,
            }
        )
    extra_only = extra_mutant(base, b"extra-payload-COLLISION\n")
    omit_base = derive_cache_key_omitting(
        base.name, base.version, base.spec_version, base.files, OMIT_PATH
    )
    omit_mut = derive_cache_key_omitting(
        extra_only.name,
        extra_only.version,
        extra_only.spec_version,
        extra_only.files,
        OMIT_PATH,
    )
    sound_extra = extra_only.cache_key()
    ok = (
        all_changed
        and len(rows) == len(base.files) >= 3
        and sound_extra != base_key
        and omit_base == omit_mut
    )
    return {
        "pass": ok,
        "probe": "test_cache_key_changes_when_any_shipped_byte_changes",
        "base_key": base_key,
        "file_count": len(base.files),
        "per_file": rows,
        "all_files_change_key": all_changed,
        "omitting_extra_hides_extra_mutation": omit_base == omit_mut,
        "sound_key_sees_extra_mutation": sound_extra != base_key,
    }


def test_explicit_cache_invalidation_works(
    tmp: Path | None = None,
) -> dict[str, Any]:
    own = tempfile.TemporaryDirectory(prefix="tst0080-invalidate-") if tmp is None else None
    root = Path(own.name) if own else Path(tmp)  # type: ignore[union-attr]
    try:
        est = _estate(root)
        registry: Registry = est["registry"]
        client: Client = est["client"]
        pkg = fixed_package()
        key = pkg.cache_key()
        registry.publish(pkg)
        first = client.install(PKG)
        present_before = key in client.cached_keys()
        dropped = client.invalidate(PKG)
        present_after = key in client.cached_keys()
        rebuilt = client.install(PKG)
        ok = (
            first["behavior"] == FIXED
            and first["source"] == "registry"
            and present_before is True
            and dropped["count"] >= 1
            and key in dropped["dropped_keys"]
            and present_after is False
            and rebuilt["behavior"] == FIXED
            and rebuilt["source"] == "registry"
            and rebuilt["cache_key"] == key
            and key in client.cached_keys()
        )
        return {
            "pass": ok,
            "probe": "test_explicit_cache_invalidation_works",
            "cache_key": key,
            "present_before": present_before,
            "present_after_invalidate": present_after,
            "dropped": dropped,
            "first": first,
            "rebuilt": rebuilt,
            "cache_paths_enumerated": est["layout"],
        }
    finally:
        if own is not None:
            own.cleanup()


def omitted_file_collision() -> dict[str, Any]:
    a = fixed_package()
    b = extra_mutant(a, b"extra-payload-OTHER\n")
    sound_a = a.cache_key()
    sound_b = b.cache_key()
    omit_a = derive_cache_key_omitting(
        a.name, a.version, a.spec_version, a.files, OMIT_PATH
    )
    omit_b = derive_cache_key_omitting(
        b.name, b.version, b.spec_version, b.files, OMIT_PATH
    )
    nv_a = derive_cache_key_name_version(a.name, a.version)
    nv_b = derive_cache_key_name_version(b.name, b.version)
    collided = omit_a == omit_b
    sound_differs = sound_a != sound_b
    nv_collided = nv_a == nv_b
    inventories_differ = a.inventory() != b.inventory()
    ok = (
        collided
        and sound_differs
        and nv_collided
        and inventories_differ
        and a.files[OMIT_PATH] != b.files[OMIT_PATH]
        and a.files["pkg/behavior.py"] == b.files["pkg/behavior.py"]
    )
    return {
        "pass": ok,
        "probe": "omitted_file_collision",
        "omit_path": OMIT_PATH,
        "sound_key_a": sound_a,
        "sound_key_b": sound_b,
        "sound_keys_differ": sound_differs,
        "omit_key_a": omit_a,
        "omit_key_b": omit_b,
        "omitted_hash_collided": collided,
        "name_version_key_a": nv_a,
        "name_version_key_b": nv_b,
        "name_version_collided": nv_collided,
        "two_materially_different_packages_share_one_sound_key": not sound_differs,
        "inventory_a": a.inventory(),
        "inventory_b": b.inventory(),
    }


def name_version_masks_fix(tmp: Path | None = None) -> dict[str, Any]:
    """Detector control: name+version key serves the broken package after a fix."""
    own = tempfile.TemporaryDirectory(prefix="tst0080-nv-") if tmp is None else None
    root = Path(own.name) if own else Path(tmp)  # type: ignore[union-attr]
    try:
        est = _estate(root, mutant=True)
        registry: Registry = est["registry"]
        client: NameVersionClient = est["client"]
        registry.publish(broken_package())
        first = client.install(PKG)
        registry.publish(fixed_package())
        second = client.install(PKG)
        masked = (
            first["behavior"] == BROKEN
            and second["behavior"] == BROKEN
            and second["source"] == "cache"
            and first["cache_key"] == second["cache_key"]
        )
        return {
            "pass": masked,
            "probe": "name_version_masks_fix",
            "first": first,
            "second": second,
            "masked_by_stale_cache": masked,
        }
    finally:
        if own is not None:
            own.cleanup()


def sound_key_source() -> dict[str, Any]:
    from inspect import getsourcelines

    import package_cache as pc

    lines, start = getsourcelines(pc.derive_cache_key)
    return {
        "file": "command-center/p2-wave/probes/TST-0080/package_cache.py",
        "line": start,
        "symbol": "derive_cache_key",
        "quote": "".join(lines),
        "composition": [
            "alg=sha256-canonical-v1",
            "name",
            "version",
            "spec_version",
            "shipped_files[].path",
            "shipped_files[].sha256",
            "shipped_files[].bytes",
        ],
        "demo_key": derive_cache_key(
            PKG, VERSION, "1", fixed_package().files
        ),
    }
