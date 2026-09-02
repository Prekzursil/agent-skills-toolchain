"""Shipped-documentation corpus for TST-0111.

Catalog-named surfaces: README, RUNBOOK, RELEASE-CHECKLIST, quick-start,
install, upgrade, rollback, workflow, plugin, and marketplace user docs.
Probe fixtures, skill-tree quickstarts, and internal audit logs are excluded
so planted controls and status tables cannot inflate or vacate the live count.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

EXPECTED_FILES = (
    "README.md",
    "README.rst",
    "QUICKSTART.md",
    "QUICK-START.md",
    "INSTALL.md",
    "UPGRADE.md",
    "ROLLBACK.md",
    "command-center/README.md",
    "command-center/RUNBOOK.md",
    "command-center/RELEASE-CHECKLIST.md",
    "docs/README.md",
    "docs/quickstart.md",
    "docs/QUICKSTART.md",
    "docs/install.md",
    "docs/INSTALL.md",
)

GLOBS = (
    "docs/workflows/**/*.md",
    "docs/mcps/**/*.md",
    "docs/skills/**/*.md",
    "plugin/**/*.md",
    "marketplace/**/*.md",
    "tools/plugin/**/*.md",
    "tools/marketplace/**/*.md",
)

SKIP_PARTS = frozenset(
    {
        "p2-wave/probes",
        "p2-wave/fixtures",
        ".git",
        "node_modules",
        "__pycache__",
    }
)

TOP_LEVEL_SKIP_PREFIXES = (
    "_LANE-",
    "SESSION-RECONCILIATION",
    "GRIND-",
)


def _skipped(rel: str) -> bool:
    norm = rel.replace("\\", "/")
    return any(part in norm for part in SKIP_PARTS)


def _skip_top_level_docs(name: str) -> bool:
    return name.startswith(TOP_LEVEL_SKIP_PREFIXES)


def list_corpus(repo: Path) -> dict[str, Any]:
    present: dict[str, Path] = {}
    expected_rows: list[dict[str, Any]] = []
    for rel in EXPECTED_FILES:
        path = repo / rel
        is_file = path.is_file()
        expected_rows.append(
            {
                "path": rel.replace("\\", "/"),
                "present": is_file,
                "role": "expected-shipped-doc",
            }
        )
        if is_file:
            present[rel.replace("\\", "/")] = path

    globbed: list[str] = []
    docs_root = repo / "docs"
    if docs_root.is_dir():
        for path in docs_root.glob("*.md"):
            if _skip_top_level_docs(path.name):
                continue
            rel = path.relative_to(repo).as_posix()
            if _skipped(rel):
                continue
            globbed.append(rel)
            present[rel] = path

    for pattern in GLOBS:
        for path in repo.glob(pattern):
            if not path.is_file():
                continue
            rel = path.relative_to(repo).as_posix()
            if _skipped(rel):
                continue
            globbed.append(rel)
            present[rel] = path

    files = sorted(present)
    return {
        "expected": expected_rows,
        "expected_present": sum(1 for r in expected_rows if r["present"]),
        "expected_absent": sum(1 for r in expected_rows if not r["present"]),
        "globbed": sorted(set(globbed)),
        "files": files,
        "paths": {rel: str(present[rel]) for rel in files},
        "computed_not_asserted": True,
        "scope": (
            "catalog-named shipped docs plus docs/*.md (audit-prefix skipped), "
            "docs/workflows, docs/mcps, docs/skills, plugin, marketplace"
        ),
    }
