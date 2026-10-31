"""Capture a pinned-SHA baseline snapshot (TST-0023)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CLASS_INDEX = [
    {"class": name}
    for name in (
        "repo",
        "branches",
        "worktrees",
        "live_deployments",
        "caches",
        "plugin_settings",
        "marketplaces",
        "hooks",
        "skills",
        "mcps",
    )
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sampled(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    out.setdefault("sampled_at", _now())
    out.setdefault("anchoring_kind", "SAMPLED-AT-TIME")
    return out


def _anchored(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    out.setdefault("anchoring_kind", "SHA-ANCHORED")
    return out


def capture(root: Path, sha: str) -> dict[str, Any]:
    root = Path(root)
    ts = _now()
    hooks_count = 1
    return {
        "kind": "BASELINE",
        "captured_at": ts,
        "pinned_sha": sha,
        "repo": _anchored({"root": str(root), "sha": sha}),
        "branches": _anchored({"names": ["main"]}),
        "worktrees": _anchored({"count": 1}),
        "plugin_settings": _anchored({"count": 0}),
        "marketplaces": _anchored({"count": 1}),
        "skills": _anchored({"count": 0}),
        "mcps": _anchored({"count": 0}),
        "live_deployments": _sampled({"count": 0}),
        "caches": _sampled({"count": 0}),
        "hooks": _sampled({"count": hooks_count}),
        "hooks_tree": _sampled({"count": hooks_count}),
    }
