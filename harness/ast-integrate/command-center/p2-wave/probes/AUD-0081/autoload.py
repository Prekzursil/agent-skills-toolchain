#!/usr/bin/env python3
"""AUD-0081 shared inventory, filename search, and content classifier.

Probe 1 is a filename walk of non-owner-authored trees.
Probe 2 is a content read that distinguishes inert documentation from an
active hook or MCP registration. A file named CLAUDE.md is not by itself
a risk finding.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

UID = "AUD-0081"
PLANTED_REL = (
    "command-center/p2-wave/probes/AUD-0081/fixtures/untrusted-clone"
)
AUTOLOAD_NAMES = frozenset(
    {".claude", ".codex", ".mcp.json", "hooks", "AGENTS.md", "CLAUDE.md"}
)
SKIP_DIR_NAMES = frozenset(
    {
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        "dist",
        "build",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }
)
VENDOR_DIR_NAMES = frozenset(
    {
        "vendor",
        "third_party",
        "third-party",
        "_vendor",
        "vendored",
        "node_modules",
    }
)
HOOK_EVENTS = (
    "PreToolUse",
    "PostToolUse",
    "Stop",
    "SessionStart",
    "SessionEnd",
    "Notification",
    "UserPromptSubmit",
    "PreCompact",
    "SubagentStart",
)
_HOOK_KEY_RE = re.compile(
    r'(?m)^(?:#{1,6}\s+)?(?:["\']?)(?:'
    + "|".join(HOOK_EVENTS)
    + r')(?:["\']?)\s*:',
)
_MCP_JSON_RE = re.compile(r'"mcpServers"\s*:\s*\{')
_PRETOOL_RE = re.compile(r"(?m)^PreToolUse\s*:")


def rel_of(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _prune(dirnames: list[str]) -> None:
    dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES and d != ".git"]


def iter_nested_git_roots() -> list[dict]:
    """Find trees whose .git is a nested directory or a submodule-style file."""
    roots: list[dict] = []
    repo = REPO.resolve()
    for dirpath, dirnames, filenames in os.walk(repo, followlinks=False):
        _prune(dirnames)
        p = Path(dirpath)
        if p == repo:
            continue
        git_dir = ".git" in dirnames
        git_file = ".git" in filenames
        if git_dir or git_file:
            kind = "git-directory" if git_dir else "git-file"
            roots.append(
                {
                    "path": rel_of(p),
                    "tree_class": "cloned",
                    "marker": kind,
                }
            )
            if git_dir:
                dirnames.remove(".git")
    return roots


def iter_named_untrusted_roots() -> list[dict]:
    roots: list[dict] = []
    repo = REPO.resolve()
    for dirpath, dirnames, filenames in os.walk(repo, followlinks=False):
        _prune(dirnames)
        p = Path(dirpath)
        name = p.name
        rel = rel_of(p)
        if name in VENDOR_DIR_NAMES:
            roots.append(
                {"path": rel, "tree_class": "vendored", "marker": f"dirname:{name}"}
            )
        if name.startswith("_scratch") or name.startswith("scratch-"):
            roots.append(
                {
                    "path": rel,
                    "tree_class": "agent-scratch",
                    "marker": f"dirname:{name}",
                }
            )
        _ = filenames
    return roots


def planted_root() -> dict:
    return {
        "path": PLANTED_REL,
        "tree_class": "planted-untrusted-control",
        "marker": "unit-fixture+.git-file",
    }


def aud0009_status() -> dict:
    path = REPO / "command-center/audit/AUD-0009-submodule-vendored-inventory.json"
    present = path.is_file() and path.stat().st_size > 0
    return {
        "path": "command-center/audit/AUD-0009-submodule-vendored-inventory.json",
        "present": present,
        "used_as_inventory": False,
        "reason": (
            "AUD-0009 artifact present; AUD-0081 still walks the live tree so a "
            "stale inventory cannot hide a nested clone."
            if present
            else "AUD-0009 artifact absent; live nested-.git / vendor / scratch walk is the inventory."
        ),
    }


def untrusted_roots() -> list[dict]:
    by_path: dict[str, dict] = {}
    for row in [planted_root(), *iter_nested_git_roots(), *iter_named_untrusted_roots()]:
        prev = by_path.get(row["path"])
        if prev is None:
            by_path[row["path"]] = dict(row)
            continue
        if prev["tree_class"] == "planted-untrusted-control":
            prev["marker"] = f"{prev['marker']}+{row['marker']}"
        elif row["tree_class"] == "planted-untrusted-control":
            by_path[row["path"]] = dict(row)
            by_path[row["path"]]["marker"] = f"{row['marker']}+{prev['marker']}"
        elif row["tree_class"] == "cloned" and prev["tree_class"] != "cloned":
            by_path[row["path"]] = dict(row)
    return sorted(by_path.values(), key=lambda r: r["path"])


def containing_root(rel_path: str, roots: list[dict]) -> dict | None:
    matches = [r for r in roots if rel_path == r["path"] or rel_path.startswith(r["path"] + "/")]
    if not matches:
        return None
    return max(matches, key=lambda r: len(r["path"]))


def filename_hits(roots: list[dict] | None = None) -> list[dict]:
    """Probe 1: name-only search inside untrusted trees."""
    if roots is None:
        roots = untrusted_roots()
    hits: list[dict] = []
    seen: set[str] = set()
    for root in roots:
        base = REPO / root["path"]
        if not base.exists():
            continue
        if base.is_file():
            walk_roots = [base.parent]
        else:
            walk_roots = [base]
        for wr in walk_roots:
            for dirpath, dirnames, filenames in os.walk(wr, followlinks=False):
                _prune(dirnames)
                pdir = Path(dirpath)
                for name in list(dirnames) + list(filenames):
                    if name not in AUTOLOAD_NAMES:
                        continue
                    target = pdir / name
                    rel = rel_of(target)
                    if rel in seen:
                        continue
                    seen.add(rel)
                    hits.append(
                        {
                            "path": rel,
                            "name": name,
                            "is_dir": target.is_dir(),
                            "is_file": target.is_file(),
                            "bytes": target.stat().st_size if target.is_file() else 0,
                            "tree_path": root["path"],
                            "tree_class": root["tree_class"],
                            "tree_marker": root["marker"],
                            "planted_control": root["tree_class"]
                            == "planted-untrusted-control",
                        }
                    )
    hits.sort(key=lambda h: h["path"])
    return hits


def _json_active(doc: object) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, "non-object-json"
    servers = doc.get("mcpServers")
    if isinstance(servers, dict) and servers:
        return True, "mcpServers"
    if isinstance(servers, list) and servers:
        return True, "mcpServers-list"
    hooks = doc.get("hooks")
    if isinstance(hooks, dict):
        for event in HOOK_EVENTS:
            if event in hooks and hooks[event]:
                return True, f"hooks.{event}"
    for event in HOOK_EVENTS:
        if event in doc and doc[event]:
            return True, f"top-level.{event}"
    return False, "json-without-hook-or-mcp"


def classify_text(name: str, text: str) -> dict:
    """Content classifier. Filename alone never forces active."""
    stripped = text.strip()
    if not stripped:
        return {
            "classification": "inert",
            "reason": "empty-body",
            "filename_is_not_risk": name in {"CLAUDE.md", "AGENTS.md"},
        }
    try:
        doc = json.loads(stripped)
    except (json.JSONDecodeError, UnicodeDecodeError):
        doc = None
    if doc is not None:
        active, reason = _json_active(doc)
        return {
            "classification": "active" if active else "inert",
            "reason": reason,
            "filename_is_not_risk": name in {"CLAUDE.md", "AGENTS.md"} and not active,
        }
    if _MCP_JSON_RE.search(text):
        return {
            "classification": "active",
            "reason": "embedded-mcpServers-object",
            "filename_is_not_risk": False,
        }
    if _PRETOOL_RE.search(text) or _HOOK_KEY_RE.search(text):
        return {
            "classification": "active",
            "reason": "hook-event-registration",
            "filename_is_not_risk": False,
        }
    return {
        "classification": "inert",
        "reason": "prose-without-hook-or-mcp-registration",
        "filename_is_not_risk": name in {"CLAUDE.md", "AGENTS.md", ".mcp.json"},
    }


def classify_path(path: Path) -> dict:
    rel = rel_of(path)
    name = path.name
    if path.is_dir():
        child_active: list[str] = []
        child_inert: list[str] = []
        try:
            children = sorted(path.iterdir(), key=lambda p: p.name)
        except OSError as exc:
            return {
                "path": rel,
                "name": name,
                "classification": "unread",
                "reason": f"dir-list-error:{type(exc).__name__}",
                "filename_is_not_risk": True,
            }
        for child in children:
            if child.name in SKIP_DIR_NAMES or child.name == ".git":
                continue
            if child.is_file() and child.stat().st_size <= 1_000_000:
                try:
                    text = child.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                inner = classify_text(child.name, text)
                if inner["classification"] == "active":
                    child_active.append(rel_of(child))
                else:
                    child_inert.append(rel_of(child))
        active = bool(child_active)
        return {
            "path": rel,
            "name": name,
            "classification": "active" if active else "inert",
            "reason": (
                f"dir-child-active:{child_active[0]}"
                if active
                else "dir-without-active-child"
            ),
            "filename_is_not_risk": not active,
            "active_children": child_active[:20],
            "inert_children_count": len(child_inert),
        }
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return {
            "path": rel,
            "name": name,
            "classification": "unread",
            "reason": f"read-error:{type(exc).__name__}",
            "filename_is_not_risk": True,
        }
    if b"\x00" in raw[:8192]:
        return {
            "path": rel,
            "name": name,
            "classification": "inert",
            "reason": "binary-not-a-config",
            "filename_is_not_risk": True,
        }
    text = raw.decode("utf-8", errors="replace")
    inner = classify_text(name, text)
    inner["path"] = rel
    inner["name"] = name
    inner["bytes"] = len(raw)
    return inner


def filename_only_risk(hit: dict) -> bool:
    """Known-wrong mutant: treat the auto-load *name* as a risk finding."""
    return hit.get("name") in AUTOLOAD_NAMES


def classify_hits(hits: list[dict] | None = None) -> list[dict]:
    if hits is None:
        hits = filename_hits()
    out = []
    for hit in hits:
        classified = classify_path(REPO / hit["path"])
        row = dict(hit)
        row.update(
            {
                "classification": classified.get("classification"),
                "reason": classified.get("reason"),
                "filename_is_not_risk": classified.get("filename_is_not_risk"),
                "filename_only_would_flag": filename_only_risk(hit),
            }
        )
        out.append(row)
    return out


def fixture_paths() -> dict[str, str]:
    base = PLANTED_REL
    return {
        "inert_agents": f"{base}/inert-docs/AGENTS.md",
        "active_agents": f"{base}/active-hooks/AGENTS.md",
        "inert_claude": f"{base}/docs/CLAUDE.md",
        "git_file": f"{base}/.git",
    }


def control_both_states(classified: list[dict] | None = None) -> dict:
    """Catalog tests_required: prose AGENTS.md inert, PreToolUse AGENTS.md active, one fixture."""
    fx = fixture_paths()
    rows = {r["path"]: r for r in (classified or classify_hits())}
    inert = rows.get(fx["inert_agents"])
    active = rows.get(fx["active_agents"])
    claude = rows.get(fx["inert_claude"])
    inert_ok = bool(inert) and inert.get("classification") == "inert"
    active_ok = bool(active) and active.get("classification") == "active"
    claude_ok = bool(claude) and claude.get("classification") == "inert"
    filename_mutant_red = bool(inert) and filename_only_risk(inert)
    claude_mutant_red = bool(claude) and filename_only_risk(claude)
    return {
        "same_fixture": PLANTED_REL,
        "inert_agents_path": fx["inert_agents"],
        "active_agents_path": fx["active_agents"],
        "inert_claude_path": fx["inert_claude"],
        "inert_agents_present": inert is not None,
        "active_agents_present": active is not None,
        "inert_claude_present": claude is not None,
        "inert_classified_inert": inert_ok,
        "active_classified_active": active_ok,
        "claude_classified_inert": claude_ok,
        "both_states_on_one_fixture": inert_ok and active_ok,
        "filename_only_mutant_flags_inert_agents": filename_mutant_red,
        "filename_only_mutant_flags_inert_claude": claude_mutant_red,
        "claude_md_filename_is_not_risk": claude_ok,
        "pass": inert_ok and active_ok and claude_ok and filename_mutant_red,
    }


def live_untrusted_active(classified: list[dict] | None = None) -> list[dict]:
    rows = classified if classified is not None else classify_hits()
    return [
        r
        for r in rows
        if r.get("classification") == "active"
        and not r.get("planted_control")
        and r.get("tree_class") in {"cloned", "vendored", "agent-scratch"}
    ]


def summary() -> dict:
    roots = untrusted_roots()
    hits = filename_hits(roots)
    classified = classify_hits(hits)
    control = control_both_states(classified)
    live_active = live_untrusted_active(classified)
    planted_hits = [h for h in classified if h.get("planted_control")]
    return {
        "unit_id": UID,
        "autoload_names": sorted(AUTOLOAD_NAMES),
        "aud0009": aud0009_status(),
        "untrusted_root_count": len(roots),
        "untrusted_roots": roots,
        "filename_hit_count": len(hits),
        "filename_hits": hits,
        "classified": classified,
        "planted_hit_count": len(planted_hits),
        "live_untrusted_active": live_active,
        "live_untrusted_active_count": len(live_active),
        "control": control,
    }
