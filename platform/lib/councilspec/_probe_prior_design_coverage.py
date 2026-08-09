"""Probe: does the new CouncilSpec schema cover the PRIOR design artifacts?

Measures, rather than assumes:
  1. section coverage vs 11-COUNCIL-SPECIFICATION.schema.json (the prior 13-section design);
  2. whether the 58 protocols / 72 presets in 12-COUNCIL-PROTOCOLS-AND-PRESETS.json validate
     against the new schema as-is (the WORK-UNIT-CATALOG IMP-3 falsifiable question).

Read-only. Writes nothing but stdout.
"""

from __future__ import annotations

import json
import os
import sys

CORPUS = r"C:\Users\Prekzursil\.claude\harness-restore-20260806"
PRIOR_SCHEMA = os.path.join(CORPUS, "11-COUNCIL-SPECIFICATION.schema.json")
PRESETS = os.path.join(CORPUS, "12-COUNCIL-PROTOCOLS-AND-PRESETS.json")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from councilspec.registry import load_schema  # noqa: E402
from councilspec.validate import schema_errors  # noqa: E402


def field_names(node, acc):
    """Every property name anywhere in a schema document."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                acc.update(value.keys())
            field_names(value, acc)
    elif isinstance(node, list):
        for item in node:
            field_names(item, acc)
    return acc


def main() -> int:
    print("=" * 78)
    if not os.path.isfile(PRIOR_SCHEMA):
        print("PRIOR SCHEMA ABSENT:", PRIOR_SCHEMA)
        return 2
    with open(PRIOR_SCHEMA, "r", encoding="utf-8") as fh:
        prior = json.load(fh)
    mine = load_schema()

    prior_sections = sorted((prior.get("properties") or {}).keys())
    my_sections = sorted((mine.get("properties") or {}).keys())
    print(f"prior top-level sections ({len(prior_sections)}): {prior_sections}")
    print(f"new   top-level sections ({len(my_sections)}): {my_sections}")
    print(
        f"prior sections MISSING as a top-level key in the new schema: "
        f"{sorted(set(prior_sections) - set(my_sections))}"
    )

    pf = field_names(prior, set())
    mf = field_names(mine, set())
    covered = pf & mf
    print(
        f"\nprior field names: {len(pf)}; new field names: {len(mf)}; "
        f"name-level overlap: {len(covered)} ({100 * len(covered) // max(len(pf), 1)}% of prior)"
    )
    missing = sorted(pf - mf)
    print(f"prior field names absent from the new schema ({len(missing)}):")
    for i in range(0, min(len(missing), 120), 8):
        print("   ", ", ".join(missing[i : i + 8]))
    if len(missing) > 120:
        print(f"    ... and {len(missing) - 120} more")

    print("\n" + "=" * 78)
    if not os.path.isfile(PRESETS):
        print("PRESETS ABSENT:", PRESETS)
        return 0
    with open(PRESETS, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    print(
        "presets doc top-level keys:",
        list(data)[:12] if isinstance(data, dict) else type(data),
    )
    for key in data if isinstance(data, dict) else {}:
        value = data[key]
        if isinstance(value, list):
            print(f"  {key}: list[{len(value)}]")
            if value and isinstance(value[0], dict):
                print(f"     first item keys: {sorted(value[0])[:14]}")
        elif isinstance(value, dict):
            print(f"  {key}: dict[{len(value)}] sample={list(value)[:4]}")

    # The IMP-3 falsifiable question: do the presets validate against the new schema as-is?
    candidates = []
    if isinstance(data, dict):
        for key in ("presets", "council_presets", "items"):
            if isinstance(data.get(key), list):
                candidates = data[key]
                break
    print(f"\npreset objects found for validation: {len(candidates)}")
    ok = 0
    first_err = None
    for preset in candidates:
        errs = schema_errors(preset)
        if not errs:
            ok += 1
        elif first_err is None:
            first_err = (preset.get("id") or preset.get("preset_id") or "?", errs[:3])
    print(
        f"presets validating UNCHANGED against the new schema: {ok}/{len(candidates)}"
    )
    if first_err:
        print(f"first failure: id={first_err[0]}")
        for msg in first_err[1]:
            print("   ", msg[:200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
