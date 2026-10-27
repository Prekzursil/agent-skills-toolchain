"""Probe 2: the audit read BOTH trees; repo-armed live-absent is listed (IMP-0430)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from audit import build_report  # noqa: E402


def main() -> int:
    report = build_report()
    assert report["read_both"] is True, "audit must open BOTH trees"
    assert report["repo_armed_live_absent"] == ["claims"], report["repo_armed_live_absent"]
    assert report["live_only_scan_misses"] == ["claims"]
    assert report["project_keyed_live"] == ["caches"], report["project_keyed_live"]
    assert report["production_project_keyed"] == [], report["production_project_keyed"]
    assert report["per_store_ok"] == {
        "goal_inject": True, "ledger_replay": True, "claims": True, "caches": True,
    }
    assert report["host_live"]["attempted"] is True

    print("read_both=True")
    print("claims_listed_despite_live_absent=True")
    print("live_only_scan_misses_claims=True")
    print("live_caches_project_keyed=True")
    print("production_repo_not_project_keyed=True")
    print("production_four_stores_in_repo=True")
    print("host_live_attempted=True")
    print("estate repo_armed_live_absent=%s live_only_misses=%s project_keyed_live=%s"
          % (report["repo_armed_live_absent"], report["live_only_scan_misses"],
             report["project_keyed_live"]))
    print("host_live attempted=%s any_present=%s candidates=%s"
          % (report["host_live"]["attempted"], report["host_live"]["any_present"],
             json.dumps(report["host_live"]["candidates"])))
    slim = {k: v for k, v in report.items() if k != "store_table"}
    print(json.dumps(slim, default=str))
    print("SUCCESS:IMP-0430-probe2 audit read BOTH; repo-armed live-absent listed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
