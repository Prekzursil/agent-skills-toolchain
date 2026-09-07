#!/usr/bin/env python3
"""AUD-0003 negative control (tests_required).

Pick a PR known to be fully merged. Against a disposable worktree of
origin/main:

  1. Confirm the detector reports zero missing files among the PR's paths.
  2. Delete one of those files in the worktree.
  3. Confirm the detector reports exactly one missing file.
  4. Remove the worktree (no permanent mutation of tip).

Detector under test: for each PR-touched path that exists at the PR head,
ask whether the corresponding path exists in the local tree under test
(filesystem existence). This is the local-delete half of tests_required;
probe1's commit-to-commit git-diff census is exercised separately.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROBE = Path(__file__).resolve().parent
sys.path.insert(0, str(PROBE))
import sample_bound as SB  # noqa: E402

OUT_JSON = PROBE / "negative-control-local-delete.json"
OUT_RAW = PROBE / "negative-control-local-delete.raw.txt"
# Prefer a small, recently merged PR whose files still exist on main.
CONTROL_PR = 313


def count_missing(tree: Path, paths: list[str]) -> list[str]:
    missing = []
    for p in paths:
        if not (tree / p).is_file():
            missing.append(p)
    return missing


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw: list[str] = [
        "PROBE=AUD-0003-negative-control-local-delete",
        f"STARTED_AT={started}",
        f"CONTROL_PR={CONTROL_PR}",
    ]

    api = SB.gh_json(["api", f"repos/{SB.REPO}/pulls/{CONTROL_PR}"])
    if not api.get("merged_at"):
        OUT_RAW.write_text("FAIL: control PR is not merged\n", encoding="utf-8")
        print("FAIL: control PR not merged")
        return 1

    head = api["head"]["sha"]
    ok_fetch, note = SB.ensure_head_fetched(head, CONTROL_PR)
    raw.append(f"HEAD={head} fetch_ok={ok_fetch} note={note}")
    if not ok_fetch:
        return 1

    paths = SB.pr_files(CONTROL_PR)
    # Only paths that exist at the PR head (deletes in the PR are not "present")
    present_at_head = []
    for p in paths:
        rc, _ = SB.run(["git", "cat-file", "-e", f"{head}:{p}"])
        if rc == 0:
            present_at_head.append(p)
    raw.append(f"PR_PATHS={paths}")
    raw.append(f"PRESENT_AT_HEAD={present_at_head}")
    if not present_at_head:
        raw.append("FAIL: no files present at head to delete")
        OUT_RAW.write_text("\n".join(raw) + "\n", encoding="utf-8")
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="aud0003-wt-"))
    wt = tmp / "main-wt"
    raw.append(f"WORKTREE={wt}")
    try:
        rc, out = SB.run(
            ["git", "worktree", "add", "--detach", str(wt), "origin/main"]
        )
        raw.append(f"worktree_add_rc={rc}")
        if rc != 0:
            raw.append(out[:1000])
            OUT_RAW.write_text("\n".join(raw) + "\n", encoding="utf-8")
            return 1

        # Sanity: every present_at_head path should exist on a clean main worktree
        # for a fully-merged control PR. If a later commit deleted it from main,
        # pick another control — fail closed rather than vacuous pass.
        baseline_missing = count_missing(wt, present_at_head)
        raw.append(f"BASELINE_MISSING={baseline_missing}")
        baseline_ok = len(baseline_missing) == 0
        if not baseline_ok:
            raw.append(
                "FAIL: control PR paths already missing on origin/main; "
                "pick a different fully-merged control"
            )
            doc = {
                "ok": False,
                "baseline_missing_count": len(baseline_missing),
                "after_delete_missing_count": None,
                "error": "control-paths-already-absent-on-main",
            }
            OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
            OUT_RAW.write_text("\n".join(raw) + "\n", encoding="utf-8")
            return 1

        victim = present_at_head[0]
        victim_path = wt / victim
        victim_path.unlink()
        raw.append(f"DELETED={victim}")

        after_missing = count_missing(wt, present_at_head)
        raw.append(f"AFTER_DELETE_MISSING={after_missing}")
        after_ok = after_missing == [victim]

        ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        ok = baseline_ok and after_ok
        raw += [
            f"BASELINE_OK={baseline_ok}",
            f"AFTER_DELETE_OK={after_ok}",
            f"CONTROL_OK={ok}",
            f"ENDED_AT={ended}",
        ]

        doc = {
            "probe": "AUD-0003-negative-control-local-delete",
            "ok": ok,
            "started_at": started,
            "ended_at": ended,
            "control_pr": CONTROL_PR,
            "control_merged_at": api.get("merged_at"),
            "control_head_sha": head,
            "control_merge_commit_sha": api.get("merge_commit_sha"),
            "pr_paths": paths,
            "present_at_head": present_at_head,
            "victim_path": victim,
            "baseline_missing": baseline_missing,
            "baseline_missing_count": len(baseline_missing),
            "after_delete_missing": after_missing,
            "after_delete_missing_count": len(after_missing),
            "expected_after_delete": [victim],
            "worktree": str(wt),
            "method": (
                "temp detached worktree of origin/main; filesystem existence of "
                "PR-head-present paths; unlink one; re-count; remove worktree"
            ),
        }
        OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        OUT_RAW.write_text("\n".join(raw) + "\n", encoding="utf-8")
        print("\n".join(raw))
        print(f"WROTE {OUT_JSON} ok={ok}")
        return 0 if ok else 1
    finally:
        # Always drop the worktree registration, then wipe the temp dir.
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(wt)],
            capture_output=True,
            text=True,
        )
        subprocess.run(["git", "worktree", "prune"], capture_output=True, text=True)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
