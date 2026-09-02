#!/usr/bin/env python3
"""Content-preserving two-tree merge procedure for ARC-0007.

Decisions are driven by LINE SETS after LF normalisation, never by which side is
newer or larger. Timestamps (git committer ISO vs live mtime) are provenance
signals for the human queue; they do not authorise a one-directional overwrite
when the discarded side still holds unique lines.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REFUSE = "REFUSE-ONE-DIRECTIONAL-OVERWRITE"
TAKE_REPO = "TAKE-REPO"
TAKE_LIVE = "TAKE-LIVE"
UNION_MERGE = "UNION-MERGE"
IDENTICAL = "IDENTICAL"
ADJUDICATE = "ADJUDICATE"
MISSING_LIVE = "TAKE-REPO-LIVE-ABSENT"
MISSING_REPO = "TAKE-LIVE-REPO-ABSENT"

LIVE_LARGER_NAMES = (
    "rules/common/owner-ops-authorization.md",
    "rules/common/performance.md",
    "rules/common/security.md",
)

TARGET_MAP = (
    ("rules/", "config/rules/"),
    ("skills/", "config/skills/"),
    ("hooks/_dispatch/", "config/hooks/"),
)


def lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def lines_of(text: str) -> list[str]:
    body = lf(text)
    if body == "":
        return []
    parts = body.split("\n")
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def line_set(text: str) -> set[str]:
    return set(lines_of(text))


def sha256_text(text: str) -> str:
    return hashlib.sha256(lf(text).encode("utf-8")).hexdigest()


def iso_mtime(path: Path) -> str | None:
    if not path.is_file():
        return None
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_committer_iso(repo_root: Path, rel: str) -> tuple[int, str]:
    """Signal 1: git log -1 --format=%cI. Returns (exit_code, stdout_or_reason)."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "log", "-1", "--format=%cI", "--", rel],
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


def classify(repo_text: str | None, live_text: str | None) -> str:
    if repo_text is None and live_text is None:
        return "ABSENT-BOTH"
    if repo_text is None:
        return "LIVE-ONLY"
    if live_text is None:
        return "REPO-ONLY"
    rs, ls = line_set(repo_text), line_set(live_text)
    if lf(repo_text) == lf(live_text):
        return "BYTE-IDENTICAL-LF"
    if rs == ls:
        return "EOL-ONLY"
    if rs < ls:
        return "LIVE-SUPERSET"
    if ls < rs:
        return "REPO-SUPERSET"
    if rs & ls and (rs - ls) and (ls - rs):
        return "BOTH-UNIQUE"
    if not (rs & ls) and rs and ls:
        return "BOTH-UNIQUE-DISJOINT"
    return "BOTH-UNIQUE"


def decide(classification: str) -> str:
    return {
        "BYTE-IDENTICAL-LF": IDENTICAL,
        "EOL-ONLY": IDENTICAL,
        "REPO-ONLY": MISSING_LIVE,
        "LIVE-ONLY": MISSING_REPO,
        "LIVE-SUPERSET": TAKE_LIVE,
        "REPO-SUPERSET": TAKE_REPO,
        "BOTH-UNIQUE": ADJUDICATE,
        "BOTH-UNIQUE-DISJOINT": ADJUDICATE,
        "ABSENT-BOTH": REFUSE,
    }.get(classification, ADJUDICATE)


def union_preview(repo_text: str, live_text: str) -> str:
    """Keep repo order; append live-unique lines in live order. Never drops a unique line."""
    repo_lines = lines_of(repo_text)
    live_lines = lines_of(live_text)
    seen = set(repo_lines)
    out = list(repo_lines)
    for line in live_lines:
        if line not in seen:
            out.append(line)
            seen.add(line)
    return "\n".join(out) + ("\n" if out else "")


def unique_lines_preserved(repo_text: str | None, live_text: str | None, migrated: str) -> bool:
    want: set[str] = set()
    if repo_text is not None:
        want |= line_set(repo_text)
    if live_text is not None:
        want |= line_set(live_text)
    have = line_set(migrated)
    return want <= have


@dataclass
class ApplyResult:
    ok: bool
    decision: str
    migrated: str | None
    refused: bool
    reason: str
    classification: str


