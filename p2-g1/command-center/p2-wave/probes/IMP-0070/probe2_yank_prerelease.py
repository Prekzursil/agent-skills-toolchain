#!/usr/bin/env python3
"""IMP-0070 probe2: reference-implementation oracle + yank/prerelease reviewer.

Signal 2 of the evidence contract: the SAME 30-case matrix is evaluated by
the pinned reference implementation (node-semver 7.6.3 maxSatisfying) and
selections must agree PER CASE - divergences are listed, never averaged.
Also re-proves, independently of probe1: a yanked pin stays resolvable from
a lockfile while never selected fresh, and prerelease precedence follows
SemVer identifier compare (the string comparison result disagrees).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.marketplace.semver_npm import compare, max_satisfying  # noqa: E402
from tools.marketplace.yank import (  # noqa: E402
    PackageRelease,
    resolve_fresh_install,
    resolve_from_lockfile,
)

VENDOR = REPO / "tools" / "marketplace" / "vendor" / "node-semver"

VERSIONS = ["0.0.1", "0.0.5", "0.1.0", "0.1.9", "0.2.0", "0.9.0", "1.0.0",
            "1.0.4", "1.2.0", "1.2.9", "1.3.0", "1.9.9", "2.0.0", "2.1.0",
            "2.1.3", "3.0.0", "1.0.0-alpha", "1.0.0-alpha.2",
            "1.0.0-alpha.10", "1.0.0-beta", "1.0.0-beta.2", "1.0.0-rc.1",
            "1.2.0-alpha.1", "1.2.0-beta", "2.0.0-rc.1", "0.1.0-alpha.1",
            "1.5.0", "1.5.0+build.7", "2.1.0+exp.sha.5114f85", "0.0.3"]

RANGES = ["^1.0.0", "^0.1.0", "^0.0.1", "~1.2.0", "~1.2", "~1", "1.2.0",
          "=1.2.0", ">1.0.0", ">=1.2.0", "<2.0.0", "<=1.2.0", "1.2.x", "1.x",
          "*", "1.0.0 - 1.9.0", "^1.0.0 || ^2.0.0", ">1.0.0 <1.3.0", "~1.2.9",
          "^0.0.5", ">=1.0.0-alpha", "1.0.0-alpha.10", "^1.2.0-alpha",
          "~0.1.0", "1.x || >=2.1.0 <2.2.0", "^2.0.0-beta", ">=0.1.0 <0.2.0",
          "=1.5.0", "1.2.0 - 2.1.0", "^1.5.0"]

RELEASES = [
    PackageRelease("1.0.0"),
    PackageRelease("1.1.0"),
    PackageRelease("1.2.0", yanked=True),
    PackageRelease("1.2.9"),
]

ORACLE_JS = (
    "const semver=require('semver');"
    "const input=JSON.parse(require('fs').readFileSync(0,'utf8'));"
    "const out=input.ranges.map(r=>semver.maxSatisfying(input.versions,r)||null);"
    "process.stdout.write(JSON.stringify(out));"
)


def run_oracle() -> list[str | None]:
    proc = subprocess.run(
        ["node", "-e", ORACLE_JS],
        cwd=str(VENDOR),
        input=json.dumps({"versions": VERSIONS, "ranges": RANGES}),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"node-semver oracle failed: {proc.stderr[-400:]}")
    return json.loads(proc.stdout)


def main() -> int:
    checks: dict[str, bool] = {}
    refs = run_oracle()
    checks["oracle_case_count"] = len(refs) == len(RANGES) == 30
    divergences = []
    for rng, ref in zip(RANGES, refs):
        ours = max_satisfying(VERSIONS, rng)
        if ours != ref:
            divergences.append({"range": rng, "ours": ours, "reference": ref})
    checks["per_case_agreement"] = not divergences

    # yank: both states, independent of probe1's process
    checks["yank_lockfile_pin_resolvable"] = (
        resolve_from_lockfile("1.2.0", RELEASES) == "1.2.0")
    fresh = resolve_fresh_install("^1.0.0", RELEASES)
    checks["yank_never_fresh"] = fresh != "1.2.0" and fresh == "1.2.9"
    checks["yank_exact_fresh_none"] = (
        resolve_fresh_install("=1.2.0", RELEASES) is None)

    # prerelease precedence by identifier compare; string compare disagrees
    checks["string_compare_disagrees"] = "1.0.0-alpha.10" < "1.0.0-alpha.2"
    checks["semver_identifier_compare"] = compare(
        "1.0.0-alpha.10", "1.0.0-alpha.2") > 0
    checks["release_outranks_prerelease"] = compare("1.0.0-rc.1", "1.0.0") < 0

    out = {
        "probe": "probe2-yank-prerelease-oracle",
        "unit_id": "IMP-0070",
        "reference": "node-semver maxSatisfying (vendored, npm semver 7.6.3)",
        "cases": len(RANGES),
        "agreements": len(RANGES) - len(divergences),
        "divergences": divergences,
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, sort_keys=True))
    if not all(checks.values()):
        print("FAILED:IMP-0070-probe2 %s" % [k for k, v in checks.items() if not v])
        return 1
    print("SUCCESS:IMP-0070-probe2 30/30 identical to node-semver oracle; yank both-states hold; prerelease by identifier compare")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
