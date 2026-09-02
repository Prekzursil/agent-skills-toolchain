#!/usr/bin/env python3
"""Named probe 1: known-present, past-EOF, worktree-only, and drift.

Re-runs the fixture git controls live. Also checks the emitted receipt is
honest (not BLOCKED) and that live corpus anchors are not silently resolved
on a git-less worktree.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import run_controls  # noqa: E402
from fixture import make_fixture  # noqa: E402
from resolve import (  # noqa: E402
    VERDICT_DRIFTED,
    VERDICT_MISSING,
    VERDICT_RESOLVED,
    VERDICT_WORKTREE,
    git_available,
)

ART = REPO / "command-center/receipts/CNF-0163.json"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0163-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "CNF-0163":
        return fail(f"unit_id={doc.get('unit_id')}")
    if "SUCCESS:CNF-0163" not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared:{st}")

    with make_fixture() as fix:
        rows = run_controls(fix)
    by_id = {r["id"]: r for r in rows}
    want = {
        "known-present": VERDICT_RESOLVED,
        "known-broken-past-eof": VERDICT_MISSING,
        "worktree-only": VERDICT_WORKTREE,
        "line-drift": VERDICT_DRIFTED,
    }
    for cid, expected in want.items():
        row = by_id.get(cid)
        if not row:
            return fail(f"control missing {cid}")
        if not row["pass"] or row["verdict"] != expected:
            return fail(f"{cid} expected={expected} got={row.get('verdict')}")

    drift = by_id["line-drift"]
    if drift["resolution"].get("drifted_to") != 2:
        return fail(f"drift not to line 2: {drift['resolution'].get('drifted_to')}")
    missing = by_id["known-broken-past-eof"]
    if missing["verdict"] == VERDICT_DRIFTED:
        return fail("past-EOF was merged into drift")

    counts = doc.get("counts") or {}
    for key in (
        VERDICT_RESOLVED,
        VERDICT_DRIFTED,
        VERDICT_MISSING,
        VERDICT_WORKTREE,
    ):
        if key not in counts:
            return fail(f"counts missing {key}")
    live_wt = int(counts.get(VERDICT_WORKTREE) or 0)
    if live_wt < 1:
        return fail("live worktree-only count is 0; harvest empty or silent-pass")
    if git_available(REPO):
        print("note: estate git is present; live resolved may be non-zero")
    else:
        if int(counts.get(VERDICT_RESOLVED) or 0) != 0:
            return fail(
                "git-less worktree must not classify live anchors as resolved"
            )
        if doc.get("estate_git_history_present") is True:
            return fail("receipt claims git history that is absent")

    method = doc.get("method") or {}
    if method.get("git_archive_forbidden") is not True:
        return fail("git_archive_forbidden not true")
    blob_cmd = str(method.get("blob_command") or "")
    if "cat-file" not in blob_cmd or "archive" in blob_cmd:
        return fail(f"blob_command not cat-file: {blob_cmd}")

    src = (HERE / "resolve.py").read_text(encoding="utf-8")
    if "cat-file" not in src:
        return fail("resolve.py does not call cat-file")
    if "'archive'" in src or '"archive"' in src:
        return fail("resolve.py must not invoke the archive porcelain")

    summary = {
        "probe": "probe1-known-present-broken-worktree",
        "unit_id": "CNF-0163",
        "pass": True,
        "controls": {cid: by_id[cid]["verdict"] for cid in want},
        "live_counts": counts,
        "git_available": git_available(REPO),
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:CNF-0163-probe1 known-present / past-EOF / worktree-only / drift")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
