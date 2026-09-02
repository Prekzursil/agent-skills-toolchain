"""28 content-differing rules-file pairs for IMP-0036.

This Linux worktree has no live ~/.claude/rules estate (re-measured each run).
Fixtures reconstruct the catalog F6 cardinality (28 content-differing) with
two-directional unique lines. They are not the owner's 2026-08-09 live bytes.

Ledger timestamps are independent of live mtime. After write, live files are
utimed into 2030 so a size/mtime heuristic would pick live; packets must not.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
REPO_ROOT = FIX / "repo"
LIVE_ROOT = FIX / "live"
LEDGER_PATH = FIX / "repo-committer-ledger.json"

# Catalog F6 class: 28 content-differing rules files.
PATHS: tuple[str, ...] = (
    "rules/common/agents.md",
    "rules/common/hooks.md",
    "rules/common/logging.md",
    "rules/common/security.md",
    "rules/common/performance.md",
    "rules/common/ci-hygiene.md",
    "rules/common/windows-shell.md",
    "rules/common/owner-ops-authorization.md",
    "rules/common/fan-out-contract.md",
    "rules/common/harness-vcs-hygiene.md",
    "rules/common/secrets.md",
    "rules/common/testing.md",
    "rules/project/owners.md",
    "rules/project/naming.md",
    "rules/project/branching.md",
    "rules/project/reviews.md",
    "rules/project/testing.md",
    "rules/project/release.md",
    "rules/project/secrets-policy.md",
    "rules/project/ci.md",
    "rules/project/docs.md",
    "rules/plugin/install.md",
    "rules/plugin/update.md",
    "rules/plugin/repair.md",
    "rules/plugin/rollback.md",
    "rules/plugin/uninstall.md",
    "rules/plugin/sync.md",
    "rules/plugin/divergence.md",
)

# Last three are LIVE-AHEAD (catalog-named live-larger class).
# Five before that are REPO-AHEAD. The first 20 are DIVERGED.
DIVERGED_N = 20
REPO_AHEAD_N = 5
assert len(PATHS) == 28
assert DIVERGED_N + REPO_AHEAD_N + 3 == 28

# Live mtime forced later than any ledger ISO so mtime-as-authorship would lie.
FUTURE_MTIME = 1893456000.0  # 2030-01-01T00:00:00Z


def host_candidates() -> list[dict]:
    rows = []
    for p in (
        REPO / "rules",
        Path.home() / ".claude",
        Path.home() / ".claude" / "rules",
        Path.home() / ".claude",
        Path.home() / ".claude" / "rules",
    ):
        rows.append(
            {
                "path": str(p),
                "exists": p.exists(),
                "is_dir": p.is_dir(),
                "file_count": sum(1 for q in p.rglob("*") if q.is_file()) if p.is_dir() else 0,
            }
        )
    return rows


def _wipe(root: Path) -> None:
    if not root.exists():
        return
    for p in sorted(root.rglob("*"), reverse=True):
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            try:
                p.rmdir()
            except OSError:
                pass


def _body(kind: str, rel: str, *, extra_live: bool, extra_repo: bool) -> tuple[str, str]:
    shared = f"shared:{rel}"
    repo_u = f"repo-unique:{rel}"
    live_u = f"live-unique:{rel}"
    repo_lines = [f"# {rel}", shared]
    live_lines = [f"# {rel}", shared]
    if kind in {"DIVERGED", "REPO-AHEAD"}:
        repo_lines.append(repo_u)
    if kind in {"DIVERGED", "LIVE-AHEAD"}:
        live_lines.append(live_u)
    if extra_live:
        live_lines.extend([f"live-pad:{rel}:{i}" for i in range(24)])
    if extra_repo:
        repo_lines.extend([f"repo-pad:{rel}:{i}" for i in range(24)])
    repo = "\n".join(repo_lines) + "\n"
    live = "\n".join(live_lines) + "\n"
    return repo, live


def kind_for(index: int) -> str:
    if index < DIVERGED_N:
        return "DIVERGED"
    if index < DIVERGED_N + REPO_AHEAD_N:
        return "REPO-AHEAD"
    return "LIVE-AHEAD"


def build_fixtures() -> dict:
    _wipe(REPO_ROOT)
    _wipe(LIVE_ROOT)
    ledger: dict[str, dict] = {}
    rows: list[dict] = []
    for i, rel in enumerate(PATHS):
        kind = kind_for(i)
        extra_live = kind == "DIVERGED" and (i % 2 == 0)
        extra_repo = kind == "DIVERGED" and (i % 2 == 1)
        if kind == "LIVE-AHEAD":
            extra_live = True
        if kind == "REPO-AHEAD":
            extra_repo = True
        repo_text, live_text = _body(
            kind, rel, extra_live=extra_live, extra_repo=extra_repo
        )
        rp = REPO_ROOT / rel
        lp = LIVE_ROOT / rel
        rp.parent.mkdir(parents=True, exist_ok=True)
        lp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(repo_text, encoding="utf-8", newline="\n")
        lp.write_text(live_text, encoding="utf-8", newline="\n")
        os.utime(lp, (FUTURE_MTIME, FUTURE_MTIME))
        iso = datetime(2025, 3, 1 + (i % 27), 12, 0, 0, tzinfo=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        ledger[rel] = {
            "committer_iso": iso,
            "commit": f"fixture-{i:02d}-{kind.lower()}",
            "derived_from_mtime": False,
        }
        rows.append(
            {
                "path": rel,
                "planted_kind": kind,
                "repo_bytes": len(repo_text.encode("utf-8")),
                "live_bytes": len(live_text.encode("utf-8")),
            }
        )
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(
        json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "count": len(PATHS),
        "paths": list(PATHS),
        "rows": rows,
        "repo_root": str(REPO_ROOT),
        "live_root": str(LIVE_ROOT),
        "ledger_path": str(LEDGER_PATH.relative_to(REPO)).replace("\\", "/"),
    }


def load_ledger() -> dict:
    return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))


def read_pair(rel: str) -> tuple[str, str, Path, Path]:
    rp = REPO_ROOT / rel
    lp = LIVE_ROOT / rel
    return rp.read_text(encoding="utf-8"), lp.read_text(encoding="utf-8"), rp, lp
