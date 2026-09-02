#!/usr/bin/env python3
"""Probe 1: `$schema` presence must not change the loaded hook/skill set.

Both-states: identical inventory with and without `$schema`.
Independent signal: fire each resolved hook and observe its marker.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from hooks_client import fire_each, inventory_equals, load  # noqa: E402
from scenario import (  # noqa: E402
    expected_hook_ids,
    expected_skill_ids,
    seed_tree,
)

ART = REPO / "command-center/receipts/TST-0181.json"


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0181-probe1 {msg}")
    return 1


def main() -> int:
    want_hooks = expected_hook_ids()
    want_skills = expected_skill_ids()
    with tempfile.TemporaryDirectory(prefix="tst0181-p1-") as tmp:
        base = Path(tmp)
        man_with = seed_tree(base / "with-schema", schema=True)
        man_without = seed_tree(base / "without-schema", schema=False)
        inv_with = load(man_with)
        inv_without = load(man_without)

        payload = {
            "probe": "probe1-schema-parity",
            "with_schema": inv_with.as_dict(),
            "without_schema": inv_without.as_dict(),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))

        if inv_with.errors or inv_without.errors:
            return _fail(
                f"clean-tree-errors with={inv_with.errors} without={inv_without.errors}"
            )
        if not inv_with.schema_present:
            return _fail("with-schema inventory did not see $schema")
        if inv_without.schema_present:
            return _fail("without-schema inventory reported $schema")
        if inv_with.hook_ids != want_hooks:
            return _fail(f"with-schema hooks {inv_with.hook_ids} want={want_hooks}")
        if inv_without.hook_ids != want_hooks:
            return _fail(f"without-schema hooks {inv_without.hook_ids}")
        if inv_with.skill_ids != want_skills or inv_without.skill_ids != want_skills:
            return _fail("skill set drifted")
        if not inventory_equals(inv_with, inv_without):
            return _fail("loaded sets diverged across $schema forms")
        if inv_with.hook_count != inv_without.hook_count:
            return _fail(
                f"count drifted {inv_with.hook_count} vs {inv_without.hook_count}"
            )

        markers = base / "markers"
        fired_with = fire_each(man_with, markers / "with")
        fired_without = fire_each(man_without, markers / "without")
        if fired_with.errors or fired_without.errors:
            return _fail(
                f"fire-errors with={fired_with.errors} without={fired_without.errors}"
            )
        if set(fired_with.fired) != set(want_hooks):
            return _fail(f"fire-with markers {sorted(fired_with.fired)}")
        if set(fired_without.fired) != set(want_hooks):
            return _fail(f"fire-without markers {sorted(fired_without.fired)}")
        for hid in want_hooks:
            if not str(fired_with.fired[hid]).startswith(f"FIRED:{hid}:"):
                return _fail(f"marker-shape {hid}={fired_with.fired[hid]!r}")
        if set(fired_with.fired) != set(inv_with.hook_ids):
            return _fail("inventory count and fire-probe set disagree")

        print(
            "schema_parity "
            f"hooks={inv_with.hook_count} skills={inv_with.skill_count} "
            f"fired={len(fired_with.fired)} identical=true"
        )

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:TST-0181" not in text:
            return _fail("receipt-sentinel-absent")
        doc = json.loads(text)
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return _fail(f"receipt-self-declared {doc.get('state')}")
        if not doc.get("schema_key_does_not_change_loaded_set"):
            return _fail("receipt-flag-schema-parity-absent")

    print("SUCCESS:TST-0181-probe1 $schema does not change loaded hooks/skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
