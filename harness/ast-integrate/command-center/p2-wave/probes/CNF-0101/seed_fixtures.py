#!/usr/bin/env python3
"""Write static CNF-0101 fixture trees. Not a named probe. Probes only READ these."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
CENSUS_SHIPPED = HERE / "fixtures" / "census" / "shipped"
CENSUS_LIVE = HERE / "fixtures" / "census" / "live"
CTRL_SHIPPED = HERE / "fixtures" / "control" / "shipped"
CTRL_LIVE = HERE / "fixtures" / "control" / "live"
SYNC = HERE / "fixtures" / "sync-from-live.ps1"


def _write(path: Path, body: str, *, newline: str = "\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = body.encode("utf-8")
    if newline == "\r\n":
        data = data.replace(b"\n", b"\r\n")
    path.write_bytes(data)


def _wipe(root: Path) -> None:
    if not root.exists():
        return
    for p in root.rglob("*"):
        if p.is_file():
            p.unlink()


def seed() -> None:
    _wipe(CENSUS_SHIPPED)
    _wipe(CENSUS_LIVE)
    _wipe(CTRL_SHIPPED)
    _wipe(CTRL_LIVE)

    identical = {
        "rules/common/agents.md": "# agents\nidentical body for both trees\n",
        "rules/common/hooks.md": "# hooks\nidentical body for both trees\n",
        "plugin.json": '{"id":"cnf-0101-shipped","version":"1"}\n',
        "skills/skill.ship/SKILL.md": "# skill.ship\nshared skill body\n",
    }
    for rel, body in identical.items():
        _write(CENSUS_SHIPPED / rel, body)
        _write(CENSUS_LIVE / rel, body)

    eol = {
        "rules/common/logging.md": "# logging\nshared body line\nthird line\n",
        "rules/project/branching.md": "# branching\nkeep left and right equal after LF\n",
        "docs/readme.md": "# readme\nshipped file set note\n",
    }
    for rel, body in eol.items():
        _write(CENSUS_SHIPPED / rel, body, newline="\n")
        _write(CENSUS_LIVE / rel, body, newline="\r\n")

    repo_ahead = {
        "rules/common/ci-hygiene.md": (
            "# ci-hygiene\nshared prefix\nREPO-EXTRA:ci-hygiene-1\n"
        ),
        "rules/common/windows-shell.md": (
            "# windows-shell\nshared prefix\nREPO-EXTRA:windows-shell-2\n"
        ),
        "rules/project/testing.md": "# testing\nshared prefix\nREPO-EXTRA:testing-3\n",
    }
    for rel, repo_body in repo_ahead.items():
        live_body = "\n".join(repo_body.split("\n")[:2]) + "\n"
        _write(CENSUS_LIVE / rel, live_body)
        _write(CENSUS_SHIPPED / rel, repo_body)

    live_ahead = {
        "rules/common/owner-ops-authorization.md": (
            "# owner-ops-authorization\nshared prefix\nLIVE-EXTRA:owner-ops+1001B-pin\n"
        ),
        "rules/common/performance.md": (
            "# performance\nshared prefix\nLIVE-EXTRA:performance+178B-pin\n"
        ),
        "rules/common/security.md": (
            "# security\nshared prefix\nLIVE-EXTRA:security+97B-pin\n"
        ),
    }
    for rel, live_body in live_ahead.items():
        repo_body = "\n".join(live_body.split("\n")[:2]) + "\n"
        _write(CENSUS_SHIPPED / rel, repo_body)
        _write(CENSUS_LIVE / rel, live_body)

    # Same-size DIVERGED: unique lines both sides, equal byte length.
    diverged_reviews_repo = "# reviews\nshared line\nREPO-UNIQUE:reviews-side-A\n"
    diverged_reviews_live = "# reviews\nshared line\nLIVE-UNIQUE:reviews-side-B\n"
    if len(diverged_reviews_repo.encode()) != len(diverged_reviews_live.encode()):
        raise SystemExit("reviews diverged fixture size mismatch")
    _write(CENSUS_SHIPPED / "rules/project/reviews.md", diverged_reviews_repo)
    _write(CENSUS_LIVE / "rules/project/reviews.md", diverged_reviews_live)

    repo_manifest = '{\n  "id": "dispatch",\n  "repo_only_hook": true\n}\n'
    live_manifest = '{\n  "id": "dispatch",\n  "live_only_hook": true\n}\n'
    _write(CENSUS_SHIPPED / "hooks/_dispatch/manifest.json", repo_manifest)
    _write(CENSUS_LIVE / "hooks/_dispatch/manifest.json", live_manifest)

    _write(
        CENSUS_SHIPPED / "rules/repo-only/unpublished-rule.md",
        "# unpublished-rule\nrepo only\n",
    )
    _write(
        CENSUS_LIVE / "rules/live-only/uncommitted-rule.md",
        "# uncommitted-rule\nlive only\n",
    )

    # Probe-2 control pairs (static; probes must not rewrite them).
    _write(CTRL_SHIPPED / "identical.md", "# control identical\nshared\n")
    _write(CTRL_LIVE / "identical.md", "# control identical\nshared\n")
    eol_body = "# control eol\nline-a\nline-b\n"
    _write(CTRL_SHIPPED / "eol-only.md", eol_body, newline="\n")
    _write(CTRL_LIVE / "eol-only.md", eol_body, newline="\r\n")
    _write(CTRL_SHIPPED / "content.md", "# control content\nAAAA\n")
    _write(CTRL_LIVE / "content.md", "# control content\nBBBB\n")
    d_repo = "# control diverged\nshared\nREPO-UNIQUE:ctrl-side-A\n"
    d_live = "# control diverged\nshared\nLIVE-UNIQUE:ctrl-side-B\n"
    if len(d_repo.encode()) != len(d_live.encode()):
        raise SystemExit("control diverged size mismatch")
    _write(CTRL_SHIPPED / "diverged.md", d_repo)
    _write(CTRL_LIVE / "diverged.md", d_live)
    _write(CTRL_SHIPPED / "repo-ahead.md", "# ra\nshared\nREPO-EXTRA:ra\n")
    _write(CTRL_LIVE / "repo-ahead.md", "# ra\nshared\n")
    _write(CTRL_SHIPPED / "live-ahead.md", "# la\nshared\n")
    _write(CTRL_LIVE / "live-ahead.md", "# la\nshared\nLIVE-EXTRA:la\n")

    SYNC.parent.mkdir(parents=True, exist_ok=True)
    SYNC.write_text(
        "# fixture stand-in of catalog-named scripts/sync-from-live.ps1\n"
        "# CNF-0101 MUST NOT execute this against any tree.\n"
        "param($LiveRoot, $RepoRoot)\n"
        "# LINE-NO-TRANSFORM: one-directional overwrite, no EOL conversion, no merge.\n"
        "Copy-Item -Path $LiveRoot -Destination $RepoRoot -Recurse -Force\n",
        encoding="utf-8",
        newline="\n",
    )
    print("seeded CNF-0101 fixtures")


if __name__ == "__main__":
    seed()
