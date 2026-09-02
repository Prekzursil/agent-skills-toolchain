"""Locate host trees and build today's measurable fixture trees.

The 2026-08-09 5/88 live-vs-repo numbers are NOT cited. Host `rules/` (repo)
and `~/.claude/rules` (live) are searched and hashed today with two signals
(sha256 AND byte-size). A missing live tree is recorded as 88 repo-only, not
as the historical 5/88 split. Census fixtures remain for the two-directional
detector-control (plant/revert) which cannot run against an absent live root.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CENSUS_REPO = HERE / "fixtures" / "census" / "repo" / "rules"
CENSUS_LIVE = HERE / "fixtures" / "census" / "live" / "rules"
CTRL_REPO = HERE / "fixtures" / "control" / "repo" / "rules"
CTRL_LIVE = HERE / "fixtures" / "control" / "live" / "rules"
ABSENT_LIVE = HERE / "fixtures" / "absent-live" / "rules"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def host_candidates() -> list[dict]:
    rows = []
    for p, role in (
        (REPO / "rules", "repo-rules"),
        (Path.home() / ".claude" / "rules", "live-rules"),
        (Path.home() / ".claude" / "rules", "live-rules"),
        (Path.home() / ".cursor" / "rules", "live-rules"),
        (Path.home() / ".claude", "claude-home-not-rules"),
        (Path.home() / ".claude", "claude-home-not-rules"),
    ):
        rows.append(
            {
                "path": str(p),
                "role": role,
                "exists": p.exists(),
                "is_dir": p.is_dir(),
                "file_count": sum(1 for q in p.rglob("*") if q.is_file()) if p.is_dir() else 0,
            }
        )
    return rows


def _empty_live_root() -> Path:
    ABSENT_LIVE.mkdir(parents=True, exist_ok=True)
    for p in ABSENT_LIVE.rglob("*"):
        if p.is_file():
            p.unlink()
    return ABSENT_LIVE


def host_divergence() -> dict:
    """Today's live-vs-repo census. Does not cite 2026-08-09 5/88."""
    repo = REPO / "rules"
    live_found: Path | None = None
    for p in (
        Path.home() / ".claude" / "rules",
        Path.home() / ".claude" / "rules",
        Path.home() / ".cursor" / "rules",
    ):
        if p.is_dir() and any(q.is_file() for q in p.rglob("*")):
            live_found = p
            break
    live = live_found if live_found is not None else _empty_live_root()
    if repo.is_dir():
        snap = census(repo, live)
    else:
        snap = {
            "repo_root": str(repo),
            "live_root": str(live),
            "union_files": 0,
            "identical": 0,
            "repo_larger": 0,
            "live_larger": 0,
            "sha_diff_same_size": 0,
            "repo_only": 0,
            "live_only": 0,
            "two_signals": ["sha256", "byte-size"],
            "rows": [],
        }
    snap["repo_tree_present"] = repo.is_dir()
    snap["live_tree_present"] = live_found is not None
    snap["cited_2026_08_09_5_of_88"] = (
        int(snap.get("identical") or 0) == 5 and int(snap.get("union_files") or 0) == 88
    )
    return snap


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")


def _wipe(root: Path) -> None:
    if not root.exists():
        return
    for p in root.rglob("*"):
        if p.is_file():
            p.unlink()


