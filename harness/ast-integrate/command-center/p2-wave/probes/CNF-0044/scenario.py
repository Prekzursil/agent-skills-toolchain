#!/usr/bin/env python3
"""Disposable fixture: upgrade a package, then roll the registry back.

agree()     — rollback WITH invalidation; warm and cold must match restored.
skip_inv()  — rollback WITHOUT invalidation; warm must resolve the rolled-away
              version while cold resolves the restored version.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from client import (
    PKG,
    PAYLOAD_RESTORED,
    PAYLOAD_ROLLED_AWAY,
    V_RESTORED,
    V_ROLLED_AWAY,
    Client,
    Registry,
    rollback_registry,
)


def _prepare(tmp: Path) -> dict[str, Any]:
    registry = Registry(tmp / "registry")
    warm = Client(registry, tmp / "cache-warm")
    cold = Client(registry, tmp / "cache-cold")
    layout = warm.enumerated_cache_paths()
    if not layout:
        raise RuntimeError("implementation-returned-empty-cache-layout")
    for spec in layout:
        if not spec.get("path"):
            raise RuntimeError("cache-path-missing-from-implementation")
        if not str(spec["path"]).startswith(str(warm.cache_root.resolve())):
            raise RuntimeError("cache-path-outside-client-root")
    registry.publish(PKG, V_RESTORED, PAYLOAD_RESTORED)
    first = warm.resolve(PKG)
    registry.publish(PKG, V_ROLLED_AWAY, PAYLOAD_ROLLED_AWAY)
    # Drop warm resolution so the upgrade is observed, then refill with v2.
    warm.invalidate_rollback_caches()
    upgraded = warm.resolve(PKG)
    if upgraded["version"] != V_ROLLED_AWAY:
        raise RuntimeError(f"upgrade-not-cached:{upgraded['version']}")
    if upgraded["source"] != "registry":
        raise RuntimeError("upgrade-did-not-miss-empty-cache")
    cached_v2 = warm.cache_entry_state(PKG)
    return {
        "tmp": str(tmp),
        "registry": registry,
        "warm": warm,
        "cold": cold,
        "layout": layout,
        "first_resolve": first,
        "upgraded": upgraded,
        "cache_before_rollback": cached_v2,
    }


def agree(tmp: Path | None = None) -> dict[str, Any]:
    own = tempfile.TemporaryDirectory(prefix="cnf0044-agree-") if tmp is None else None
    root = Path(own.name) if own else Path(tmp)  # type: ignore[union-attr]
    try:
        prep = _prepare(root)
        warm: Client = prep["warm"]
        cold: Client = prep["cold"]
        rolled = rollback_registry(
            prep["registry"], [warm], invalidate=True
        )
        warm_after = warm.resolve(PKG)
        cold_after = cold.resolve(PKG)
        cache_after = warm.cache_entry_state(PKG)
        match = (
            warm_after["version"] == cold_after["version"] == V_RESTORED
            and warm_after["digest"] == cold_after["digest"]
        )
        return {
            "pass": match
            and rolled["invalidated"] is True
            and cache_after.get("present") is True
            and cache_after.get("version") == V_RESTORED
            and warm_after["source"] == "registry"
            and len(prep["layout"]) >= 1,
            "probe": "probe1-warm-cold-agree",
            "package": PKG,
            "restored_version": V_RESTORED,
            "rolled_away_version": V_ROLLED_AWAY,
            "warm": warm_after,
            "cold": cold_after,
            "cache_before_rollback": prep["cache_before_rollback"],
            "cache_after_rollback": cache_after,
            "cache_paths_enumerated": prep["layout"],
            "rollback": {
                "invalidated": rolled["invalidated"],
                "dropped": rolled["clients"],
            },
        }
    finally:
        if own is not None:
            own.cleanup()


def skip_inv(tmp: Path | None = None) -> dict[str, Any]:
    own = tempfile.TemporaryDirectory(prefix="cnf0044-skip-") if tmp is None else None
    root = Path(own.name) if own else Path(tmp)  # type: ignore[union-attr]
    try:
        prep = _prepare(root)
        warm: Client = prep["warm"]
        cold: Client = prep["cold"]
        rolled = rollback_registry(
            prep["registry"], [warm], invalidate=False
        )
        warm_after = warm.resolve(PKG)
        cold_after = cold.resolve(PKG)
        mismatch = (
            warm_after["version"] == V_ROLLED_AWAY
            and cold_after["version"] == V_RESTORED
            and warm_after["source"] == "cache"
            and cold_after["source"] == "registry"
        )
        return {
            "pass": mismatch and rolled["invalidated"] is False,
            "probe": "probe2-skip-invalidation",
            "package": PKG,
            "restored_version": V_RESTORED,
            "rolled_away_version": V_ROLLED_AWAY,
            "warm": warm_after,
            "cold": cold_after,
            "cache_before_rollback": prep["cache_before_rollback"],
            "cache_after_rollback": warm.cache_entry_state(PKG),
            "cache_paths_enumerated": prep["layout"],
            "resolution_mismatch": mismatch,
            "rollback": {"invalidated": rolled["invalidated"]},
        }
    finally:
        if own is not None:
            own.cleanup()
