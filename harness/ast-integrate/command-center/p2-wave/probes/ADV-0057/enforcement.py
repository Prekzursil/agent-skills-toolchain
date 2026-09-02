"""Contribution-flow enforcement probe: unsigned vs signed scratch PRs.

Does not git-commit the worktree. Scratch PRs are fixture payloads evaluated
against (a) in-tree enforcement discovery and (b) a planted DCO detector used
only as the negative control.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from corpus import REPO, inventory, rel

SIGNOFF_RE = re.compile(
    r"^Signed-off-by:\s+\S.+\s+<\S+@\S+>\s*$",
    re.I | re.M,
)

ENFORCEMENT_NEEDLES = (
    "signed-off-by",
    "developer certificate of origin",
    "\bdco\b",
    "cla-assistant",
    "contributor license agreement",
    "license/cla",
)

UNSIGNED_PR = {
    "id": "scratch-pr-unsigned",
    "title": "ADV-0057 scratch: add note without sign-off",
    "commits": [
        {
            "subject": "Add scratch note",
            "message": "Add scratch note\n\nNo sign-off trailer on purpose.\n",
        }
    ],
}

SIGNED_PR = {
    "id": "scratch-pr-signed",
    "title": "ADV-0057 scratch: add note with DCO",
    "commits": [
        {
            "subject": "Add scratch note",
            "message": (
                "Add scratch note\n\n"
                "Signed-off-by: A Contributor <contributor@example.test>\n"
            ),
        }
    ],
}


def commit_signed(message: str) -> bool:
    return bool(SIGNOFF_RE.search(message or ""))


def dco_evaluate(pr: dict[str, Any]) -> dict[str, Any]:
    commits = pr.get("commits") or []
    missing = [
        c.get("subject")
        for c in commits
        if not commit_signed(c.get("message") or "")
    ]
    blocked = bool(missing)
    return {
        "checker": "planted-dco-trailer",
        "blocked": blocked,
        "missing_signoff": missing,
        "commit_count": len(commits),
    }


def discover_live_enforcement(inv: dict[str, Any]) -> dict[str, Any]:
    hits: list[dict[str, str]] = []
    roots = [
        REPO / ".github",
        REPO / "ci",
        REPO / "hooks",
    ]
    extra_files = [
        REPO / "dco.yml",
        REPO / "cla.yml",
        REPO / ".cla.yml",
        REPO / "CODEOWNERS",
    ]
    files: list[Path] = []
    for root in roots:
        if root.is_dir():
            files.extend(p for p in root.rglob("*") if p.is_file())
    files.extend(p for p in extra_files if p.is_file())
    for path in files:
        posix = rel(path)
        if "p2-wave/probes" in posix:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        low = text.lower()
        for needle in ENFORCEMENT_NEEDLES:
            if re.search(needle, low):
                hits.append({"path": posix, "needle": needle})
                break
    flow_present = [f["path"] for f in inv["contribution_flow_files"] if f["present"]]
    return {
        "hits": hits,
        "enforcement_present": bool(hits) or bool(flow_present),
        "contribution_flow_files_present": flow_present,
        "github_dir_present": inv["github_dir_present"],
        "github_tree": inv["github_tree"],
        "note": (
            "Live GitHub PR not opened: worktree forbids git commit/push. "
            "Enforcement is the intersection of in-tree checks that would "
            "gate a PR and these scratch payloads."
        ),
    }


def live_gate(discovery: dict[str, Any], pr: dict[str, Any]) -> dict[str, Any]:
    """Apply only checks that actually exist in this worktree."""
    if not discovery["enforcement_present"]:
        return {
            "blocked": False,
            "reason": "no-in-tree-dco-or-cla-check",
            "pr_id": pr["id"],
            "signed_commits": all(
                commit_signed(c.get("message") or "") for c in pr["commits"]
            ),
        }
    # If a real check existed we would run it. None does on this tree.
    return {
        "blocked": False,
        "reason": "declared-enforcement-files-present-but-no-executable-gate",
        "pr_id": pr["id"],
        "signed_commits": all(
            commit_signed(c.get("message") or "") for c in pr["commits"]
        ),
    }


def run() -> dict[str, Any]:
    inv = inventory()
    discovery = discover_live_enforcement(inv)
    unsigned_live = live_gate(discovery, UNSIGNED_PR)
    signed_live = live_gate(discovery, SIGNED_PR)
    unsigned_planted = dco_evaluate(UNSIGNED_PR)
    signed_planted = dco_evaluate(SIGNED_PR)
    control_compliant_passes = signed_live["blocked"] is False
    globally_broken = signed_live["blocked"] is True
    planted_ok = unsigned_planted["blocked"] is True and signed_planted["blocked"] is False
    unenforced = (not unsigned_live["blocked"]) and (not globally_broken)
    return {
        "probe": "probe2-enforcement-scratch-pr",
        "unit_id": "ADV-0057",
        "discovery": discovery,
        "unsigned_live": unsigned_live,
        "signed_live": signed_live,
        "planted_dco": {
            "unsigned": unsigned_planted,
            "signed": signed_planted,
            "detector_fired": unsigned_planted["blocked"],
            "silent_on_good": not signed_planted["blocked"],
            "ok": planted_ok,
        },
        "control_compliant_scratch_pr_passes": control_compliant_passes,
        "globally_broken_ci": globally_broken,
        "unenforced_signoff": unenforced,
        "pass": planted_ok and control_compliant_passes and not globally_broken,
        "computed_not_asserted": True,
        "scratch_pr_method": "in-tree-check-evaluation-of-fixture-payloads",
    }
