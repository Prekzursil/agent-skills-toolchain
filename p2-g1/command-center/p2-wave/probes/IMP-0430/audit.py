"""Repo-vs-live session-keying audit. Reads BOTH trees (IMP-0430).

A store armed in the repo but absent from live is listed
(repo_armed_live_absent), never dismissed; a live-only scan misses it.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def _host_candidates() -> list:
    home = Path.home()
    return [home / ".claude" / "hooks", home / ".codex" / "hooks"]


def build_report() -> dict:
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    from fixtures import FIXTURE_LIVE, scan_store_dir

    repo_scan = scan_store_dir(REPO / "hooks")
    live_scan = scan_store_dir(FIXTURE_LIVE)
    read_both = bool(repo_scan) and bool(live_scan)

    host_rows, any_present = [], False
    for cand in _host_candidates():
        count = sum(1 for _ in cand.glob("*.py")) if cand.is_dir() else 0
        host_rows.append({"path": str(cand), "present": cand.is_dir(), "file_count": count})
        any_present = any_present or cand.is_dir()

    store_table, armed_absent, project_live = [], [], []
    production_project_keyed, per_store_ok = [], {}
    for name in ("goal_inject", "ledger_replay", "claims", "caches"):
        r = repo_scan.get(name, {})
        lv = live_scan.get(name, {})
        row = {
            "store": name,
            "repo_present": bool(r.get("present")),
            "repo_key_shape": r.get("key_shape"),
            "repo_source": r.get("repo_source"),
            "live_present": bool(lv.get("present")),
            "live_key_shape": lv.get("key_shape"),
            "repo_armed_live_absent": bool(r.get("present")) and not lv.get("present"),
            "project_keyed_in_repo": r.get("key_shape") == "project",
            "project_keyed_in_live": lv.get("key_shape") == "project",
            "listed_despite_live_absent": True,
        }
        store_table.append(row)
        if row["repo_armed_live_absent"]:
            armed_absent.append(name)
        if row["project_keyed_in_live"]:
            project_live.append(name)
        if row["project_keyed_in_repo"]:
            production_project_keyed.append(name)
        per_store_ok[name] = bool(row["repo_present"]) and row["repo_key_shape"] == "session"

    return {
        "kind": "session-keying-audit",
        "read_both": read_both,
        "store_table": store_table,
        "repo_armed_live_absent": armed_absent,
        "live_only_scan_misses": list(armed_absent),
        "project_keyed_live": project_live,
        "production_project_keyed": production_project_keyed,
        "per_store_ok": per_store_ok,
        "host_live": {"attempted": True, "any_present": any_present,
                      "candidates": host_rows},
    }
