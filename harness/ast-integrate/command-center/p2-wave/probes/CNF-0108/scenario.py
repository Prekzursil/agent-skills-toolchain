"""Run the CNF-0108 history-scan scenario in a tempfile.

Returns a JSON-safe dict. The canary body is attached only under the private
key `_canary_body` so emit can prove the artifact does not contain it; probes
must pop and never print that key.
"""
from __future__ import annotations

import hashlib
import secrets
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from history_repo import build_history_repo  # noqa: E402
from scanners import (  # noqa: E402
    CANARY_PREFIX,
    canary_found,
    packed_blob_shas,
    redact_finding,
    scan_history,
    scan_working_tree,
)

LIVE_ROOT = HERE.parents[3]


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def live_git_present(root: Path) -> dict:
    git_dir = root / ".git"
    return {
        "path": str(root),
        "dot_git_present": git_dir.exists(),
        "history_scanned": False,
        "reason": (
            "live worktree is not a git repository; a working-tree walk of the "
            "program tree is not accepted as history coverage"
            if not git_dir.exists()
            else "live .git present"
        ),
    }


def run_scenario(tmp: Path) -> dict:
    body = secrets.token_urlsafe(24)
    repo = Path(tmp) / "history-repo"
    meta = build_history_repo(repo, CANARY_PREFIX, body)
    hist = scan_history(repo)
    wt_p, wt_e = scan_working_tree(repo)
    packed = packed_blob_shas(repo)
    packed_has_canary_blob = meta["canary_blob"] in packed

    pattern_found = canary_found(hist["pattern_hits"])
    entropy_found = canary_found(hist["entropy_hits"])
    wt_pattern_found = canary_found(wt_p)
    wt_entropy_found = canary_found(wt_e)

    findings: list[dict] = []
    n = 0
    for hit in hist["pattern_hits"] + hist["entropy_hits"]:
        if hit.get("prefix") != CANARY_PREFIX:
            continue
        n += 1
        findings.append(
            redact_finding(
                hit,
                "secret-exposure" if hit["scanner"] == "pattern" else "secret-exposure",
                f"F{n:02d}-{hit['scanner']}",
            )
        )

    live = live_git_present(LIVE_ROOT)
    result = {
        "prefix": CANARY_PREFIX,
        "body_sha256": _sha256_text(body),
        "body_len": len(body),
        "meta": {
            "commits": meta["commits"],
            "canary_commit": meta["canary_commit"],
            "head_commit": meta["head_commit"],
            "canary_blob": meta["canary_blob"],
            "canary_path": meta["canary_path"],
            "canary_branch": meta["canary_branch"],
            "refs": meta["refs"],
            "packs": meta["packs"],
            "head_working_tree_has_canary_file": meta["head_working_tree_has_canary_file"],
        },
        "history": {
            "commits_walked": hist["commits_walked"],
            "blobs_walked": hist["blobs_walked"],
            "packed_object_shas": hist["packed_object_shas"],
            "all_object_shas": hist["all_object_shas"],
        },
        "pattern_found": pattern_found,
        "entropy_found": entropy_found,
        "both_scanners_found": bool(pattern_found and entropy_found),
        "working_tree_only_pattern_found": wt_pattern_found,
        "working_tree_only_entropy_found": wt_entropy_found,
        "working_tree_only_insufficient": (not wt_pattern_found) and (not wt_entropy_found),
        "packed_objects_scanned": hist["packed_object_shas"] > 0,
        "packed_objects_contained_canary_blob": packed_has_canary_blob,
        "findings": findings,
        "live_repository": live,
        "pass": bool(
            pattern_found
            and entropy_found
            and (not wt_pattern_found)
            and (not wt_entropy_found)
            and packed_has_canary_blob
            and not meta["head_working_tree_has_canary_file"]
            and len(findings) >= 2
        ),
        "_canary_body": body,
    }
    return result
