"""Planted two-directional trees for IMP-0025 probes.

Host `rules/` and `~/.claude/rules` are searched. On this Linux worktree they
are typically absent; probes then use these fixtures and say so.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"

IDENTICAL = [
    "common/agents.md",
    "common/hooks.md",
    "common/security.md",
    "common/performance.md",
    "common/logging.md",
]
EOL_ONLY = [
    "common/ci-hygiene.md",
    "common/windows-shell.md",
    "project/naming.md",
    "project/reviews.md",
]
REPO_AHEAD = [
    "project/testing.md",
    "project/release.md",
    "project/branching.md",
    "project/owners.md",
    "project/secrets-policy.md",
    "common/fan-out-contract.md",
]
LIVE_AHEAD = [
    "live-only-edits/session-notes.md",
    "live-only-edits/local-allowlist.md",
    "live-only-edits/debug-flags.md",
]
DIVERGED = [
    "common/owner-ops-authorization.md",
    "common/reviews-extra.md",
    "project/divergent-policy.md",
    "common/both-unique.md",
]
REPO_ONLY = ["repo-only/unpublished-rule.md"]
LIVE_ONLY = ["live-only/uncommitted-rule.md"]

REVIEWER_SAMPLE = [
    IDENTICAL[0],
    IDENTICAL[1],
    EOL_ONLY[0],
    EOL_ONLY[1],
    REPO_AHEAD[0],
    REPO_AHEAD[1],
    LIVE_AHEAD[0],
    LIVE_AHEAD[1],
    DIVERGED[0],
    DIVERGED[1],
]


def _write(path: Path, body: str, newline: str = "\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body.replace("\n", newline).encode("utf-8"))


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


def host_candidates() -> list[dict]:
    rows = []
    for p in (
        REPO / "rules",
        Path.home() / ".claude" / "rules",
        Path.home() / ".claude" / "rules",
    ):
        rows.append(
            {
                "path": str(p),
                "exists": p.exists(),
                "is_dir": p.is_dir(),
                "file_count": sum(1 for q in p.rglob("*") if q.is_file())
                if p.is_dir()
                else 0,
            }
        )
    return rows


def build_fixtures() -> dict:
    repo = FIX / "estate" / "repo"
    live = FIX / "estate" / "live"
    _wipe(repo)
    _wipe(live)

    for rel in IDENTICAL:
        body = f"# {rel}\nidentical body for both trees\n"
        _write(repo / rel, body)
        _write(live / rel, body)
    for rel in EOL_ONLY:
        body = f"# {rel}\nsame logical content, eol differs\n"
        _write(repo / rel, body, newline="\n")
        _write(live / rel, body, newline="\r\n")
    for i, rel in enumerate(REPO_AHEAD):
        live_b = f"# {rel}\nshared prefix\n"
        repo_b = live_b + f"repo extra line {i}\n"
        _write(live / rel, live_b)
        _write(repo / rel, repo_b)
    for i, rel in enumerate(LIVE_AHEAD):
        repo_b = f"# {rel}\nshared prefix\n"
        live_b = repo_b + f"live extra line {i}\n"
        _write(repo / rel, repo_b)
        _write(live / rel, live_b)
    for i, rel in enumerate(DIVERGED):
        shared = f"# {rel}\nshared prefix\n"
        _write(repo / rel, shared + f"repo unique {i}\n")
        _write(live / rel, shared + f"live unique {i}\n")
    for rel in REPO_ONLY:
        _write(repo / rel, f"# {rel}\nrepo only\n")
    for rel in LIVE_ONLY:
        _write(live / rel, f"# {rel}\nlive only\n")

    return {
        "repo_root": str(repo),
        "live_root": str(live),
        "expected": {
            "IDENTICAL": list(IDENTICAL),
            "IDENTICAL-MODULO-EOL": list(EOL_ONLY),
            "REPO-AHEAD": list(REPO_AHEAD) + list(REPO_ONLY),
            "LIVE-AHEAD": list(LIVE_AHEAD) + list(LIVE_ONLY),
            "DIVERGED": list(DIVERGED),
        },
        "reviewer_sample": list(REVIEWER_SAMPLE),
        "cited_historical_5_of_88": False,
    }


def estate_roots() -> tuple[Path, Path]:
    return FIX / "estate" / "repo", FIX / "estate" / "live"
