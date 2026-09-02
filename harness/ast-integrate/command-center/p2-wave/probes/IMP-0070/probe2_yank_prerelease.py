#!/usr/bin/env python3
"""IMP-0070 probe 2: yank lockfile vs fresh install + prerelease reviewer check.

Negative control: a yanked version must NOT be selected for a fresh install
of the same range. Independent of probe 1 (does not consult node-semver).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.marketplace.semver_npm import compare  # noqa: E402
from tools.marketplace.yank import (  # noqa: E402
    PackageRelease,
    resolve_from_lockfile,
    resolve_fresh_install,
)

RELEASES = [
    PackageRelease("1.0.0"),
    PackageRelease("1.1.0"),
    PackageRelease("1.2.0", yanked=True),
]


def main() -> int:
    lock = resolve_from_lockfile("1.2.0", RELEASES)
    fresh = resolve_fresh_install("^1.0.0", RELEASES)
    live = resolve_fresh_install(
        "^1.0.0",
        [
            PackageRelease("1.0.0"),
            PackageRelease("1.1.0"),
            PackageRelease("1.2.0", yanked=False),
        ],
    )
    # Reviewer requirement: prerelease precedence is not string comparison.
    string_order = "1.0.0-alpha.10" < "1.0.0-alpha.2"
    semver_order = compare("1.0.0-alpha.10", "1.0.0-alpha.2")
    release_beats_pre = compare("1.0.0-rc.1", "1.0.0") < 0

    payload = {
        "probe": "probe2-yank-and-prerelease",
        "unit_id": "IMP-0070",
        "lockfile_yanked_resolves": lock,
        "fresh_skips_yanked": fresh,
        "fresh_selects_live_when_not_yanked": live,
        "negative_control_fresh_is_not_yanked": fresh != "1.2.0" and fresh == "1.1.0",
        "both_states": {
            "yanked_latest_fresh": fresh,
            "live_latest_fresh": live,
            "detector_fires_only_when_yanked": fresh == "1.1.0" and live == "1.2.0",
        },
        "prerelease_reviewer": {
            "string_cmp_alpha10_lt_alpha2": string_order,
            "semver_cmp_alpha10_gt_alpha2": semver_order > 0,
            "release_outranks_prerelease": release_beats_pre,
            "not_left_to_string_comparison": string_order and (semver_order > 0),
        },
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    ok = (
        lock == "1.2.0"
        and fresh == "1.1.0"
        and live == "1.2.0"
        and string_order
        and semver_order > 0
        and release_beats_pre
    )
    if not ok:
        print("FAILED:IMP-0070-probe2 yank or prerelease precedence")
        return 1
    print(
        "SUCCESS:IMP-0070-probe2 lockfile keeps yanked pin; fresh install skips it; "
        "prerelease identifiers compared numerically"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
