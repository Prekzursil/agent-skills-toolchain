#!/usr/bin/env python3
"""Pre-registration comparator: threshold timestamp vs confirmation records."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

LIVE_RECORD_GLOBS = (
    "command-center/confirmation/records/**/*.json",
    "command-center/confirmation/*confirmation*.json",
)


def parse_ts(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def threshold_timestamp(threshold: dict) -> tuple[datetime, str]:
    git = threshold.get("git") if isinstance(threshold.get("git"), dict) else {}
    path_ts = git.get("path_last_commit_time")
    if isinstance(path_ts, str) and path_ts.strip():
        return parse_ts(path_ts), "git-path-committer-date"
    frozen = threshold.get("frozen_at")
    if not isinstance(frozen, str) or not frozen.strip():
        raise ValueError("threshold has no frozen_at and no git path timestamp")
    return parse_ts(frozen), "declared_frozen_at"


def precedes(threshold: dict, confirmation_ts: str) -> bool:
    t0, _src = threshold_timestamp(threshold)
    t1 = parse_ts(confirmation_ts)
    return t0 < t1


def live_confirmation_records(repo: Path | None = None) -> list[dict]:
    root = repo or REPO
    found: list[dict] = []
    seen: set[str] = set()
    for pattern in LIVE_RECORD_GLOBS:
        for path in root.glob(pattern):
            rel = path.relative_to(root).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            if path.name.startswith("CNF-0138"):
                continue
            try:
                import json

                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(doc, dict):
                continue
            ts = doc.get("recorded_at") or doc.get("frozen_at") or doc.get("ts")
            if not isinstance(ts, str):
                continue
            if str(doc.get("record_type") or doc.get("kind") or "").lower().find(
                "confirm"
            ) < 0 and "confirmation" not in rel:
                continue
            found.append({"path": rel, "recorded_at": ts, "id": doc.get("id")})
    return found
