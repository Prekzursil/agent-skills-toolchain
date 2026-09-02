"""Repo-versus-live audit of harness state key shapes.

A store armed in the repo and missing from the live tree is still live for
anyone who deploys: it is listed, not dismissed. Scanning only the live tree
is the failure class live-only-audit-misses-repo-armed-config.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
HOST_LIVE_CANDIDATES = (
    Path.home() / ".claude" / "hooks",
    Path("/root/.claude/hooks"),
)

RE_STORE = re.compile(r'^STORE_NAME\s*=\s*"([^"]+)"', re.M)
RE_SHAPE = re.compile(r'^KEY_SHAPE\s*=\s*"(session|project)"', re.M)
RE_TMPL = re.compile(r'^KEY_TEMPLATE\s*=\s*"([^"]+)"', re.M)
STORES = ("goal_inject", "ledger_replay", "claims", "caches")


def _line_of(text: str, needle: str) -> int | None:
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return i
    return None


def scan_tree(root: Path) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    hooks = root / "hooks"
    if hooks.is_dir():
        for path in sorted(hooks.glob("*.py")):
            if path.name.startswith("_"):
                continue
            text = path.read_text(encoding="utf-8")
            sm = RE_STORE.search(text)
            km = RE_SHAPE.search(text)
            tm = RE_TMPL.search(text)
            if not sm:
                continue
            store = sm.group(1)
            rel = path.as_posix()
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                pass
            found[store] = {
                "store": store,
                "key_shape": km.group(1) if km else "unknown",
                "key_template": tm.group(1) if tm else "",
                "path": rel,
                "abs_path": str(path),
                "line": _line_of(text, "KEY_SHAPE"),
                "present": True,
                "source": "hooks-py",
            }
    settings = root / "agent-self" / "config" / "settings.json"
    if settings.is_file():
        text = settings.read_text(encoding="utf-8")
        doc = json.loads(text)
        stores = (doc.get("state_keying") or {}).get("stores") or {}
        for name, spec in stores.items():
            if name in found:
                found[name]["settings_key_shape"] = spec.get("key_shape")
                found[name]["settings_line"] = _line_of(text, '"' + name + '"')
            else:
                found[name] = {
                    "store": name,
                    "key_shape": spec.get("key_shape") or "unknown",
                    "key_template": spec.get("template") or "",
                    "path": "agent-self/config/settings.json",
                    "abs_path": str(settings),
                    "line": _line_of(text, '"' + name + '"'),
                    "present": True,
                    "source": "settings-json",
                }
    return found


def host_live_status() -> dict[str, Any]:
    rows = []
    any_present = False
    for p in HOST_LIVE_CANDIDATES:
        present = p.is_dir()
        n = 0
        if present:
            n = sum(1 for q in p.rglob("*") if q.is_file())
            any_present = True
        rows.append({"path": str(p), "present": present, "file_count": n})
    return {"attempted": True, "any_present": any_present, "candidates": rows}


def table_row(
    store: str,
    repo: dict[str, Any] | None,
    live: dict[str, Any] | None,
) -> dict[str, Any]:
    repo_loc = "ABSENT-FROM-REPO"
    live_loc = "ABSENT-FROM-LIVE"
    repo_shape = None
    live_shape = None
    if repo:
        repo_loc = f"{repo['path']}:{repo.get('line') or '?'}"
        repo_shape = repo.get("key_shape")
    if live:
        live_loc = f"{live['path']}:{live.get('line') or '?'}"
        live_shape = live.get("key_shape")
    # Prefer repo shape as the "current source" answer; live shape is reported separately.
    shape = repo_shape or live_shape or "unknown"
    repo_armed_live_absent = bool(repo) and not live
    return {
        "store": store,
        "key_shape": shape,
        "repo_key_shape": repo_shape,
        "live_key_shape": live_shape,
        "repo_source": repo_loc,
        "deployed_copy": live_loc,
        "repo_present": bool(repo),
        "live_present": bool(live),
        "repo_armed_live_absent": repo_armed_live_absent,
        "listed_despite_live_absent": repo_armed_live_absent,
        "project_keyed": shape == "project",
        "project_keyed_in_repo": repo_shape == "project",
        "project_keyed_in_live": live_shape == "project",
    }


def audit_live_only(
    live_files: dict[str, dict[str, Any]], names: list[str]
) -> list[dict[str, Any]]:
    rows = []
    for n in names:
        live = live_files.get(n)
        if not live:
            continue
        rows.append(
            {
                "store": n,
                "key_shape": live.get("key_shape"),
                "deployed_copy": f"{live['path']}:{live.get('line') or '?'}",
                "repo_source": "NOT-READ",
            }
        )
    return rows


def audit(repo_root: Path, live_root: Path) -> dict[str, Any]:
    repo_files = scan_tree(repo_root)
    live_files = scan_tree(live_root)
    names: list[str] = []
    for n in list(STORES) + sorted(set(repo_files) | set(live_files)):
        if n not in names:
            names.append(n)
    rows = [table_row(n, repo_files.get(n), live_files.get(n)) for n in names]
    live_only = audit_live_only(live_files, names)
    live_only_names = {x["store"] for x in live_only}
    missed = [
        r["store"]
        for r in rows
        if r["repo_armed_live_absent"] and r["store"] not in live_only_names
    ]
    return {
        "repo_root": str(repo_root),
        "live_root": str(live_root),
        "repo_files_opened": len(repo_files),
        "live_files_opened": len(live_files),
        "live_tree_exists": live_root.is_dir(),
        "read_both": bool(repo_files) and live_root.is_dir(),
        "host_live": host_live_status(),
        "rows": rows,
        "live_only_scan_rows": live_only,
        "live_only_scan_misses_repo_armed": missed,
        "project_keyed_in_repo": [
            r["store"] for r in rows if r["project_keyed_in_repo"]
        ],
        "project_keyed_in_live": [
            r["store"] for r in rows if r["project_keyed_in_live"]
        ],
        "repo_armed_live_absent": [
            r["store"] for r in rows if r["repo_armed_live_absent"]
        ],
    }


def audit_production() -> dict[str, Any]:
    """Scan this worktree's hooks/ plus host ~/.claude/hooks (usually absent)."""
    host = Path.home() / ".claude"
    # Use ~/.claude as live root so scan_tree looks at ~/.claude/hooks
    return audit(REPO, host)
