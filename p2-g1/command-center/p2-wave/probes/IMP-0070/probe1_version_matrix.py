#!/usr/bin/env python3
"""IMP-0070 probe1: 30-case range matrix on the Python resolver + yank.

The resolver must select identically to the pinned oracle for all 30 cases
(the oracle itself runs in probe2, a different process). Prerelease
precedence must follow SemVer identifier compare - demonstrated against
the string-comparison result, which disagrees. Yank: a yanked pin stays
resolvable from a lockfile and is never selected fresh.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

from tools.marketplace.semver_npm import compare, max_satisfying  # noqa: E402
from tools.marketplace.yank import (  # noqa: E402
    PackageRelease,
    resolve_fresh_install,
    resolve_from_lockfile,
)

VERSIONS = ["0.0.1", "0.0.5", "0.1.0", "0.1.9", "0.2.0", "0.9.0", "1.0.0",
            "1.0.4", "1.2.0", "1.2.9", "1.3.0", "1.9.9", "2.0.0", "2.1.0",
            "2.1.3", "3.0.0", "1.0.0-alpha", "1.0.0-alpha.2",
            "1.0.0-alpha.10", "1.0.0-beta", "1.0.0-beta.2", "1.0.0-rc.1",
            "1.2.0-alpha.1", "1.2.0-beta", "2.0.0-rc.1", "0.1.0-alpha.1",
            "1.5.0", "1.5.0+build.7", "2.1.0+exp.sha.5114f85", "0.0.3"]

EXPECTED = [
    ("^1.0.0", "1.9.9"), ("^0.1.0", "0.1.9"), ("^0.0.1", "0.0.1"),
    ("~1.2.0", "1.2.9"), ("~1.2", "1.2.9"), ("~1", "1.9.9"),
    ("1.2.0", "1.2.0"), ("=1.2.0", "1.2.0"), (">1.0.0", "3.0.0"),
    (">=1.2.0", "3.0.0"), ("<2.0.0", "1.9.9"), ("<=1.2.0", "1.2.0"),
    ("1.2.x", "1.2.9"), ("1.x", "1.9.9"), ("*", "3.0.0"),
    ("1.0.0 - 1.9.0", "1.5.0"), ("^1.0.0 || ^2.0.0", "2.1.3"),
    (">1.0.0 <1.3.0", "1.2.9"), ("~1.2.9", "1.2.9"), ("^0.0.5", "0.0.5"),
    (">=1.0.0-alpha", "3.0.0"), ("1.0.0-alpha.10", "1.0.0-alpha.10"),
    ("^1.2.0-alpha", "1.9.9"), ("~0.1.0", "0.1.9"),
    ("1.x || >=2.1.0 <2.2.0", "2.1.3"), ("^2.0.0-beta", "2.1.3"),
    (">=0.1.0 <0.2.0", "0.1.9"), ("=1.5.0", "1.5.0"),
    ("1.2.0 - 2.1.0", "2.1.0"), ("^1.5.0", "1.9.9"),
]

RELEASES = [
    PackageRelease("1.0.0"),
    PackageRelease("1.1.0"),
    PackageRelease("1.2.0", yanked=True),
    PackageRelease("1.2.9"),
]


def main() -> int:
    checks = {}
    mismatches = []
    for rng, expected in EXPECTED:
        got = max_satisfying(VERSIONS, rng)
        if got != expected:
            mismatches.append({"range": rng, "got": got, "expected": expected})
    checks["matrix_30_exact"] = not mismatches and len(EXPECTED) == 30
    # prerelease precedence is identifier compare; string compare disagrees
    string_rank = "1.0.0-alpha.10" < "1.0.0-alpha.2"
    checks["string_compare_disagrees"] = string_rank is True
    checks["semver_rank_alpha10_gt_alpha2"] = compare(
        "1.0.0-alpha.10", "1.0.0-alpha.2") > 0
    checks["rc_lt_release"] = compare("1.0.0-rc.1", "1.0.0") < 0
    # yank semantics
    checks["yanked_lockfile_pin_resolvable"] = (
        resolve_from_lockfile("1.2.0", RELEASES) == "1.2.0")
    fresh = resolve_fresh_install("^1.0.0", RELEASES)
    checks["yanked_never_fresh"] = fresh != "1.2.0" and fresh == "1.2.9"
    checks["yanked_exact_fresh_none"] = (
        resolve_fresh_install("=1.2.0", RELEASES) is None)
    out = {
        "probe": "probe1-version-matrix",
        "unit_id": "IMP-0070",
        "cases": len(EXPECTED),
        "mismatches": mismatches,
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, sort_keys=True))
    if not all(checks.values()):
        print("FAILED:IMP-0070-probe1 %s" % [k for k, v in checks.items() if not v])
        return 1
    print("SUCCESS:IMP-0070-probe1 30-case matrix exact, prerelease by spec, yank holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
