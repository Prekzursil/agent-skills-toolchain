"""Discover named user-documentation paths for CNF-0191.

Scope (catalog question_or_target + inputs): README, RUNBOOK, quick-start,
install, upgrade, rollback and workflow docs, RELEASE-CHECKLIST, plugin and
marketplace user documentation.

Not in scope: skill READMEs, pytest_cache, vendor trees, p2-wave probes.
A repo-wide rglob of every README.md is a detector failure (thousands of
non-user fences) and is refused here.
"""
from __future__ import annotations

from pathlib import Path

NAMED_DOCS = [
    "README.md",
    "README",
    "Readme.md",
    "command-center/RUNBOOK.md",
    "command-center/RELEASE-CHECKLIST.md",
    "docs/README.md",
    "docs/quick-start.md",
    "docs/quickstart.md",
    "docs/QUICKSTART.md",
    "docs/install.md",
    "docs/INSTALL.md",
    "docs/upgrade.md",
    "docs/rollback.md",
    "docs/RUNBOOK.md",
    "plugin/README.md",
    "plugins/README.md",
    "marketplace/README.md",
    "tools/marketplace/README.md",
    "tools/plugin/README.md",
    "platform/marketplace/README.md",
    "commands/rollback.md",
]

TOP_LEVEL_BASENAMES = {
    "readme.md",
    "runbook.md",
    "release-checklist.md",
    "quick-start.md",
    "quickstart.md",
    "install.md",
    "upgrade.md",
    "rollback.md",
}

EXTRA_DIRS = [
    "docs",
    "docs/workflows",
    "plugin",
    "plugins",
    "marketplace",
    "tools/marketplace",
    "tools/plugin",
    "platform/marketplace",
    "commands",
]


def _is_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def discover(repo: Path) -> dict:
    present: list[str] = []
    seen: set[str] = set()

    def add(rel: str) -> None:
        key = rel.replace("\\", "/")
        if key in seen:
            return
        seen.add(key)
        if _is_file(repo / key):
            present.append(key)

    for rel in NAMED_DOCS:
        add(rel)

    extra: list[str] = []
    for root_rel in EXTRA_DIRS:
        root = repo / root_rel
        if not root.is_dir():
            continue
        for path in root.iterdir():
            if not path.is_file():
                continue
            if path.name.lower() not in TOP_LEVEL_BASENAMES and not (
                root_rel.endswith("workflows") and path.suffix.lower() == ".md"
            ):
                continue
            key = path.relative_to(repo).as_posix()
            if key in seen:
                continue
            if _is_file(path):
                seen.add(key)
                extra.append(key)
                present.append(key)

    present = sorted(set(present))
    return {
        "named_checked": NAMED_DOCS,
        "present": present,
        "absent_named": [p for p in NAMED_DOCS if p not in present],
        "extra_found": extra,
    }
