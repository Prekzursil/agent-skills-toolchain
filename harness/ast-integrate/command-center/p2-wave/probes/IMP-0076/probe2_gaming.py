#!/usr/bin/env python3
"""Named probe 2: popularity inflation produces no trust change.

Signal 2 is a gaming control. A HIGH publisher with downloads/stars/ratings
cranked to absurd values must keep the same level, millipoint score, component
vector, and scoring_input_sha256. If those fields were merely down-weighted
they would still appear in the scoring canonicalisation and the hash would move.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

from trust_levels import (  # noqa: E402
    LEVEL_HIGH,
    LEVEL_UNRATED,
    compute_publisher_trust,
)

FIXTURE = REPO / "tools/marketplace/fixtures/trust_publishers.json"
RECEIPT = REPO / "command-center/receipts/IMP-0076.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0076-probe2 {msg}")
    return 1


def load_record(fid: str) -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for item in data["publishers"]:
        if item["id"] == fid:
            return copy.deepcopy(item["record"])
    raise KeyError(fid)


def main() -> int:
    if not RECEIPT.is_file():
        return fail("receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0076" not in text:
        return fail("sentinel-absent")

    alice = load_record("alice")
    clean = compute_publisher_trust(alice)
    gamed = copy.deepcopy(alice)
    gamed["downloads"] = 10**12
    gamed["stars"] = 999999
    gamed["ratings"] = 5
    gamed["install_count"] = 777777
    gamed["metrics"] = {
        "weekly_downloads": 42424242,
        "github_stars": 123456,
        "rating_average": 5,
        "likes": 8888,
    }
    dirty = compute_publisher_trust(gamed)

    if clean.level != LEVEL_HIGH:
        return fail(f"alice not HIGH: {clean.level}")
    if dirty.level != clean.level:
        return fail(f"level moved {clean.level} -> {dirty.level}")
    if dirty.score_millipoints != clean.score_millipoints:
        return fail("score moved")
    if dirty.scoring_input_sha256 != clean.scoring_input_sha256:
        return fail("scoring_input_sha256 moved — popularity leaked into the formula")
    if [c.as_dict() for c in dirty.components] != [c.as_dict() for c in clean.components]:
        return fail("component vector moved")
    names = [c.name for c in dirty.components]
    if "downloads" in names or "stars" in names or "ratings" in names:
        return fail("popularity appeared as a scoring component")
    if not dirty.ignored_popularity_fields:
        return fail("gamed record listed no ignored popularity fields")

    empty = load_record("unrated-empty")
    empty["downloads"] = 10**9
    empty["stars"] = 50000
    empty["default_trusted"] = True
    empty["trust_level"] = "DEFAULT-TRUSTED"
    still = compute_publisher_trust(empty)
    if still.level != LEVEL_UNRATED:
        return fail(f"empty+popularity became {still.level}, want UNRATED")
    if still.level == "DEFAULT-TRUSTED":
        return fail("DEFAULT-TRUSTED")

    worse = load_record("near-high")
    worse["conformance_passes"] = 2
    dropped = compute_publisher_trust(worse)
    if dropped.level == clean.level and dropped.score_millipoints == clean.score_millipoints:
        return fail("detector silent: real measurement change did not move trust")
    if dropped.level != "MEDIUM":
        return fail(f"conformance drop expected MEDIUM, got {dropped.level}")

    summary = {
        "probe": "probe2-gaming",
        "unit_id": "IMP-0076",
        "alice_level": clean.level,
        "gamed_level": dirty.level,
        "score_unchanged": dirty.score_millipoints == clean.score_millipoints,
        "scoring_sha_unchanged": dirty.scoring_input_sha256 == clean.scoring_input_sha256,
        "ignored_popularity_fields": list(dirty.ignored_popularity_fields),
        "empty_plus_popularity_level": still.level,
        "measurement_change_moves_level": dropped.level,
        "gaming_strategy": "inflate downloads, stars, ratings, install_count",
        "gaming_works": False,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"clean_sha={clean.scoring_input_sha256} dirty_sha={dirty.scoring_input_sha256} "
        f"ignored={len(dirty.ignored_popularity_fields)}"
    )
    print("SUCCESS:IMP-0076-probe2 popularity gaming produces no trust change")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
