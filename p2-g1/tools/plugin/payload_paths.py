"""Deny-by-default payload path expansion (AUD-0088).

load_allowlist reads tools/plugin/payload-allowlist.json and exposes
deny_by_default. expand_payload_paths uses matcher A (slash-segment regex).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

from .payload_allowlist import (  # noqa: E402
    expand,
    include_globs,
    listed_paths,
    load_allowlist as _load_file,
)

ALLOWLIST_REL = "tools/plugin/payload-allowlist.json"


def _as_repo(repo: Path | None) -> Path:
    if repo is None:
        return REPO
    return Path(repo)


def load_allowlist(repo: Path | None = None) -> dict[str, Any]:
    root = _as_repo(repo)
    src = root / ALLOWLIST_REL
    if not src.is_file():
        src = HERE / "payload-allowlist.json"
    data = _load_file(src)
    policy = str(data.get("policy") or "").replace("_", "-").lower()
    data["deny_by_default"] = bool(
        data.get("deny_by_default") is True or policy in {"deny-by-default", "deny"}
    )
    data["include"] = include_globs(data)
    excludes: list[str] = []
    for row in data.get("exclude") or []:
        if isinstance(row, str):
            excludes.append(row)
        elif isinstance(row, dict) and row.get("glob"):
            excludes.append(str(row["glob"]))
    for _cls, globs in (data.get("forbidden_classes") or {}).items():
        if isinstance(globs, list):
            excludes.extend(str(g) for g in globs)
    data["exclude"] = excludes
    return data


def expand_payload_paths(repo: Path | None = None) -> list[str]:
    root = _as_repo(repo)
    allow = load_allowlist(root)
    _src, census = listed_paths(root)
    chosen = expand(census, allow, matcher="a")
    return list(chosen)


__all__ = ["expand_payload_paths", "load_allowlist"]
