#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.council.presets.catalog import ensure_catalog  # noqa: E402
from tools.council.presets.store import PresetStore, canonical_hash, fidelity_ok, reorder_keys  # noqa: E402


def main() -> int:
    ensure_catalog()
    store = PresetStore()
    presets = store.presets()
    assert len(presets) == 72
    row = store.round_trip_one(presets[0]["id"])
    assert row["fidelity_ok"] and row["edited_hash_changed"]
    original = store.presets()[0]
    mutated = reorder_keys(original, list(reversed(list(original.keys()))))
    ok, diffs = fidelity_ok(original, mutated, allowed_paths=set())
    assert not ok
    assert any(d.get("kind") == "keys_reordered" for d in diffs)
    assert canonical_hash(original) != canonical_hash(mutated)
    print("SUCCESS:test_store presets=72 reorder_detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
