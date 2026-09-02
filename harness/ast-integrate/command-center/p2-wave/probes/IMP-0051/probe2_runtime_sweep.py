#!/usr/bin/env python3
"""Probe 2: runtime sweep — emitted code matches the declared taxonomy code.

Independent signal (2): actually raise a sample through production APIs
(parse_permission, toml dumper, unique-line differ, widen-consent gate)
and fail() every declared code. A declared taxonomy nothing raises is not
a taxonomy. Uniqueness is re-derived from the JSON file here (not from
identities()) so the reviewer check is a second walker.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import error_taxonomy as et  # noqa: E402

UNIT = "IMP-0051"


def uniqueness_from_json() -> dict:
    """Second walker: parse the JSON file directly, do not call identities()."""
    raw = json.loads(et.TAXONOMY_PATH.read_text(encoding="utf-8"))
    codes = [e["code"] for e in raw["codes"]]
    summaries = [e["summary"] for e in raw["codes"]]
    return {
        "n": len(codes),
        "unique_codes": len(set(codes)) == len(codes),
        "unique_summaries": len(set(summaries)) == len(summaries),
        "code_ids_match": set(codes) == set(raw["code_ids"]),
        "duplicate_codes": [c for c, n in Counter(codes).items() if n > 1],
        "namespace": raw.get("namespace"),
        "never_renumber": raw.get("stability_policy", {}).get("never_renumber"),
    }


def main() -> int:
    uniq = uniqueness_from_json()
    if not (
        uniq["unique_codes"]
        and uniq["unique_summaries"]
        and uniq["code_ids_match"]
        and uniq["namespace"] == "plugin"
        and uniq["never_renumber"] is True
    ):
        print("FAILED:IMP-0051-probe2 uniqueness/stability from JSON")
        print(json.dumps(uniq, indent=2))
        return 1

    auth = et.authentic_triggers()
    sweep = et.sweep_all_via_fail()
    if not auth["all_match"] or auth["n"] < 2:
        print("FAILED:IMP-0051-probe2 authentic triggers")
        print(json.dumps(auth, indent=2)[:4000])
        return 1
    if not sweep["all_match"] or sweep["n"] != uniq["n"]:
        print("FAILED:IMP-0051-probe2 fail() sweep")
        print(json.dumps(sweep, indent=2)[:4000])
        return 1

    # Mismatch control: empty token must be 0321, not 0311.
    import permission_diff as pd

    try:
        pd.parse_permission("   ")
    except et.PluginError as exc:
        if exc.code != "plugin.validation.0321":
            print("FAILED:IMP-0051-probe2 empty token emitted", exc.code)
            return 1
    else:
        print("FAILED:IMP-0051-probe2 empty token did not raise")
        return 1

    out = {
        "probe": "probe2-runtime-sweep",
        "unit_id": UNIT,
        "pass": True,
        "json_uniqueness": uniq,
        "authentic_n": auth["n"],
        "authentic_codes": auth["codes"],
        "sweep_n": sweep["n"],
        "empty_token_code": "plugin.validation.0321",
        "reviewer": {
            "reviewer_id": "IMP-0051-probe2-json-uniqueness",
            "verdict": "PASS",
            "independent": True,
            "no_code_reused_for_two_meanings": uniq["unique_codes"]
            and uniq["unique_summaries"],
            "numbering_leaves_room": all(
                row["room"] for row in et.family_numbering_gaps().values()
            ),
        },
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print("SUCCESS:IMP-0051-probe2 runtime codes match declared; JSON uniqueness holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
