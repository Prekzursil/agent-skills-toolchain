#!/usr/bin/env python3
"""Harvest a pinned, deterministic corpus of real config documents (TST-0058)."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

MIN_REAL = 50
MAX_REAL = 70
MAX_BYTES = 256_000

SKIP_NAMES = {
    "UNIT-ARTIFACT-MANIFEST.json",
    "SUBAGENT-RETURN.json",
    "WORK-UNIT-CATALOG.json",
    "package-lock.json",
    "package.json",
}
SKIP_DIR_PARTS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "runtime",
    "TST-0058",
}

HARVEST_ROOTS = (
    "command-center/schema",
    "tools",
    "command-center/phase3",
    "command-center/phase4",
    "command-center/p2-wave/probes/IMP-0385/fixtures",
    "command-center/p2-wave/probes/IMP-0394/fixtures",
    "command-center/p2-wave/probes/CNF-0157/fixtures",
    "command-center/p2-wave/probes/RES-0048/fixtures",
    "command-center/p2-wave/probes/ARC-0010",
    "command-center/p2-wave/probes/ARC-0012/fixtures/complete",
    "command-center/p2-wave/probes/IMP-0367/fixtures",
    "command-center/p2-wave/probes/CNF-0094/fixtures",
    "command-center/p2-wave/probes/CNF-0058/fixtures",
    "command-center/p2-wave/probes/ARC-0016/fixtures",
    "command-center/p2-wave/probes/IMP-0187/fixtures",
    "command-center/p2-wave/probes/CNL-0061/fixtures",
    "command-center/p2-wave/probes/IMP-0079",
)

EXTRA_FILES = (
    "command-center/CLAIM-REGISTRY.json",
    "tools/router/capability-index.json",
    "tools/release/ruleset_v1.json",
)


def _skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & SKIP_DIR_PARTS:
        return True
    if any(p.endswith(".egg-info") for p in path.parts):
        return True
    if path.name in SKIP_NAMES:
        return True
    return False


def adversarial_dir() -> Path:
    return HERE / "fixtures" / "adversarial"


def adversarial_paths() -> list[Path]:
    paths = sorted(adversarial_dir().glob("*.jsonc"))
    return paths


def _try_real(path: Path) -> bool:
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if size <= 0 or size > MAX_BYTES:
        return False
    try:
        text = path.read_text(encoding="utf-8")
        json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return True


def harvest_real(repo: Path | None = None) -> list[str]:
    """Return repo-relative POSIX paths of real, strict-JSON config documents."""
    root = repo or REPO
    found: list[str] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        if not path.is_file() or _skip(path):
            return
        try:
            rel = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return
        if rel in seen:
            return
        if not _try_real(path):
            return
        seen.add(rel)
        found.append(rel)

    for extra in EXTRA_FILES:
        add(root / extra)
    for rel_root in HARVEST_ROOTS:
        base = root / rel_root
        if not base.exists():
            continue
        if base.is_file():
            add(base)
            continue
        for path in sorted(base.rglob("*.json")):
            add(path)

    found.sort()
    if len(found) > MAX_REAL:
        found = found[:MAX_REAL]
    return found


def require_corpus(repo: Path | None = None) -> dict:
    root = repo or REPO
    real = harvest_real(root)
    adv = adversarial_paths()
    missing_adv = [p.name for p in adv if not p.is_file()]
    return {
        "real_count": len(real),
        "real_paths": real,
        "adversarial_count": len(adv),
        "adversarial_paths": [
            p.relative_to(root).as_posix() for p in adv
        ],
        "min_real": MIN_REAL,
        "min_adversarial": 10,
        "ok": len(real) >= MIN_REAL and len(adv) >= 10 and not missing_adv,
    }
