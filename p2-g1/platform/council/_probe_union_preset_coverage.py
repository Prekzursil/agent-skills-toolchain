"""Measure the CROSS-LANE union of required preset names in platform/council/presets/.

The lane brief says the union across all four preset lanes must cover the spec's required
presets. One lane cannot assert that, but it CAN measure it: every lane writes into the same
directory, so the union is computable by reading the `preset` field of every
*.councilspec.json on disk and comparing against the schema's preset_name enum.

This is a SNAPSHOT. Sibling lanes are writing concurrently, so a name reported missing here
may land seconds later. The number is therefore evidence for the orchestrator's fan-in gate,
never a verdict on a sibling's work.

Detector control: the run asserts it can see a known-present name (this lane's own
general_purpose_auto_composed) before reporting any name as absent. A scanner that finds
nothing is a broken scanner, not an empty directory.

Run: python platform/council/_probe_union_preset_coverage.py
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", "lib"))
if LIB not in sys.path:
    sys.path.insert(0, LIB)

from councilspec.registry import load_schema  # noqa: E402

PRESETS_DIR = os.path.join(HERE, "presets")
KNOWN_PRESENT = "general_purpose_auto_composed"  # authored by THIS lane


def main() -> int:
    required = [
        n for n in load_schema()["$defs"]["preset_name"]["enum"] if n != "custom"
    ]
    files = sorted(
        n for n in os.listdir(PRESETS_DIR) if n.endswith(".councilspec.json")
    )
    if not files:
        print(
            "FAILED:union-coverage zero preset files found; an empty walk is a broken detector"
        )
        return 1

    by_name = defaultdict(list)
    unreadable = []
    no_preset_field = []
    for name in files:
        try:
            with open(os.path.join(PRESETS_DIR, name), "r", encoding="utf-8") as fh:
                spec = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            # A sibling mid-write is the likely cause; report it, never swallow it.
            unreadable.append(f"{name}: {type(exc).__name__}")
            continue
        preset = spec.get("preset")
        if not preset:
            no_preset_field.append(name)
        else:
            by_name[preset].append(name)

    if KNOWN_PRESENT not in by_name:
        print(
            f"FAILED:union-coverage detector control failed - cannot see the known-present "
            f"name {KNOWN_PRESENT!r}; the scan is not trustworthy"
        )
        return 1
    print(
        f"[CONTROL] scanner sees the known-present name {KNOWN_PRESENT!r} -> trustworthy"
    )

    covered = [n for n in required if n in by_name]
    missing = [n for n in required if n not in by_name]
    dupes = {n: v for n, v in by_name.items() if n != "custom" and len(v) > 1}

    print(f"files scanned          : {len(files)}")
    print(f"unreadable (mid-write) : {len(unreadable)} {unreadable}")
    print(f"no `preset` field      : {len(no_preset_field)} {no_preset_field}")
    print(f"preset=custom          : {len(by_name.get('custom', []))}")
    print(f"required names         : {len(required)}")
    print(f"UNION covered          : {len(covered)}/{len(required)}")
    print(f"UNION still missing    : {len(missing)} -> {missing}")
    if dupes:
        print("duplicated required names (orchestrator may want to dedupe):")
        for n, v in sorted(dupes.items()):
            print(f"   {n}: {v}")

    out = {
        "snapshot_note": "concurrent lanes are still writing; a missing name may land later",
        "files_scanned": len(files),
        "unreadable": unreadable,
        "no_preset_field": no_preset_field,
        "required": required,
        "union_covered": covered,
        "union_missing": missing,
        "duplicated_required_names": {k: v for k, v in sorted(dupes.items())},
        "by_preset_name": {k: sorted(v) for k, v in sorted(by_name.items())},
    }
    dest = os.path.join(HERE, "LANE-4-UNION-COVERAGE.json")
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=2)
        fh.write("\n")
    print(f"wrote {dest}")

    # Coverage of the union is NOT this lane's gate, so an incomplete union is reported, not failed.
    print(
        "SUCCESS:union-coverage snapshot measured "
        f"({len(covered)}/{len(required)} required names present on disk)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
