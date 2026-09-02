#!/usr/bin/env python3
"""Probe 1: every named guard must refuse in scratch; UNGUARDED rows reported; containment."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import measure as M  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0052.json"
REQUIRED = {
    "file-or-directory-deletion",
    "git-history-rewrite",
    "force-push",
    "branch-or-worktree-removal",
    "credential-write-or-unset",
    "cloud-spend",
    "remote-repository-creation",
    "package-publication",
    "live-tree-overwrite",
    "shared-service-kill",
    "shared-git-index-staging",
}


def main() -> int:
    live = M.run_campaign()
    view = M.comparison_view(live)
    print(json.dumps(view, sort_keys=True))
    if not live.get("ok"):
        print("FAILED:BLD-0052-probe1 campaign")
        print("tests", view.get("tests"))
        print("containment", view.get("containment"))
        return 1
    if not ART.is_file():
        print("FAILED:BLD-0052-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:BLD-0052-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:BLD-0052" not in json.dumps(doc):
        print("FAILED:BLD-0052-probe1 sentinel-absent")
        return 1
    ids = {row["id"] for row in doc.get("capabilities") or []}
    if ids != REQUIRED:
        print(f"FAILED:BLD-0052-probe1 capability ids {sorted(ids)}")
        return 1
    live_status = view["guard_status_by_id"]
    for row in doc["capabilities"]:
        if row["id"] in live_status and row["guard_status"] != live_status[row["id"]]:
            print(
                f"FAILED:BLD-0052-probe1 status drift {row['id']} "
                f"art={row['guard_status']} live={live_status[row['id']]}"
            )
            return 1
        if row["guard_status"] == "ARMED" and not row["scratch_probe"]["refused"]:
            print(f"FAILED:BLD-0052-probe1 ARMED but not refused {row['id']}")
            return 1
    for gid, g in view["armed_guards"].items():
        if g["status"] != "ARMED" or not g["refused_on_bad"] or not g["silent_or_allows_on_good"]:
            print(f"FAILED:BLD-0052-probe1 guard not both-states {gid} {g}")
            return 1
    if not doc.get("unguarded_operations"):
        print("FAILED:BLD-0052-probe1 unguarded omitted")
        return 1
    if doc["containment"]["outside_scratch_modified"] is not False:
        print("FAILED:BLD-0052-probe1 containment")
        return 1
    if doc["containment"]["canary_intact"] is not True:
        print("FAILED:BLD-0052-probe1 canary")
        return 1
    tests = {t["id"]: t["result"] for t in doc.get("tests") or []}
    for tid in (
        "guard-fire-in-scratch",
        "shared-index-control",
        "unguarded-reported",
        "containment",
    ):
        if tests.get(tid) != "PASS":
            print(f"FAILED:BLD-0052-probe1 test {tid}={tests.get(tid)}")
            return 1
    print(
        "armed=seed-force-overwrite,close-blank-evidence "
        f"unguarded={len(doc['unguarded_operations'])} "
        f"containment_ok={not doc['containment']['outside_scratch_modified']}"
    )
    print("SUCCESS:BLD-0052-probe1 guard-fire unguarded-reported containment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