def apply_merge(
    repo_text: str | None,
    live_text: str | None,
    *,
    requested: str | None = None,
) -> ApplyResult:
    classification = classify(repo_text, live_text)
    automatic = decide(classification)

    if requested == TAKE_REPO and classification in {
        "LIVE-SUPERSET",
        "BOTH-UNIQUE",
        "BOTH-UNIQUE-DISJOINT",
        "LIVE-ONLY",
    }:
        return ApplyResult(
            ok=False,
            decision=REFUSE,
            migrated=None,
            refused=True,
            reason=(
                "one-directional overwrite refused: live side holds unique line(s) "
                f"(classification={classification})"
            ),
            classification=classification,
        )
    if requested == TAKE_LIVE and classification in {
        "REPO-SUPERSET",
        "BOTH-UNIQUE",
        "BOTH-UNIQUE-DISJOINT",
        "REPO-ONLY",
    }:
        return ApplyResult(
            ok=False,
            decision=REFUSE,
            migrated=None,
            refused=True,
            reason=(
                "one-directional overwrite refused: repo side holds unique line(s) "
                f"(classification={classification})"
            ),
            classification=classification,
        )

    action = requested or automatic
    if action == REFUSE:
        return ApplyResult(
            False, REFUSE, None, True, "merge refused", classification
        )
    if action == ADJUDICATE:
        preview = union_preview(repo_text or "", live_text or "")
        return ApplyResult(
            ok=True,
            decision=ADJUDICATE,
            migrated=preview,
            refused=False,
            reason="neither side is a superset; queued for human adjudication; preview is union",
            classification=classification,
        )
    if action in {IDENTICAL, TAKE_REPO, MISSING_LIVE}:
        text = repo_text if repo_text is not None else ""
        return ApplyResult(True, action, lf(text) if text.endswith("\n") or text == "" else lf(text) + "\n" if text else "", False, "take repo", classification)
    if action in {TAKE_LIVE, MISSING_REPO}:
        text = live_text if live_text is not None else ""
        return ApplyResult(True, action, lf(text) if text.endswith("\n") or text == "" else lf(text) + "\n" if text else "", False, "take live", classification)
    if action == UNION_MERGE:
        preview = union_preview(repo_text or "", live_text or "")
        return ApplyResult(True, UNION_MERGE, preview, False, "union merge", classification)
    return ApplyResult(False, REFUSE, None, True, f"unknown action {action}", classification)


def target_rel(source_rel: str) -> str:
    for src, dst in TARGET_MAP:
        if source_rel.startswith(src):
            return dst + source_rel[len(src) :]
    return "config/unmapped/" + source_rel


