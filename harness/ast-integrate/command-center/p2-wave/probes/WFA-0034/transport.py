#!/usr/bin/env python3
"""Fixture transport: API JSON is signal A; git ref HEAD is signal B.

API files are opened only through the acquisition scheduler.
Git dates are read from git objects, never from the API JSON.
"""
from __future__ import annotations

import json
from pathlib import Path

from git_refs import read_head, write_bare_head
from scheduler import AcquisitionScheduler

GIT_DATES = {
    "live-active": ("2026-08-01T12:00:00Z", "main", "live active head"),
    "archived-adopt": ("2019-03-01T00:00:00Z", "master", "archived head"),
    "stale-api": ("2026-08-20T09:00:00Z", "main", "git head newer than api"),
    "prose-archived-wrong": ("2026-06-01T00:00:00Z", "main", "not actually archived"),
}


class FixtureTransport:
    def __init__(self, here: Path):
        self.here = here
        self.api_dir = here / "fixtures" / "api"
        self.git_root = here / "fixtures" / "git-repos"
        self.scheduler = AcquisitionScheduler(tokens_per_minute=1000.0)
        self._ensure_git_repos()

    def _ensure_git_repos(self) -> None:
        for name, (iso, branch, message) in GIT_DATES.items():
            git_dir = self.git_root / name
            write_bare_head(git_dir, committer_iso=iso, message=message, branch=branch)

    def _read_api_file(self, name: str) -> dict | None:
        path = self.api_dir / f"{name}.json"
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None

    def github_repo(self, owner: str, name: str) -> dict | None:
        target = f"{owner}/{name}"
        return self.scheduler.through("github", target, self._read_api_file, name)

    def git_head(self, owner: str, name: str) -> dict | None:
        git_dir = self.git_root / name
        return read_head(git_dir)
