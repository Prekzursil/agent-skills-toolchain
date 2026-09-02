#!/usr/bin/env python3
"""Probe 2: base-version bump over all 72 + non-editable dial REJECT."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0101-a-preset-is-a-typed-delta-over-councilspec-not-a-fork.md"
)
REPO = HERE.parents[3]


def main() -> int:
    C.write_fixtures()
    presets = C.load_presets()
    bump = C.migrate_all(presets)
    print(
        json.dumps(
            {
                "probe": "probe2-bump-and-dials",
                "unit_id": "CNL-0101",
                "preset_count": bump["preset_count"],
                "migrated_count": bump["migrated_count"],
                "cannot_migrate_count": bump["cannot_migrate_count"],
                "cannot_migrate_ids": bump["cannot_migrate_ids"],
                "dropped_base_keys": bump["dropped_base_keys"],
            },
            sort_keys=True,
        )
    )
    if bump["preset_count"] != 72:
        print("FAILED:CNL-0101-probe2 did not count 72")
        return 1
    if bump["migrated_count"] + bump["cannot_migrate_count"] != 72:
        print("FAILED:CNL-0101-probe2 migrate+blocked != 72")
        return 1
    if bump["cannot_migrate_ids"] != ["C-M01", "C-002", "C-003"]:
        print(
            "FAILED:CNL-0101-probe2 unexpected un-migratable "
            f"{bump['cannot_migrate_ids']}"
        )
        return 1
    if bump["migrated_count"] != 69:
        print(f"FAILED:CNL-0101-probe2 migrated={bump['migrated_count']}")
        return 1

    artifact = REPO / OUT
    doc = json.loads(artifact.read_text(encoding="utf-8"))
    recorded = doc.get("version_bump") or {}
    if recorded.get("migrated_count") != 69:
        print("FAILED:CNL-0101-probe2 artifact migrated_count mismatch")
        return 1
    if recorded.get("cannot_migrate_ids") != ["C-M01", "C-002", "C-003"]:
        print("FAILED:CNL-0101-probe2 artifact cannot_migrate mismatch")
        return 1

    silent = json.loads(
        (C.FIXTURES / "silent_non_editable.json").read_text(encoding="utf-8")
    )
    result = C.apply_delta(silent)
    verbatim = result.get("verbatim") or ""
    print(verbatim)
    if not result.get("rejected") or result.get("reason") != "non-editable-dial-override":
        print(f"FAILED:CNL-0101-probe2 silent override not rejected {result}")
        return 1
    if "REJECT non-editable-dial-override" not in verbatim:
        print("FAILED:CNL-0101-probe2 negative control verbatim missing")
        return 1

    legal = presets[20]
    ok = C.apply_delta(legal)
    if not ok.get("ok"):
        print(f"FAILED:CNL-0101-probe2 legal apply rejected {ok}")
        return 1
    print(
        f"legal_apply ok=True preset={legal['id']} "
        f"delta_keys={ok['resolved']['applied_delta_keys']}"
    )
    print(
        "negative_control: apply_delta REJECTs a preset that writes voting "
        "while editable_dials lists only roles; the same function ACCEPTs a "
        "catalog-class preset whose overlay keys are a subset of editable_dials."
    )
    print("SUCCESS:CNL-0101-probe2 version-bump 69/3 and non-editable REJECT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
