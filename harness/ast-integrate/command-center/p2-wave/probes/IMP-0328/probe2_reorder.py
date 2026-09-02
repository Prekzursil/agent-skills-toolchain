#!/usr/bin/env python3
"""Probe 2: negative control — key reorder must fail the fidelity check (IMP-0328)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.council.presets.catalog import ensure_catalog  # noqa: E402
from tools.council.presets.store import (  # noqa: E402
    PresetStore,
    canonical_hash,
    fidelity_ok,
    reorder_keys,
)


def main() -> int:
    ensure_catalog()
    store = PresetStore()
    original = store.presets()[0]
    mutated = reorder_keys(original, list(reversed(list(original.keys()))))
    ok, diffs = fidelity_ok(original, mutated, allowed_paths=set())
    kinds = {d.get("kind") for d in diffs}
    identity_ok, identity_diffs = fidelity_ok(original, original, allowed_paths=set())
    hash_changed = canonical_hash(original) != canonical_hash(mutated)

    payload = {
        "probe": "probe2-reorder-negative-control",
        "unit_id": "IMP-0328",
        "preset_id": original["id"],
        "reorder_fidelity_ok": ok,
        "reorder_detected": (not ok) and ("keys_reordered" in kinds),
        "diff_kinds": sorted(kinds),
        "identity_fidelity_ok": identity_ok,
        "identity_diff_count": len(identity_diffs),
        "canonical_hash_changed": hash_changed,
        "pass": (not ok)
        and ("keys_reordered" in kinds)
        and identity_ok
        and identity_diffs == []
        and hash_changed,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if ok:
        print("FAILED:IMP-0328-probe2 reorder was accepted by fidelity check")
        return 1
    if "keys_reordered" not in kinds:
        print("FAILED:IMP-0328-probe2 reorder not classified as keys_reordered")
        return 1
    if not identity_ok or identity_diffs:
        print("FAILED:IMP-0328-probe2 identity check is vacuous or failing")
        return 1
    if not hash_changed:
        print("FAILED:IMP-0328-probe2 canonical hash ignored key order")
        return 1
    print(
        "reorder_detected=True identity_ok=True hash_changed=True "
        f"kinds={sorted(kinds)}"
    )
    print("SUCCESS:IMP-0328-probe2 reorder keys on save; diff check FAILS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
