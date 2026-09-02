#!/usr/bin/env python3
"""Probe 2: repo-versus-live control asserting the audit read BOTH trees.

A store armed in the repo and absent from live (claims) must be listed.
A live-only scan must miss that store. Production repo must not remain
project-keyed after the fix. Host ~/.claude/hooks is measured, not assumed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402
import fixtures as F  # noqa: E402

OUT = HERE / "probe2-repo-vs-live.raw.json"


def main() -> int:
    repo, live = F.build_estate()
    estate = A.audit(repo, live)
    production = A.audit_production()
    host = production["host_live"]

    claims_listed = "claims" in estate["repo_armed_live_absent"]
    live_only_misses_claims = "claims" in estate["live_only_scan_misses_repo_armed"]
    live_caches_project = "caches" in estate["project_keyed_in_live"]
    repo_claims_session = any(
        r["store"] == "claims"
        and r["repo_present"]
        and r["key_shape"] == "session"
        and r["listed_despite_live_absent"]
        for r in estate["rows"]
    )
    read_both = bool(estate["read_both"] and estate["repo_files_opened"] >= 4 and estate["live_tree_exists"])
    production_repo_clean = production["project_keyed_in_repo"] == []
    host_attempted = bool(host.get("attempted"))
    production_four = {
        r["store"] for r in production["rows"] if r["repo_present"] and r["store"] in A.STORES
    } == set(A.STORES)

    doc = {
        "estate": estate,
        "production": production,
        "checks": {
            "read_both": read_both,
            "claims_listed_despite_live_absent": claims_listed,
            "live_only_scan_misses_claims": live_only_misses_claims,
            "live_caches_project_keyed": live_caches_project,
            "repo_claims_session": repo_claims_session,
            "production_repo_not_project_keyed": production_repo_clean,
            "production_four_stores_in_repo": production_four,
            "host_live_attempted": host_attempted,
            "host_live_any_present": host.get("any_present"),
        },
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for k, v in doc["checks"].items():
        print(f"{k}={v}")
    print(
        f"estate repo_armed_live_absent={estate['repo_armed_live_absent']} "
        f"live_only_misses={estate['live_only_scan_misses_repo_armed']} "
        f"project_keyed_live={estate['project_keyed_in_live']}"
    )
    print(
        f"host_live attempted={host_attempted} any_present={host.get('any_present')} "
        f"candidates={host.get('candidates')}"
    )
    if not all(
        [
            read_both,
            claims_listed,
            live_only_misses_claims,
            live_caches_project,
            repo_claims_session,
            production_repo_clean,
            production_four,
            host_attempted,
        ]
    ):
        print("FAILED:IMP-0430-probe2 repo-versus-live control")
        return 1
    print("SUCCESS:IMP-0430-probe2 audit read BOTH; repo-armed live-absent listed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
