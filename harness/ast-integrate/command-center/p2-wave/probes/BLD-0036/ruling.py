#!/usr/bin/env python3
"""Per-file authority: git log %cI vs live mtime, plus live-larger content read.

git log is always invoked. This estate root has no .git, so exit is recorded
verbatim and an independent fixture ledger supplies the repo-side analogue
(not derived from live mtime). Unique lines on both sides force MERGE even
when one clock is newer.
"""
from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import classify as C

REPO = Path(__file__).resolve().parents[3]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def iso_mtime(path: Path) -> str | None:
    if not path.is_file():
        return None
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_log_cI(rel: str, cwd: Path | None = None) -> tuple[int, str]:
    cmd = ["git", "log", "-1", "--format=%cI", "--", rel]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd or REPO),
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, f"{type(exc).__name__}:{exc}"
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        return proc.returncode, err or out or "git-log-empty"
    return proc.returncode, out


def read_text_bytes(path: Path) -> tuple[bytes | None, str | None]:
    if not path.is_file():
        return None, None
    raw = path.read_bytes()
    return raw, raw.decode("utf-8", errors="replace")


def rule_file(
    rel: str,
    repo_root: Path,
    live_root: Path,
    ledger: dict[str, str],
) -> dict:
    rp, lp = repo_root / rel, live_root / rel
    repo_raw, repo_text = read_text_bytes(rp)
    live_raw, live_text = read_text_bytes(lp)
    classification = C.classify_pair(repo_text, live_text, repo_raw, live_raw)
    verdict = C.verdict_for(classification)
    git_rc, git_raw = git_log_cI(rel, cwd=REPO)
    git_iso = git_raw if git_rc == 0 and git_raw[:1].isdigit() else None
    ledger_iso = ledger.get(rel)
    repo_u, live_u, shared = C.unique_lists(repo_text, live_text)
    repo_bytes = len(repo_raw) if repo_raw is not None else 0
    live_bytes = len(live_raw) if live_raw is not None else 0
    preview = None
    if verdict == C.MERGE and repo_text is not None and live_text is not None:
        preview = C.union_preview(repo_text, live_text)
    return {
        "path": rel,
        "classification": classification,
        "verdict": verdict,
        "repo_exists": repo_text is not None,
        "live_exists": live_text is not None,
        "repo_bytes": repo_bytes,
        "live_bytes": live_bytes,
        "live_larger": (
            classification not in {C.BYTE_IDENTICAL, C.EOL_ONLY}
            and live_bytes > repo_bytes
            and repo_text is not None
            and live_text is not None
        ),
        "repo_larger": (
            classification not in {C.BYTE_IDENTICAL, C.EOL_ONLY}
            and repo_bytes > live_bytes
            and repo_text is not None
            and live_text is not None
        ),
        "repo_sha256": sha256_bytes(repo_raw) if repo_raw is not None else None,
        "live_sha256": sha256_bytes(live_raw) if live_raw is not None else None,
        "signal1_git_log_cI": {
            "command": f"git log -1 --format=%cI -- {rel}",
            "exit_code": git_rc,
            "raw": git_raw[:500],
            "iso": git_iso,
            "independent_ledger_iso": ledger_iso,
            "used": git_iso or ledger_iso,
            "note": (
                "git log is signal 1 when a git repo is present. This worktree "
                "has no .git at the estate root; the fixture ledger ISO is the "
                "independent repo-side timestamp analogue and is not derived "
                "from live mtime."
            ),
        },
        "signal2_live_mtime": iso_mtime(lp),
        "repo_unique_line_count": len(repo_u),
        "live_unique_line_count": len(live_u),
        "shared_line_count": len(shared),
        "repo_unique_lines": repo_u[:20],
        "live_unique_lines": live_u[:20],
        "union_preview": preview,
        "timestamps_do_not_authorise_overwrite_when_both_unique": classification
        == C.BOTH_UNIQUE,
        "authority_basis": _basis(classification, verdict, git_iso or ledger_iso, iso_mtime(lp)),
    }


def _basis(classification: str, verdict: str, repo_iso: str | None, live_iso: str | None) -> str:
    if verdict == C.NO_ACTION:
        return "byte-identical; neither side has unique content; NO-ACTION."
    if verdict == C.VERDICT_EOL:
        return (
            "LF-normalised bodies are identical; difference is line endings only; "
            "EOL-ONLY and excluded from the merge plan."
        )
    if verdict == C.MERGE:
        return (
            f"both sides hold unique lines (classification={classification}); "
            f"repo_committer={repo_iso} live_mtime={live_iso}; clocks are "
            "provenance only and do not pick a side."
        )
    if verdict == C.REPO_AUTH:
        return (
            f"live line-set is a subset of repo (classification={classification}); "
            f"taking live would drop repo-only lines. repo_committer={repo_iso} "
            f"live_mtime={live_iso}."
        )
    if verdict == C.LIVE_AUTH:
        return (
            f"repo line-set is a subset of live (classification={classification}); "
            f"taking repo would drop live-only policy lines. repo_committer={repo_iso} "
            f"live_mtime={live_iso}."
        )
    return f"classification={classification} verdict={verdict}"


def rule_all(repo_root: Path, live_root: Path, ledger: dict[str, str]) -> list[dict]:
    from trees import iter_rel

    keys = sorted(set(iter_rel(repo_root)) | set(iter_rel(live_root)))
    return [rule_file(rel, repo_root, live_root, ledger) for rel in keys]


def merge_plan(rows: list[dict]) -> list[dict]:
    plan = []
    for row in rows:
        if row["verdict"] != C.MERGE:
            continue
        plan.append(
            {
                "path": row["path"],
                "verdict": C.MERGE,
                "classification": row["classification"],
                "repo_unique_line_count": row["repo_unique_line_count"],
                "live_unique_line_count": row["live_unique_line_count"],
                "repo_unique_lines": row["repo_unique_lines"],
                "live_unique_lines": row["live_unique_lines"],
                "union_preview": row["union_preview"],
                "owner_authorization_required": True,
                "pick_a_side_forbidden": True,
                "signal1_used": row["signal1_git_log_cI"]["used"],
                "signal2_live_mtime": row["signal2_live_mtime"],
            }
        )
    return plan
