#!/usr/bin/env python3
"""Live (this worktree) scope walk for CC-0011.

Honest coverage: missing inputs are NOT-CHECKED, never a silent zero.
"""
from __future__ import annotations

import os
from pathlib import Path

from scanner import scan_git_history, scan_path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

ROLLBACK_MANIFEST = REPO / "command-center" / "ROLLBACK-MANIFEST.md"
HARNESS_CANDIDATES = [
    Path.home() / ".claude" / "harness-restore-20260806",
    Path("/root/.claude/harness-restore-20260806"),
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806"),
]
AGENTS_CANDIDATES = [
    REPO / "AGENTS.md",
    REPO / "command-center" / "AGENTS.md",
    Path.home() / ".claude" / "AGENTS.md",
]


def _exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def _git_available(path: Path) -> bool:
    return (path / ".git").exists() or (REPO / ".git").exists()


def coverage_inputs() -> dict:
    harness = next((p for p in HARNESS_CANDIDATES if _exists(p)), None)
    agents = next((p for p in AGENTS_CANDIDATES if _exists(p)), None)
    git_root = REPO if (REPO / ".git").exists() else None
    return {
        "command_center_tree": {
            "path": "command-center",
            "present": (REPO / "command-center").is_dir(),
            "coverage": "SCANNED" if (REPO / "command-center").is_dir() else "NOT-CHECKED",
        },
        "tools_tree": {
            "path": "tools",
            "present": (REPO / "tools").is_dir(),
            "coverage": "SCANNED" if (REPO / "tools").is_dir() else "NOT-CHECKED",
        },
        "rollback_manifest": {
            "path": "command-center/ROLLBACK-MANIFEST.md",
            "present": ROLLBACK_MANIFEST.is_file(),
            "coverage": "SCANNED" if ROLLBACK_MANIFEST.is_file() else "NOT-CHECKED",
            "reason": None
            if ROLLBACK_MANIFEST.is_file()
            else "ROLLBACK-MANIFEST.md absent on this worktree",
        },
        "harness_restore": {
            "path": str(harness) if harness else "~/.claude/harness-restore-20260806",
            "present": bool(harness),
            "coverage": "SCANNED" if harness else "NOT-CHECKED",
            "reason": None
            if harness
            else "harness-restore-20260806 corpus absent on this Linux host",
        },
        "agents_md_section_9": {
            "path": str(agents) if agents else "AGENTS.md",
            "present": bool(agents),
            "coverage": "SCANNED" if agents else "NOT-CHECKED",
            "reason": None
            if agents
            else "AGENTS.md absent; applied catalog restatement of section 9 (never print a value, never rotate)",
        },
        "command_center_git_history": {
            "path": str(REPO),
            "present": git_root is not None,
            "coverage": "SCANNED" if git_root is not None else "NOT-CHECKED",
            "reason": None
            if git_root is not None
            else "worktree is not a git repository; live history cannot be walked. Historical-scope capability is proven on a scratch fixture, not this tree.",
        },
    }


def live_scan() -> dict:
    cov = coverage_inputs()
    hits = []
    if cov["command_center_tree"]["coverage"] == "SCANNED":
        hits.extend(
            scan_path(
                REPO / "command-center",
                repo=REPO,
                scope="command-center-working-tree",
            )
        )
    if cov["tools_tree"]["coverage"] == "SCANNED":
        hits.extend(scan_path(REPO / "tools", repo=REPO, scope="tools-working-tree"))
    if cov["rollback_manifest"]["coverage"] == "SCANNED":
        # Manifest names backup paths; scan the manifest itself and any existing
        # paths it lists (read-only). Missing named backups stay NOT-CHECKED.
        hits.extend(
            scan_path(ROLLBACK_MANIFEST, repo=REPO, scope="rollback-manifest")
        )
        text = ROLLBACK_MANIFEST.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip().strip("`")
            if not line or line.startswith("#"):
                continue
            candidate = Path(line) if line.startswith("/") else REPO / line
            if candidate.exists() and candidate != ROLLBACK_MANIFEST:
                hits.extend(
                    scan_path(candidate, repo=REPO, scope="rollback-backup")
                )
    if cov["harness_restore"]["coverage"] == "SCANNED":
        hits.extend(
            scan_path(
                Path(cov["harness_restore"]["path"]),
                repo=REPO,
                scope="harness-restore",
            )
        )
    if cov["command_center_git_history"]["coverage"] == "SCANNED":
        hits.extend(
            scan_git_history(
                REPO,
                pathspec="command-center",
                label_path="command-center",
                scope="command-center-git-history",
            )
        )

    by_class = {"credential-shaped": 0, "placeholder": 0, "synthetic": 0}
    for h in hits:
        by_class[h.classification] = by_class.get(h.classification, 0) + 1

    public = [h.as_public() for h in hits]
    live_secrets = [h for h in hits if h.classification == "credential-shaped"]
    return {
        "coverage": cov,
        "hit_count": len(hits),
        "credential_shaped_count": len(live_secrets),
        "placeholder_count": by_class.get("placeholder", 0),
        "synthetic_count": by_class.get("synthetic", 0),
        "hits": public,
        "whoami": [
            {
                "path": h.path,
                "prefix": h.prefix,
                "byte_length": h.byte_length,
                "variable_name": h.variable_name,
                "whoami_authenticates": h.whoami_authenticates,
                "whoami_status": h.whoami_status or "not-attempted-file-hit-classified-not-live-probe",
            }
            for h in live_secrets
        ],
        "process_env_credential_names_out_of_scope": sorted(
            k
            for k in os.environ
            if any(
                tok in k.upper()
                for tok in ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
            )
        ),
    }
