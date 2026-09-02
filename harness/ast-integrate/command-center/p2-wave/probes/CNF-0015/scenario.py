#!/usr/bin/env python3
"""Both-states fixtures and live-tree lookup for CNF-0015.

Catalog numbers this fixture reconstructs (when live docs are absent):
  family M = 33 ids, architecture mechanisms = 38 ids,
  pre-fix shared bare M-NN = 31, post-fix shared = 0.
  17-DECISION-LOG.md: ~44 KiB, line 175 present-tense collision, zero MECH.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"

OPTION_NAMES = (
    "07-OPTION-UNIVERSE.md",
    "07-OPTION-UNIVERSE.md",
    "07-OPTION-UNIVERSE.json",
)
ARCH_NAMES = (
    "13-ARCHITECTURE-CANDIDATES.md",
    "13-ARCHITECTURE-CANDIDATES.md",
)
LOG_NAMES = (
    "17-DECISION-LOG.md",
    "17-DECISION-LOG.md",
)


def family_m_block() -> str:
    cards = []
    for n in range(1, 34):
        cards.append(f"### M-{n:02d} Option card {n:02d}\n\nid: M-{n:02d}\n")
    return "\n".join(cards)


def option_universe() -> str:
    return (
        "# 07-OPTION-UNIVERSE\n\n"
        "## Family L\n\n### L-01 Unrelated family (must not enter family M)\n\n"
        "## Family M\n\n"
        f"{family_m_block()}\n"
        "## Family N\n\n### N-01 Unrelated family\n"
    )


def architecture_pre() -> str:
    """Pre-fix: 38 bare M-NN mechanism cards, 31 overlapping family M."""
    parts = ["# 13-ARCHITECTURE-CANDIDATES\n\n## Mechanisms\n"]
    for n in range(1, 32):
        parts.append(f"### M-{n:02d} Mechanism {n:02d}\n\nid: M-{n:02d}\n")
    for n in range(34, 41):
        parts.append(f"### M-{n:02d} Mechanism {n:02d}\n\nid: M-{n:02d}\n")
    parts.append("\n## Architectures\n\nA1-A11 tournament roster (not M-NN ids).\n")
    return "\n".join(parts)


def architecture_post() -> str:
    """Post-fix: same 38 cards re-prefixed to MECH-NN. Zero bare M-NN decls."""
    parts = ["# 13-ARCHITECTURE-CANDIDATES\n\n## Mechanisms\n"]
    for n in range(1, 32):
        parts.append(f"### MECH-{n:02d} Mechanism {n:02d}\n\nid: MECH-{n:02d}\n")
    for n in range(34, 41):
        parts.append(f"### MECH-{n:02d} Mechanism {n:02d}\n\nid: MECH-{n:02d}\n")
    parts.append(
        "\n## Architectures\n\n"
        "Re-prefix applied 2026-08-07 (107 substitutions). "
        "Bare M-NN mechanism ids are retired. The letters M-NN in this sentence "
        "are not identifiers.\n"
    )
    return "\n".join(parts)


def architecture_planted_collision() -> str:
    """Post-fix tree plus one planted bare M-07 mechanism inside Mechanisms."""
    post = architecture_post()
    marker = "\n## Architectures\n"
    planted = "\n### M-07 Planted collision card\n\nid: M-07\n"
    if marker in post:
        return post.replace(marker, planted + marker, 1)
    return post + planted


def decision_log_stale() -> str:
    pad = "x" * 80
    lines = ["# 17-DECISION-LOG"]
    while len(lines) < 174:
        lines.append(f"{len(lines)+1:04d} {pad}")
    lines.append(
        "The 31-way option-id collision between family M and architecture "
        "mechanisms is a live blocker. Queued as P2-09."
    )
    while len(lines) < 520:
        lines.append(f"{len(lines)+1:04d} {pad}")
    return "\n".join(lines) + "\n"


def decision_log_reconciled() -> str:
    text = decision_log_stale()
    return text.replace(
        "The 31-way option-id collision between family M and architecture "
        "mechanisms is a live blocker. Queued as P2-09.",
        "The 31-way option-id collision was resolved by re-prefixing "
        "mechanisms to MECH-NN on 2026-08-07. Closed. No longer queued.",
    )


def write_fixtures() -> dict[str, Path]:
    FIX.mkdir(parents=True, exist_ok=True)
    files = {
        "option": FIX / "07-OPTION-UNIVERSE.md",
        "arch_pre": FIX / "13-ARCHITECTURE-CANDIDATES.pre.md",
        "arch_post": FIX / "13-ARCHITECTURE-CANDIDATES.post.md",
        "arch_planted": FIX / "13-ARCHITECTURE-CANDIDATES.planted.md",
        "log_stale": FIX / "17-DECISION-LOG.stale.md",
        "log_reconciled": FIX / "17-DECISION-LOG.reconciled.md",
    }
    files["option"].write_text(option_universe(), encoding="utf-8")
    files["arch_pre"].write_text(architecture_pre(), encoding="utf-8")
    files["arch_post"].write_text(architecture_post(), encoding="utf-8")
    files["arch_planted"].write_text(architecture_planted_collision(), encoding="utf-8")
    files["log_stale"].write_text(decision_log_stale(), encoding="utf-8")
    files["log_reconciled"].write_text(decision_log_reconciled(), encoding="utf-8")
    return files


def _try_git_show(rel: str) -> str | None:
    git = REPO / ".git"
    if not git.exists():
        return None
    try:
        r = subprocess.run(
            ["git", "cat-file", "-p", f"HEAD:{rel}"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return r.stdout or None


def find_live(names: tuple[str, ...]) -> dict:
    """Locate a document in the worktree or via git cat-file (read-only)."""
    searched = []
    for name in names:
        candidates = [
            REPO / name,
            REPO / "docs" / name,
            REPO / "command-center" / name,
            REPO / "command-center" / "docs" / name,
        ]
        for p in candidates:
            searched.append(str(p))
            if p.is_file() and p.stat().st_size > 0:
                return {
                    "present": True,
                    "path": str(p.relative_to(REPO)),
                    "source": "worktree",
                    "bytes": p.stat().st_size,
                }
        blob = _try_git_show(name)
        if blob:
            return {
                "present": True,
                "path": name,
                "source": "git-cat-file HEAD",
                "bytes": len(blob.encode("utf-8")),
            }
    return {"present": False, "path": None, "source": None, "searched": searched[:8]}


def live_census() -> dict:
    return {
        "option_universe": find_live(OPTION_NAMES),
        "architecture_candidates": find_live(ARCH_NAMES),
        "decision_log": find_live(LOG_NAMES),
        "git_present": (REPO / ".git").exists(),
    }


write_fixtures = write_fixtures
live_census = live_census
