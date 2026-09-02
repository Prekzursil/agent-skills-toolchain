#!/usr/bin/env python3
"""Deterministic Claude + Codex estate for IMP-0407 probes and emit."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from discover import encode_claude_project, to_iso

CLAUDE_LIVE_ID = "11111111-1111-4111-8111-111111111111"
CLAUDE_STALE_ID = "22222222-2222-4222-8222-222222222222"
CODEX_LIVE_ID = "sess-codex-live"
CODEX_ROLL_UUID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"

CLAUDE_LIVE_CWD = "/work/claude-live"
CLAUDE_STALE_CWD = "/work/claude-stale"
CODEX_LIVE_CWD = "/work/codex-live"
ORPHAN_CWD = "/tmp/claude-orphan"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_estate(root: Path, now: datetime | None = None) -> dict:
    """Plant two Claude sessions, one Codex session, and a process snapshot.

    Timeline relative to probe `now`:
      * claude-live and codex-live started 60s earlier (known-present)
      * claude-stale started 3600s earlier, no process (ON_DISK_WITHOUT_PROCESS)
      * orphan claude process, no disk row (PROCESS_WITHOUT_ON_DISK)
      * self-matching probe process at `now` (must be excluded)
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    t_live = now - timedelta(seconds=60)
    t_stale = now - timedelta(seconds=3600)
    t_orphan = now - timedelta(seconds=30)
    root = Path(root)
    if root.exists():
        for p in sorted(root.rglob("*"), reverse=True):
            if p.is_file() or p.is_symlink():
                p.unlink()
            elif p.is_dir():
                try:
                    p.rmdir()
                except OSError:
                    pass
    root.mkdir(parents=True, exist_ok=True)

    claude_home = root / "claude_home"
    codex_home = root / "codex_home"

    live_proj = claude_home / "projects" / encode_claude_project(CLAUDE_LIVE_CWD)
    stale_proj = claude_home / "projects" / encode_claude_project(CLAUDE_STALE_CWD)
    live_jsonl = {
        "parentUuid": None,
        "type": "user",
        "cwd": CLAUDE_LIVE_CWD,
        "sessionId": CLAUDE_LIVE_ID,
        "timestamp": to_iso(t_live),
        "message": {"role": "user", "content": "known-present claude session"},
    }
    stale_jsonl = {
        "parentUuid": None,
        "type": "user",
        "cwd": CLAUDE_STALE_CWD,
        "sessionId": CLAUDE_STALE_ID,
        "timestamp": to_iso(t_stale),
        "message": {"role": "user", "content": "finished claude session"},
    }
    _write(live_proj / f"{CLAUDE_LIVE_ID}.jsonl", json.dumps(live_jsonl) + "\n")
    _write(stale_proj / f"{CLAUDE_STALE_ID}.jsonl", json.dumps(stale_jsonl) + "\n")
    nested = live_proj / "subagents" / "agent-should-not-count.jsonl"
    _write(
        nested,
        json.dumps(
            {
                "sessionId": "nested-subagent-not-a-session",
                "cwd": CLAUDE_LIVE_CWD,
                "timestamp": to_iso(t_live),
                "type": "assistant",
            }
        )
        + "\n",
    )

    thread = {
        "id": CODEX_LIVE_ID,
        "cwd": CODEX_LIVE_CWD,
        "cwd_path": CODEX_LIVE_CWD,
        "created_at": to_iso(t_live),
        "updated_at": to_iso(now),
    }
    _write(codex_home / "threads" / f"{CODEX_LIVE_ID}.json", json.dumps(thread, indent=2))
    rollout = {
        "type": "session_meta",
        "payload": {
            "id": CODEX_LIVE_ID,
            "cwd": CODEX_LIVE_CWD,
            "timestamp": to_iso(t_live),
        },
    }
    roll_name = f"rollout-{t_live.strftime('%Y-%m-%dT%H-%M-%S')}-{CODEX_ROLL_UUID}.jsonl"
    _write(
        codex_home / "sessions" / t_live.strftime("%Y") / t_live.strftime("%m") / t_live.strftime("%d") / roll_name,
        json.dumps(rollout) + "\n",
    )

    snapshot = [
        {
            "pid": 4242,
            "cmdline": f"claude --resume {CLAUDE_LIVE_ID}",
            "cwd": CLAUDE_LIVE_CWD,
            "start_time": to_iso(t_live),
            "vendor": "claude",
        },
        {
            "pid": 4243,
            "cmdline": f"codex resume {CODEX_LIVE_ID}",
            "cwd": CODEX_LIVE_CWD,
            "start_time": to_iso(t_live),
            "vendor": "codex",
        },
        {
            "pid": 4300,
            "cmdline": "claude --orphan-no-disk",
            "cwd": ORPHAN_CWD,
            "start_time": to_iso(t_orphan),
            "vendor": "claude",
        },
        {
            "pid": 9999,
            "CommandLine": "python3 /tmp/discover-probe.py --search claude --dump",
            "ProcessId": 9999,
            "CreationDate": to_iso(now),
            "cwd": "/tmp",
        },
    ]
    snap_path = root / "process_snapshot.json"
    _write(snap_path, json.dumps(snapshot, indent=2) + "\n")

    return {
        "root": str(root),
        "claude_home": str(claude_home),
        "codex_home": str(codex_home),
        "snapshot_path": str(snap_path),
        "snapshot": snapshot,
        "now": to_iso(now),
        "known_present": {
            "claude": {
                "session_id": CLAUDE_LIVE_ID,
                "cwd": CLAUDE_LIVE_CWD,
                "start_time": to_iso(t_live),
                "started_seconds_before_probe": 60,
            },
            "codex": {
                "session_id": CODEX_LIVE_ID,
                "cwd": CODEX_LIVE_CWD,
                "start_time": to_iso(t_live),
                "started_seconds_before_probe": 60,
            },
        },
        "stale_claude": CLAUDE_STALE_ID,
        "self_pid": 9999,
        "orphan_pid": 4300,
        "expected_on_disk": {"claude": 2, "codex": 1, "total": 3},
        "expected_process_after_exclusion": 3,
        "expected_self_excluded": 1,
        "expected_disagreement_kinds": [
            "ON_DISK_WITHOUT_PROCESS",
            "PROCESS_WITHOUT_ON_DISK",
        ],
    }
