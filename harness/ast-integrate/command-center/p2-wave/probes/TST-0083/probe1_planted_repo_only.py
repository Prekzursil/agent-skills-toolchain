#!/usr/bin/env python3
"""Probe 1: planted repo-only skill is found; live-only is not misclassified.

Also measures the availability consequence: a live router cannot select the
planted repo-only skill. Distinct from TST-0079 (sync-tool overwrite safety).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from differ import reconcile, route  # noqa: E402
from fixtures import IDENTICAL_ID, LIVE_ONLY_ID, REPO_ONLY_ID, build_planted_pair  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0083-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0083-p1-") as raw:
        roots = build_planted_pair(Path(raw))
        report = reconcile(roots["repo"], roots["live"])
        repo_ids = [r["skill_id"] for r in report["repo_only"]]
        live_ids = [r["skill_id"] for r in report["live_only"]]
        if REPO_ONLY_ID not in repo_ids:
            return fail(f"planted {REPO_ONLY_ID} missing from repo_only={repo_ids}")
        if LIVE_ONLY_ID in repo_ids:
            return fail("live-only plant leaked into repo_only")
        if REPO_ONLY_ID in live_ids:
            return fail("repo-only plant leaked into live_only")
        planted = next(r for r in report["repo_only"] if r["skill_id"] == REPO_ONLY_ID)
        if "SKILL.md" not in planted["file_list"]:
            return fail(f"repo-only file list missing SKILL.md: {planted['file_list']}")
        if report["counts"]["repo_only"] < 1:
            return fail("repo_only count is zero despite a planted skill")
        routing = route(REPO_ONLY_ID, report)
        if routing.get("status") != "UNAVAILABLE":
            return fail(f"repo-only skill still routable: {routing}")
        if route(IDENTICAL_ID, report).get("status") != "AVAILABLE":
            return fail("shared identical skill not selectable from live")
        payload = {
            "pass": True,
            "probe": "probe1-planted-repo-only",
            "unit_id": "TST-0083",
            "planted_skill_id": REPO_ONLY_ID,
            "repo_only_ids": repo_ids,
            "live_only_ids": live_ids,
            "repo_only_count": report["counts"]["repo_only"],
            "planted_file_list": planted["file_list"],
            "routing": routing,
            "distinct_from_tst0079": report["distinct_from_tst0079"],
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            f"planted={REPO_ONLY_ID} repo_only={repo_ids} "
            f"routing={routing['status']}"
        )
        print("SUCCESS:TST-0083-probe1 differ finds planted repo-only skill")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
