#!/usr/bin/env python3
"""Probe 2: git index + history via plumbing, independent of zip namelist.

Ignore rules are not evidence. Rotation-pool accounts.json must stay
untracked, unstaged, and unmodified. History must still list a deleted
credential-shaped name. Filenames only; fixture bodies are not printed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402
from inventory import KNOWN_PRESENT_REL, ROTATION_POOL_BASENAME  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0116-credential-exclusion.json"


def _sid(run: dict, sid: str) -> dict:
    for row in run["surfaces"]:
        if row["id"] == sid:
            return row
    raise KeyError(sid)


def _art_surfaces(doc: dict) -> list:
    if isinstance(doc.get("surfaces"), list) and doc["surfaces"]:
        return doc["surfaces"]
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if isinstance(report.get("surfaces"), list):
        return report["surfaces"]
    return []


def main() -> int:
    run = S.run_scenario()
    git = _sid(run, "git-index-and-history")
    live_git = run["live_git"]
    pool = git.get("rotation_pool") or {}
    print(
        json.dumps(
            {
                "method": git["method"],
                "tracked_count": len(git.get("tracked") or []),
                "history_count": len(git.get("history_names") or []),
                "known_present_found": git["known_present_found"],
                "hits": [h["path"] for h in git["credential_hits"]],
                "ignore_not_evidence": git.get("ignore_not_evidence"),
                "history_has_deleted_env": git.get("history_has_deleted_env"),
                "head_has_deleted_env": git.get("head_has_deleted_env"),
                "rotation_pool": {
                    "path": pool.get("path"),
                    "tracked": pool.get("tracked"),
                    "staged": pool.get("staged"),
                    "unmodified": pool.get("unmodified"),
                    "bytes": pool.get("bytes"),
                    "contents": None,
                },
                "live_git_present": live_git.get("present"),
                "live_git_unmeasurable": live_git.get("unmeasurable"),
            },
            sort_keys=True,
        )
    )
    if not run.get("pass"):
        print("FAILED:CNF-0116-probe2 scenario controls failed")
        return 1
    if git.get("known_present") != KNOWN_PRESENT_REL or not git["known_present_found"]:
        print("FAILED:CNF-0116-probe2 known-present missing on git surface")
        return 1
    if not git.get("ignore_not_evidence"):
        print("FAILED:CNF-0116-probe2 ignore rules were treated as exclusion proof")
        return 1
    if not git.get("history_has_deleted_env") or git.get("head_has_deleted_env"):
        print("FAILED:CNF-0116-probe2 history listing is working-tree-only")
        return 1
    if pool.get("path") != ROTATION_POOL_BASENAME:
        print("FAILED:CNF-0116-probe2 rotation-pool name mismatch")
        return 1
    if pool.get("tracked") or pool.get("staged") or not pool.get("unmodified"):
        print("FAILED:CNF-0116-probe2 rotation-pool tracked/staged/modified")
        return 1
    if pool.get("contents") is not None:
        print("FAILED:CNF-0116-probe2 rotation-pool contents were captured")
        return 1
    if "ls-files" not in git["method"] or "gitignore" in git["method"].lower().split("not")[0]:
        # method must name git plumbing and say ignore is not the enumerator
        if "not .gitignore" not in git["method"] and "not gitignore" not in git["method"].lower():
            print("FAILED:CNF-0116-probe2 method is not git plumbing")
            return 1
    if live_git.get("unmeasurable") is not True and live_git.get("present") is not True:
        print("FAILED:CNF-0116-probe2 live git state neither present nor unmeasurable")
        return 1
    if not ART.is_file():
        print("FAILED:CNF-0116-probe2 confirmation artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0116-probe2 self-declared {doc.get('state')}")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNF-0116" not in text:
        print("FAILED:CNF-0116-probe2 sentinel absent")
        return 1
    if "CNF-0116-filename-only-fixture" in text:
        print("FAILED:CNF-0116-probe2 artifact stores fixture body")
        return 1
    rec = {s["id"]: s for s in _art_surfaces(doc)}
    gdoc = rec.get("git-index-and-history") or {}
    if not gdoc.get("known_present_found"):
        print("FAILED:CNF-0116-probe2 artifact omitted git known-present")
        return 1
    if gdoc.get("ignore_not_evidence") is not True:
        print("FAILED:CNF-0116-probe2 artifact omitted ignore-not-evidence")
        return 1
    rpool = gdoc.get("rotation_pool") or {}
    if rpool.get("tracked") or rpool.get("staged") or not rpool.get("unmodified"):
        print("FAILED:CNF-0116-probe2 artifact rotation-pool not clean")
        return 1
    if rpool.get("contents") is not None:
        print("FAILED:CNF-0116-probe2 artifact stored rotation-pool contents")
        return 1
    art_hits = sorted(h["path"] for h in gdoc.get("credential_hits") or [])
    now_hits = sorted(h["path"] for h in git["credential_hits"])
    if art_hits != now_hits:
        print("FAILED:CNF-0116-probe2 git hits drifted from artifact")
        print("artifact", art_hits)
        print("live", now_hits)
        return 1
    # Probe 2 must not be a zip namelist clone.
    if "zipfile" in git["method"] or "namelist" in git["method"]:
        print("FAILED:CNF-0116-probe2 used the artifact enumerator")
        return 1
    print("SUCCESS:CNF-0116-probe2 git plumbing ignore-not-evidence rotation-pool")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
