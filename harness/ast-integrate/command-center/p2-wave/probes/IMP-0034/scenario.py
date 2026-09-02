"""Host-or-fixture pair for IMP-0034.

This Linux worktree typically has no repo `rules/` and no `~/.claude/rules`.
When both host trees are present they are classified. Otherwise a planted
estate encodes all five classes plus the three catalog-named live-larger files.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE_REPO = HERE / "fixtures" / "estate" / "repo" / "rules"
FIXTURE_LIVE = HERE / "fixtures" / "estate" / "live" / "rules"

NAMED_LIVE_LARGER = (
    "common/owner-ops-authorization.md",
    "common/performance.md",
    "common/security.md",
)

SHARED = "# shared prefix\ncommon line\n"


def host_candidates() -> list[dict]:
    rows = []
    for label, path in (
        ("repo-rules", REPO / "rules"),
        ("home-claude-rules", Path.home() / ".claude" / "rules"),
        ("root-claude-rules", Path("/root/.claude/rules")),
    ):
        n = sum(1 for p in path.rglob("*") if p.is_file()) if path.is_dir() else 0
        rows.append(
            {
                "label": label,
                "path": str(path),
                "exists": path.exists(),
                "is_dir": path.is_dir(),
                "file_count": n,
            }
        )
    return rows


def host_pair() -> tuple[Path, Path] | None:
    repo = REPO / "rules"
    live = Path.home() / ".claude" / "rules"
    if repo.is_dir() and live.is_dir():
        repo_n = sum(1 for p in repo.rglob("*") if p.is_file())
        live_n = sum(1 for p in live.rglob("*") if p.is_file())
        if repo_n > 0 and live_n > 0:
            return repo, live
    return None


def _write(path: Path, body: str | bytes, *, newline: str | None = "\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(body, bytes):
        path.write_bytes(body)
        return
    if newline is None:
        path.write_bytes(body.encode("utf-8"))
        return
    path.write_text(body, encoding="utf-8", newline=newline)


def build_estate_fixtures() -> dict:
    """Plant all five classes and the three named live-larger files."""
    for root in (FIXTURE_REPO, FIXTURE_LIVE):
        if root.exists():
            for p in root.rglob("*"):
                if p.is_file():
                    p.unlink()

    # IDENTICAL
    for rel in (
        "common/agents.md",
        "common/logging.md",
        "project/owners.md",
        "project/naming.md",
        "project/branching.md",
    ):
        _write(FIXTURE_REPO / rel, f"# {rel}\nidentical on both sides\n")
        _write(FIXTURE_LIVE / rel, f"# {rel}\nidentical on both sides\n")

    # IDENTICAL-MODULO-EOL (LF repo, CRLF live)
    for rel in ("common/hooks.md", "project/reviews.md", "project/testing.md"):
        body = f"# {rel}\nsame logical bytes, different EOL\n"
        _write(FIXTURE_REPO / rel, body, newline="\n")
        _write(FIXTURE_LIVE / rel, body, newline="\r\n")

    # REPO-AHEAD (repo is a strict superset)
    for i, rel in enumerate(
        (
            "common/ci-hygiene.md",
            "common/windows-shell.md",
            "project/release.md",
            "project/secrets-policy.md",
        )
    ):
        live = f"# {rel}\nshared prefix\n"
        repo = live + f"repo extra line {i}\n"
        _write(FIXTURE_LIVE / rel, live)
        _write(FIXTURE_REPO / rel, repo)

    # LIVE-AHEAD: the three catalog-named live-larger files
    extras = {
        NAMED_LIVE_LARGER[0]: "LIVE-UNIQUE: owner-ops-authorization measured live-larger\n",
        NAMED_LIVE_LARGER[1]: "LIVE-UNIQUE: performance measured live-larger\n",
        NAMED_LIVE_LARGER[2]: "LIVE-UNIQUE: security measured live-larger\n",
    }
    for rel, extra in extras.items():
        _write(FIXTURE_REPO / rel, SHARED)
        _write(FIXTURE_LIVE / rel, SHARED + extra)

    # DIVERGED: both unique. Repo is larger so one-directional / size say REPO-AHEAD.
    diverged = "common/fan-out-contract.md"
    live_d = SHARED + "LIVE-UNIQUE: fan-out C4 mechanical comparison\n"
    repo_d = SHARED + "REPO-UNIQUE: extra contract clause A\nREPO-UNIQUE: extra clause B\n"
    _write(FIXTURE_LIVE / diverged, live_d)
    _write(FIXTURE_REPO / diverged, repo_d)
    if len(repo_d.encode()) <= len(live_d.encode()):
        raise SystemExit("diverged fixture is not repo-larger")

    # one extra DIVERGED that is live-larger in bytes (still both-unique)
    both = "project/unsettled.md"
    _write(FIXTURE_REPO / both, SHARED + "repo unsettled line\n")
    _write(
        FIXTURE_LIVE / both,
        SHARED + "live unsettled line\nLIVE-UNIQUE remainder\n",
    )

    return {
        "repo_root": str(FIXTURE_REPO),
        "live_root": str(FIXTURE_LIVE),
        "named_live_larger": list(NAMED_LIVE_LARGER),
        "diverged_repo_larger": diverged,
        "source": "fixtures",
        "cited_2026_08_09_5_of_88": False,
    }


def resolve_pair() -> dict:
    host = host_candidates()
    pair = host_pair()
    if pair is not None:
        return {
            "repo_root": str(pair[0]),
            "live_root": str(pair[1]),
            "source": "host",
            "host_candidates": host,
            "named_live_larger": list(NAMED_LIVE_LARGER),
            "cited_2026_08_09_5_of_88": False,
        }
    meta = build_estate_fixtures()
    meta["host_candidates"] = host
    return meta
