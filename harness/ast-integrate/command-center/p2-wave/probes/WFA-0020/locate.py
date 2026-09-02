"""Locate live catalog inputs. Missing paths become recall_limit, not invented runs."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"

REGISTRY_NAME = "08-WORKFLOW-CANDIDATE-REGISTRY.json"

CATALOG_LIVE_GLOBS = [
    "~/.claude/projects/<proj>/<session>/subagents/agent-*.jsonl",
    "~/.claude/event-ledger/",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
]


def _exists_file(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def _exists_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def registry_candidates() -> list[Path]:
    home = Path.home()
    env = os.environ.get("WFA0020_REGISTRY")
    out: list[Path] = []
    if env:
        out.append(Path(env))
    out.extend(
        [
            Path("C:/Users/Prekzursil/.claude/harness-restore-20260806") / REGISTRY_NAME,
            Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806") / REGISTRY_NAME,
            Path("/c/Users/Prekzursil/.claude/harness-restore-20260806") / REGISTRY_NAME,
            home / ".claude/harness-restore-20260806" / REGISTRY_NAME,
            Path("/root/.claude/harness-restore-20260806") / REGISTRY_NAME,
            REPO / "command-center" / REGISTRY_NAME,
        ]
    )
    return out


def transcript_roots() -> list[Path]:
    env = os.environ.get("WFA0020_TRANSCRIPTS")
    home = Path.home()
    out: list[Path] = []
    if env:
        out.append(Path(env))
    out.extend(
        [
            home / ".claude/projects",
            Path("/root/.claude/projects"),
            home / ".claude/projects",
        ]
    )
    return out


def ledger_roots() -> list[Path]:
    env = os.environ.get("WFA0020_LEDGER")
    home = Path.home()
    out: list[Path] = []
    if env:
        out.append(Path(env))
    out.extend(
        [
            home / ".claude/event-ledger",
            Path("/root/.claude/event-ledger"),
        ]
    )
    return out


def first_existing_file(paths: list[Path]) -> Path | None:
    for p in paths:
        if _exists_file(p):
            return p
    return None


def first_existing_dir(paths: list[Path]) -> Path | None:
    for p in paths:
        if _exists_dir(p):
            return p
    return None


def list_agent_jsonl(root: Path | None) -> list[Path]:
    if root is None or not _exists_dir(root):
        return []
    return sorted(root.rglob("agent-*.jsonl"))


def unread_catalog_inputs(found: dict[str, Any]) -> list[dict[str, Any]]:
    unread: list[dict[str, Any]] = []
    for label, present in (
        ("live:~/.claude/projects/<proj>/<session>/subagents/agent-*.jsonl", found.get("live_transcript_count", 0) == 0),
        ("live:~/.claude/event-ledger/", not found.get("live_ledger_present")),
        (
            "C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
            not found.get("live_registry_present"),
        ),
    ):
        if present:
            unread.append(
                {
                    "input": label,
                    "reason": "path-absent-on-this-worktree",
                    "invented": False,
                }
            )
    return unread


def inspect_live() -> dict[str, Any]:
    reg = first_existing_file(registry_candidates())
    tx_root = first_existing_dir(transcript_roots())
    led_root = first_existing_dir(ledger_roots())
    jsonl = list_agent_jsonl(tx_root)
    ledger_files: list[str] = []
    if led_root is not None:
        ledger_files = [p.as_posix() for p in sorted(led_root.rglob("*")) if p.is_file()]
    found = {
        "live_registry_path": None if reg is None else str(reg),
        "live_registry_present": reg is not None,
        "live_transcript_root": None if tx_root is None else str(tx_root),
        "live_transcript_count": len(jsonl),
        "live_transcript_sample": [str(p) for p in jsonl[:8]],
        "live_ledger_root": None if led_root is None else str(led_root),
        "live_ledger_present": bool(ledger_files),
        "live_ledger_file_count": len(ledger_files),
        "fixture_dir": str(FIXTURES),
    }
    found["unread"] = unread_catalog_inputs(found)
    found["catalog_live_globs"] = CATALOG_LIVE_GLOBS
    return found
