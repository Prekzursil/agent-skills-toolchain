"""Live-box census. Never prints secret values; env/header keys are named only."""
from __future__ import annotations

import json
from pathlib import Path

from inject import is_lazy, parse_frontmatter

CANDIDATE_USAGE_ROOTS = (
    Path.home() / ".claude" / "projects",
    Path.home() / ".cursor" / "projects",
)
LIVE_SKILLS = Path.home() / ".claude" / "skills"
LIVE_RULES = Path.home() / ".claude" / "rules"
LIVE_MCP = Path.home() / ".mcp.json"
LIVE_CURSOR_MCP = Path.home() / ".cursor" / "mcp.json"


def _safe_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def live_skills_census() -> dict:
    root = LIVE_SKILLS
    if not _safe_exists(root) or not root.is_dir():
        return {
            "status": "NOT-CHECKED",
            "reason": "absent:~/.claude/skills",
            "path": str(root),
        }
    always_on = 0
    lazy = 0
    tree_bytes = 0
    injected_bytes = 0
    for path in sorted(root.rglob("SKILL.md")):
        try:
            raw = path.read_bytes().replace(b"\r\n", b"\n")
        except OSError:
            continue
        tree_bytes += len(raw)
        meta, _ = parse_frontmatter(raw.decode("utf-8", errors="replace"))
        if is_lazy(meta):
            lazy += 1
        else:
            always_on += 1
            injected_bytes += len(raw)
    return {
        "status": "MEASURED",
        "path": str(root),
        "always_on": always_on,
        "lazy": lazy,
        "tree_bytes": tree_bytes,
        "always_on_bytes": injected_bytes,
        "file_size_inference_would_use_tree_bytes": True,
    }


def live_rules_census() -> dict:
    root = LIVE_RULES
    if not _safe_exists(root) or not root.is_dir():
        return {
            "status": "NOT-CHECKED",
            "reason": "absent:~/.claude/rules",
            "path": str(root),
        }
    n = 0
    tree_bytes = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            tree_bytes += path.stat().st_size
            n += 1
        except OSError:
            continue
    return {
        "status": "MEASURED",
        "path": str(root),
        "n_files": n,
        "tree_bytes": tree_bytes,
    }


def _mcp_server_names(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "status": "NOT-CHECKED",
            "reason": f"unreadable:{type(exc).__name__}",
            "path": str(path),
        }
    servers = doc.get("mcpServers") or doc.get("servers") or {}
    names = []
    env_keys_named = []
    if isinstance(servers, dict):
        for name, cfg in servers.items():
            names.append(str(name))
            if isinstance(cfg, dict) and isinstance(cfg.get("env"), dict):
                env_keys_named.extend(sorted(str(k) for k in cfg["env"].keys()))
    return {
        "status": "MEASURED",
        "path": str(path),
        "server_names": names,
        "n_servers": len(names),
        "env_keys_named": env_keys_named,
        "env_values_recorded": False,
    }


def live_mcp_census() -> dict:
    rows = []
    for path in (LIVE_MCP, LIVE_CURSOR_MCP):
        if _safe_exists(path) and path.is_file():
            rows.append(_mcp_server_names(path))
        else:
            rows.append(
                {
                    "status": "NOT-CHECKED",
                    "reason": f"absent:{path}",
                    "path": str(path),
                }
            )
    return {"candidates": rows}


def live_usage_report(limit_files: int = 40) -> dict:
    """First-turn input_tokens if a session JSONL exists. Values only, no bodies."""
    scanned = 0
    hits = []
    for root in CANDIDATE_USAGE_ROOTS:
        if not _safe_exists(root) or not root.is_dir():
            continue
        try:
            jsonl_files = sorted(root.rglob("*.jsonl"))
        except OSError:
            continue
        for path in jsonl_files:
            if scanned >= limit_files:
                break
            scanned += 1
            try:
                with path.open("r", encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line or "input_tokens" not in line:
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        usage = None
                        if isinstance(obj, dict):
                            msg = obj.get("message") or obj.get("usage") or {}
                            if isinstance(msg, dict) and "usage" in msg:
                                usage = msg.get("usage")
                            elif isinstance(msg, dict) and "input_tokens" in msg:
                                usage = msg
                            elif "input_tokens" in obj:
                                usage = obj
                        if not isinstance(usage, dict):
                            continue
                        if "input_tokens" not in usage:
                            continue
                        hits.append(
                            {
                                "path": str(path),
                                "input_tokens": usage.get("input_tokens"),
                                "output_tokens": usage.get("output_tokens"),
                                "cache_read_input_tokens": usage.get(
                                    "cache_read_input_tokens"
                                ),
                                "note": (
                                    "first usage object in file; not used as "
                                    "occupancy numerator unless it is turn-0"
                                ),
                            }
                        )
                        break
            except OSError:
                continue
        if scanned >= limit_files:
            break
    if not hits:
        return {
            "status": "NOT-CHECKED",
            "reason": "no-session-jsonl-with-input_tokens",
            "files_scanned": scanned,
            "roots": [str(p) for p in CANDIDATE_USAGE_ROOTS],
        }
    first = hits[0]
    return {
        "status": "MEASURED",
        "files_scanned": scanned,
        "n_hits": len(hits),
        "first_hit": first,
        "used_as_occupancy_numerator": False,
        "reason_not_numerator": (
            "live JSONL usage is a mixed-turn instrument; occupancy uses the "
            "hermetic turn-0 injection snapshot, not this cumulative-looking field"
        ),
    }


def live_census() -> dict:
    return {
        "skills": live_skills_census(),
        "rules": live_rules_census(),
        "mcp": live_mcp_census(),
        "usage_report": live_usage_report(),
    }