def build_census_fixtures() -> dict:
    """Two-directional split measured today. Not the 2026-08-09 5/88 citation."""
    _wipe(CENSUS_REPO)
    _wipe(CENSUS_LIVE)

    identical = [
        "common/agents.md",
        "common/hooks.md",
        "common/security.md",
        "common/performance.md",
    ]
    repo_larger = [
        "common/ci-hygiene.md",
        "common/windows-shell.md",
        "common/owner-ops-authorization.md",
        "project/naming.md",
        "project/reviews.md",
        "project/testing.md",
        "project/release.md",
    ]
    live_larger = [
        "live-only-edits/session-notes.md",
        "live-only-edits/local-allowlist.md",
        "live-only-edits/debug-flags.md",
    ]
    same_size_diff = [
        "common/logging.md",
        "project/branching.md",
        "project/owners.md",
        "project/secrets-policy.md",
    ]
    repo_only = ["repo-only/unpublished-rule.md"]
    live_only = ["live-only/uncommitted-rule.md"]

    for rel in identical:
        body = f"# {rel}\nidentical body for both trees\n"
        _write(CENSUS_REPO / rel, body)
        _write(CENSUS_LIVE / rel, body)
    for i, rel in enumerate(repo_larger):
        live = f"# {rel}\nshared prefix\n"
        repo = live + ("repo extra line %d\n" % i)
        _write(CENSUS_LIVE / rel, live)
        _write(CENSUS_REPO / rel, repo)
    for i, rel in enumerate(live_larger):
        repo = f"# {rel}\nshared prefix\n"
        live = repo + ("live extra line %d\n" % i)
        _write(CENSUS_REPO / rel, repo)
        _write(CENSUS_LIVE / rel, live)
    for rel in same_size_diff:
        a = f"# {rel}\nAAAA-same-length-payload-xx\n"
        b = f"# {rel}\nBBBB-same-length-payload-xx\n"
        if len(a.encode()) != len(b.encode()):
            raise SystemExit("same-size fixture length mismatch")
        _write(CENSUS_REPO / rel, a)
        _write(CENSUS_LIVE / rel, b)
    for rel in repo_only:
        _write(CENSUS_REPO / rel, f"# {rel}\nrepo only\n")
    for rel in live_only:
        _write(CENSUS_LIVE / rel, f"# {rel}\nlive only\n")

    return census(CENSUS_REPO, CENSUS_LIVE)


def build_control_fixtures() -> None:
    body = "# control\nboth-states baseline identical\n"
    for rel in ("common/control.md", "common/hooks.md"):
        _write(CTRL_REPO / rel, body)
        _write(CTRL_LIVE / rel, body)


def iter_rel_files(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    for p in root.rglob("*"):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = p
    return out


def census(repo_root: Path, live_root: Path) -> dict:
    repo = iter_rel_files(repo_root)
    live = iter_rel_files(live_root)
    keys = sorted(set(repo) | set(live))
    rows = []
    identical = repo_larger = live_larger = sha_diff_same_size = 0
    repo_only = live_only = 0
    for rel in keys:
        rp, lp = repo.get(rel), live.get(rel)
        rec: dict = {"path": rel, "in_repo": rp is not None, "in_live": lp is not None}
        if rp is None:
            raw = lp.read_bytes()
            rec.update(
                {
                    "live_bytes": len(raw),
                    "live_sha256": sha256_bytes(raw),
                    "direction": "live-only",
                }
            )
            live_only += 1
        elif lp is None:
            raw = rp.read_bytes()
            rec.update(
                {
                    "repo_bytes": len(raw),
                    "repo_sha256": sha256_bytes(raw),
                    "direction": "repo-only",
                }
            )
            repo_only += 1
        else:
            rb, lb = rp.read_bytes(), lp.read_bytes()
            rs, ls = sha256_bytes(rb), sha256_bytes(lb)
            rec.update(
                {
                    "repo_bytes": len(rb),
                    "live_bytes": len(lb),
                    "repo_sha256": rs,
                    "live_sha256": ls,
                }
            )
            if rs == ls and len(rb) == len(lb):
                rec["direction"] = "identical"
                identical += 1
            elif len(rb) > len(lb):
                rec["direction"] = "repo-larger"
                repo_larger += 1
            elif len(lb) > len(rb):
                rec["direction"] = "live-larger"
                live_larger += 1
            else:
                rec["direction"] = "sha-diff-same-size"
                sha_diff_same_size += 1
        rows.append(rec)
    return {
        "repo_root": str(repo_root),
        "live_root": str(live_root),
        "union_files": len(keys),
        "identical": identical,
        "repo_larger": repo_larger,
        "live_larger": live_larger,
        "sha_diff_same_size": sha_diff_same_size,
        "repo_only": repo_only,
        "live_only": live_only,
        "two_signals": ["sha256", "byte-size"],
        "cited_2026_08_09_5_of_88": False,
        "rows": rows,
    }


def dump(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
