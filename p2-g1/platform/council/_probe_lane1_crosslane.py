"""READ-ONLY cross-lane view of platform/council/presets.

Answers three questions the orchestrator needs and no single lane can answer:
  * how many preset instances exist on disk right now, and how many are lane 1's;
  * whether any two files claim the same council_id (a real collision, since all
    four preset lanes write into ONE shared directory);
  * which of the schema's required preset names are covered by the union of
    everything currently on disk, and which are still uncovered.

It never writes to another lane's file. It reports; it does not reconcile.
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PRESETS = os.path.join(HERE, "presets")
sys.path.insert(0, os.path.join(HERE, "..", "lib"))

from councilspec.registry import SCHEMA_PATH, load_schema  # noqa: E402

LANE1 = {
    "c-m01-micro-triage-2seat",
    "c-m02-micro-go-nogo-3voice",
    "c-m03-micro-single-claim-adjudication",
    "c-m04-micro-second-opinion-crossvendor",
    "c-m05-micro-premortem-solo-plus-critic",
    "c-m06-micro-assumption-check",
    "c-m07-micro-scope-guard",
    "c-m08-micro-cost-sanity",
    "c-m09-micro-security-smell",
    "c-m10-micro-should-we-stop",
    "c-s11-design-gate-5",
    "c-s12-plan-gate-3-adversarial",
    "c-s13-council-4voice-classic",
    "c-s14-critique-panel-rubric",
    "c-s15-arch-review-board-5",
    "c-s16-peer-review-3-blind",
    "c-g73-general-purpose-auto-composed",
}


def main() -> int:
    required = [
        n
        for n in load_schema(SCHEMA_PATH)["$defs"]["preset_name"]["enum"]
        if n != "custom"
    ]
    files = sorted(f for f in os.listdir(PRESETS) if f.endswith(".councilspec.json"))
    by_id: dict[str, list[str]] = {}
    by_name: dict[str, list[str]] = {}
    used: set[str] = set()
    unreadable: list[str] = []

    for name in files:
        try:
            with open(os.path.join(PRESETS, name), "r", encoding="utf-8") as fh:
                spec = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            unreadable.append(f"{name}: {exc}")
            continue
        by_id.setdefault(str(spec.get("council_id")), []).append(name)
        preset = spec.get("preset")
        if preset and preset != "custom":
            used.add(preset)
            by_name.setdefault(preset, []).append(name)

    collisions = {k: v for k, v in by_id.items() if len(v) > 1}
    # Two files claiming the same required preset name is NOT an error - one may
    # be a micro screen and the other the full council - but the orchestrator has
    # to see it to reconcile, so it is reported rather than judged here.
    multi_claimed = {k: v for k, v in by_name.items() if len(v) > 1}
    stems = {f[: -len(".councilspec.json")] for f in files}
    mine = sorted(stems & LANE1)
    others = sorted(stems - LANE1)
    uncovered = [n for n in required if n not in used]

    print(f"files on disk        : {len(files)}")
    print(f"  lane 1 (this unit) : {len(mine)}")
    print(f"  other lanes        : {len(others)}")
    print(f"council_id collisions: {len(collisions)} {collisions or ''}")
    print(f"unreadable           : {len(unreadable)} {unreadable or ''}")
    print(f"required names total : {len(required)}")
    print(f"  covered on disk    : {len(used)} {sorted(used)}")
    print(f"  still uncovered    : {len(uncovered)} {uncovered}")
    print(f"  claimed twice+     : {len(multi_claimed)} {multi_claimed or ''}")
    print(f"other-lane stems     : {others}")

    if collisions or unreadable:
        print("FAILED:lane1-crosslane collision or unreadable file present")
        return 1
    print(
        f"SUCCESS:lane1-crosslane {len(files)} instances, {len(mine)} lane-1, "
        f"0 id collisions, {len(uncovered)} required names still uncovered"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