def read_if(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def walk_rel(root: Path) -> set[str]:
    out: set[str] = set()
    if not root.is_dir():
        return out
    for p in root.rglob("*"):
        if p.is_file():
            out.add(p.relative_to(root).as_posix())
    return out


def snapshot_tree(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for rel in sorted(walk_rel(src)):
        s = src / rel
        d = dest / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_bytes(s.read_bytes())


def restore_tree(snapshot: Path, dest: Path) -> None:
    if dest.exists():
        for p in sorted(dest.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                try:
                    p.rmdir()
                except OSError:
                    pass
    snapshot_tree(snapshot, dest)


@dataclass
class FileRecord:
    path: str
    classification: str
    decision: str
    repo_exists: bool
    live_exists: bool
    repo_bytes: int
    live_bytes: int
    repo_sha256: str | None
    live_sha256: str | None
    repo_committer_iso: str | None
    git_log_exit: int
    git_log_raw: str
    live_mtime_iso: str | None
    repo_unique_line_count: int
    live_unique_line_count: int
    shared_line_count: int
    unique_lines_preserved: bool
    live_larger: bool
    target_path: str
    migrated_sha256: str | None
    refused_overwrite: bool
    reason: str
    ledger_committer_iso: str | None = None


def measure_file(
    rel: str,
    repo_root: Path,
    live_root: Path,
    ledger: dict[str, str],
    migrated_root: Path | None = None,
) -> FileRecord:
    rp, lp = repo_root / rel, live_root / rel
    repo_text, live_text = read_if(rp), read_if(lp)
    git_rc, git_raw = git_committer_iso(repo_root, rel)
    git_iso = git_raw if git_rc == 0 and git_raw and git_raw[:1].isdigit() else None
    ledger_iso = ledger.get(rel)
    result = apply_merge(repo_text, live_text)
    migrated = result.migrated or ""
    rs = line_set(repo_text or "")
    ls = line_set(live_text or "")
    preserved = (
        unique_lines_preserved(repo_text, live_text, migrated)
        if result.migrated is not None
        else False
    )
    live_larger = bool(
        repo_text is not None
        and live_text is not None
        and len(live_text.encode("utf-8")) > len(repo_text.encode("utf-8"))
    )
    if migrated_root is not None and result.migrated is not None:
        tp = migrated_root / target_rel(rel)
        tp.parent.mkdir(parents=True, exist_ok=True)
        tp.write_text(result.migrated, encoding="utf-8", newline="\n")
    return FileRecord(
        path=rel,
        classification=classify(repo_text, live_text),
        decision=result.decision,
        repo_exists=repo_text is not None,
        live_exists=live_text is not None,
        repo_bytes=len(repo_text.encode("utf-8")) if repo_text is not None else 0,
        live_bytes=len(live_text.encode("utf-8")) if live_text is not None else 0,
        repo_sha256=sha256_text(repo_text) if repo_text is not None else None,
        live_sha256=sha256_text(live_text) if live_text is not None else None,
        repo_committer_iso=git_iso,
        git_log_exit=git_rc,
        git_log_raw=git_raw[:500],
        live_mtime_iso=iso_mtime(lp),
        repo_unique_line_count=len(rs - ls),
        live_unique_line_count=len(ls - rs),
        shared_line_count=len(rs & ls),
        unique_lines_preserved=preserved,
        live_larger=live_larger,
        target_path=target_rel(rel),
        migrated_sha256=sha256_text(migrated) if result.migrated is not None else None,
        refused_overwrite=result.refused,
        reason=result.reason,
        ledger_committer_iso=ledger_iso,
    )


def record_to_dict(rec: FileRecord) -> dict[str, Any]:
    return {
        "path": rec.path,
        "target_path": rec.target_path,
        "classification": rec.classification,
        "decision": rec.decision,
        "repo_exists": rec.repo_exists,
        "live_exists": rec.live_exists,
        "repo_bytes": rec.repo_bytes,
        "live_bytes": rec.live_bytes,
        "live_larger": rec.live_larger,
        "repo_sha256": rec.repo_sha256,
        "live_sha256": rec.live_sha256,
        "signal1_git_log_cI": {
            "command": f"git log -1 --format=%cI -- {rec.path}",
            "exit_code": rec.git_log_exit,
            "raw": rec.git_log_raw,
            "iso": rec.repo_committer_iso,
            "independent_ledger_iso": rec.ledger_committer_iso,
            "used": rec.repo_committer_iso or rec.ledger_committer_iso,
            "note": (
                "git log is signal 1 when a repo is present; this worktree has no "
                ".git at the estate root, so the fixture ledger ISO is the independent "
                "repo-side timestamp analogue (not derived from live mtime)."
            ),
        },
        "signal2_live_mtime_plus_diff": {
            "live_mtime_iso": rec.live_mtime_iso,
            "repo_unique_line_count": rec.repo_unique_line_count,
            "live_unique_line_count": rec.live_unique_line_count,
            "shared_line_count": rec.shared_line_count,
        },
        "unique_lines_preserved": rec.unique_lines_preserved,
        "migrated_sha256": rec.migrated_sha256,
        "refused_overwrite": rec.refused_overwrite,
        "reason": rec.reason,
    }


def negative_control_refuse_overwrite(live_unique_line: str) -> dict[str, Any]:
    repo = "shared line alpha\nshared line beta\nrepo-only line\n"
    live = "shared line alpha\nshared line beta\n" + live_unique_line + "\n"
    forced = apply_merge(repo, live, requested=TAKE_REPO)
    auto = apply_merge(repo, live)
    preserved_auto = unique_lines_preserved(repo, live, auto.migrated or "")
    return {
        "id": "negative-control-refuse-one-directional-overwrite",
        "live_unique_line": live_unique_line,
        "classification": forced.classification,
        "requested": TAKE_REPO,
        "refused": forced.refused,
        "decision": forced.decision,
        "reason": forced.reason,
        "automatic_decision": auto.decision,
        "automatic_preserves_union": preserved_auto,
        "pass": forced.refused is True and live_unique_line in (auto.migrated or ""),
    }
