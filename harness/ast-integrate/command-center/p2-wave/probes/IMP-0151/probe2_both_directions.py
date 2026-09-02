#!/usr/bin/env python3
"""Probe 2: repo-only and live-only controls classified in both directions.

Both-states: without planted orphans those ids are absent; with them, each
lands in the matching direction. A shared capability must not be filed as an
orphan. Neither side is treated as authoritative on a hash mismatch.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import adapter as A  # noqa: E402
import fixtures as F  # noqa: E402

OUT = HERE / "probe2-both-directions.raw.json"
REPO_ONLY_ID = "repo-only-skill"
LIVE_ONLY_ID = "live-only-skill"
SHARED_ID = "shared-skill"
DIVERGENT_ID = "divergent-skill"


def _ids(report: dict, classification: str, kind: str = "skills") -> set[str]:
    return {
        r["capability_id"]
        for r in report["rows"]
        if r["kind"] == kind and r["classification"] == classification
    }


def _row(report: dict, capability_id: str, kind: str = "skills") -> dict | None:
    for r in report["rows"]:
        if r["kind"] == kind and r["capability_id"] == capability_id:
            return r
    return None


def main() -> int:
    repo_g, live_g = F.build_classify_estate(plant_orphans=False)
    good = A.discover(live_g, repo_g, protect_host=True)
    silent = (
        REPO_ONLY_ID not in _ids(good, "repo-only")
        and LIVE_ONLY_ID not in _ids(good, "live-only")
        and SHARED_ID in _ids(good, "identical")
    )

    repo_b, live_b = F.build_classify_estate(plant_orphans=True)
    bad = A.discover(live_b, repo_b, protect_host=True)
    repo_only = _ids(bad, "repo-only")
    live_only = _ids(bad, "live-only")
    identical = _ids(bad, "identical")
    divergent = _ids(bad, "divergent")
    fired = REPO_ONLY_ID in repo_only and LIVE_ONLY_ID in live_only
    shared_not_orphan = SHARED_ID in identical and SHARED_ID not in repo_only and SHARED_ID not in live_only
    divergent_not_authoritative = DIVERGENT_ID in divergent
    div_row = _row(bad, DIVERGENT_ID)
    neither_side = div_row is not None and div_row["authoritative_side"] is None

    scratch_harvested = any(
        "notes.txt" in (r.get("rel") or "") or r["capability_id"] == "notes"
        for r in bad["rows"]
    )
    readme_harvested = any(r["capability_id"] == "README" for r in bad["rows"])

    # Commands planted in both directions as a second kind (not just skills).
    cmd_repo_only = _ids(bad, "repo-only", kind="commands")
    cmd_live_only = _ids(bad, "live-only", kind="commands")
    commands_ok = "repo-only" in cmd_repo_only and "live-only" in cmd_live_only

    doc = {
        "probe": "probe2-both-directions",
        "unit_id": "IMP-0151",
        "silent_on_good": silent,
        "fired_on_bad": fired,
        "shared_not_orphan": shared_not_orphan,
        "divergent_not_authoritative": divergent_not_authoritative and neither_side,
        "scratch_not_harvested": not scratch_harvested,
        "readme_not_capability": not readme_harvested,
        "commands_both_directions": commands_ok,
        "good_counts": good["counts"],
        "bad_counts": bad["counts"],
        "repo_only_ids": sorted(repo_only),
        "live_only_ids": sorted(live_only),
        "identical_ids": sorted(identical),
        "divergent_ids": sorted(divergent),
        "cited_historical_5_of_88": bad["cited_historical_5_of_88"],
        "pass": bool(
            silent
            and fired
            and shared_not_orphan
            and divergent_not_authoritative
            and neither_side
            and not scratch_harvested
            and not readme_harvested
            and commands_ok
        ),
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"silent_on_good={silent} fired_on_bad={fired} "
        f"shared_not_orphan={shared_not_orphan} "
        f"divergent={divergent_not_authoritative} "
        f"commands_ok={commands_ok} "
        f"repo-only={sorted(repo_only)} live-only={sorted(live_only)}"
    )
    if not doc["pass"]:
        print("FAILED:IMP-0151-probe2 classification both-states")
        return 1
    print("SUCCESS:IMP-0151-probe2 repo-only and live-only classified in both directions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
