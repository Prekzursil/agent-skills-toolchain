#!/usr/bin/env python3
"""BLD-0002 probe 1: planted controls on a scratch shipped package.

  * orphaned module is reported unreachable
  * hook-manifest-only module is NOT reported (entry-point set includes hooks)
  * importlib.import_module(name_from_config) module is NOT reported
  * covered-but-unreachable files are individually explained
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from engine import run_census  # noqa: E402

SCRATCH = HERE / "fixtures" / "scratch"
UNIT = "BLD-0002"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not SCRATCH.is_dir():
        return fail("scratch fixture missing")
    census = run_census(SCRATCH, coverage_xml=SCRATCH / "coverage.xml")
    unreachable = {row["module"] for row in census["unreachable_modules"]}
    covered_but = {row["module"] for row in census["covered_but_unreachable"]}
    entry = set(census["entry_modules"])
    hook_eps = [
        e
        for e in census["entry_points"]
        if e["module"] == "pkg.hook_only" and e["kind"] == "hook_manifest"
    ]

    checks = []

    def check(cid: str, ok: bool, detail: str) -> None:
        checks.append({"id": cid, "ok": ok, "detail": detail})
        mark = "PASS" if ok else "FAIL"
        print(f"{mark} {cid} {detail}")

    check(
        "orphan-reported",
        "pkg.orphan" in unreachable,
        f"orphan in unreachable={('pkg.orphan' in unreachable)} set={sorted(unreachable)}",
    )
    check(
        "hook-only-not-reported",
        "pkg.hook_only" not in unreachable and "pkg.hook_only" in entry and len(hook_eps) >= 1,
        f"hook_only entry={('pkg.hook_only' in entry)} eps={len(hook_eps)} unreachable={('pkg.hook_only' in unreachable)}",
    )
    check(
        "dynamic-import-not-reported",
        "pkg.dyn_loaded" not in unreachable and "pkg.dyn_loaded" in census["known_modules"],
        f"dyn_loaded unreachable={('pkg.dyn_loaded' in unreachable)} importers={census['dynamic_import_search']['dynamic_importer_modules']}",
    )
    explained = [
        row
        for row in census["covered_but_unreachable"]
        if row["module"] == "pkg.covered_unreach" and row.get("explanation")
    ]
    check(
        "covered-but-unreachable-explained",
        "pkg.covered_unreach" in covered_but and "pkg.covered_unreach" in unreachable and bool(explained),
        f"covered_unreach in both sets={('pkg.covered_unreach' in covered_but)} explained={bool(explained)}",
    )
    check(
        "unused-public-function",
        any(f["symbol"] == "pkg.plugin_cmd:unused_public" for f in census["unreachable_functions"]),
        "plugin_cmd.unused_public listed as entry-point-unreachable",
    )

    payload = {
        "probe": "probe1-controls",
        "unit_id": UNIT,
        "pass": all(c["ok"] for c in checks),
        "checks": checks,
        "unreachable_modules": sorted(unreachable),
        "entry_modules": sorted(entry),
        "covered_but_unreachable": census["covered_but_unreachable"],
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    if not payload["pass"]:
        return fail("one or more planted controls failed")
    print("SUCCESS:BLD-0002-probe1 planted controls (orphan / hook / dynamic / coverage-xcheck)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
