#!/usr/bin/env python3
"""Read-only plugin/marketplace enablement sweep for WFA-0018.

Settles which file governs enablement: ~/.claude/settings.json enabledPlugins
versus the same key in ~/.claude.json (root or per-project). The measured
estate trap is the RIGHT key in the WRONG file. This module never enables,
disables, installs, or removes a plugin.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

MUTATING_SUBCOMMANDS = frozenset(
    {
        "enable",
        "disable",
        "install",
        "uninstall",
        "remove",
        "add",
        "update",
        "publish",
        "market",
        "marketplace",
    }
)

PLUGIN_LIST_ARGV = ("claude", "plugin", "list")
PLUGIN_LIST_JSON_ARGV = ("claude", "plugin", "list", "--json")

REGISTRY_CANDIDATES = (
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "command-center/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "command-center/_wfa2_entries.json",
)

LIVE_SETTINGS_CANDIDATES = (
    "~/.claude/settings.json",
    str(Path.home() / ".claude" / "settings.json"),
    "/home/ubuntu/.claude/settings.json",
    "C:/Users/Prekzursil/.claude/settings.json",
    "/mnt/c/Users/Prekzursil/.claude/settings.json",
)

LIVE_CLAUDE_JSON_CANDIDATES = (
    "~/.claude.json",
    str(Path.home() / ".claude.json"),
    "/home/ubuntu/.claude.json",
    "C:/Users/Prekzursil/.claude.json",
    "/mnt/c/Users/Prekzursil/.claude.json",
)


def expand(path: str) -> Path:
    return Path(os.path.expanduser(path)).expanduser()


def load_json(path: Path) -> tuple[dict | list | None, str | None]:
    if not path.is_file():
        return None, "absent"
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"read-error:{type(exc).__name__}"
    if not raw.strip():
        return None, "empty"
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError:
        return None, "unparseable"
    return doc, None


def as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        low = value.strip().lower()
        if low in {"true", "yes", "on", "1", "enabled"}:
            return True
        if low in {"false", "no", "off", "0", "disabled"}:
            return False
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    return None


def enabled_map_from_obj(doc: Any) -> dict[str, bool]:
    """Read enabledPlugins from ONE object. Absence of the key is an empty map,
    not 'never loaded'. Values that are not booleans are dropped (not coerced
    into enabled).
    """
    out: dict[str, bool] = {}
    if not isinstance(doc, dict):
        return out
    raw = doc.get("enabledPlugins")
    if not isinstance(raw, dict):
        return out
    for key, val in raw.items():
        if not isinstance(key, str) or not key.strip():
            continue
        flag = as_bool(val)
        if flag is None:
            continue
        out[key.strip()] = flag
    return out


def extract_maps(settings_doc: Any, claude_doc: Any) -> dict:
    """Evidence A: both files' enablement maps, kept side by side.

    Does not pick a winner. A key present in only one file stays a mismatch.
    """
    settings_map = enabled_map_from_obj(settings_doc)
    claude_root = enabled_map_from_obj(claude_doc)
    projects: list[dict] = []
    if isinstance(claude_doc, dict) and isinstance(claude_doc.get("projects"), dict):
        for proj, body in claude_doc["projects"].items():
            projects.append(
                {
                    "project": str(proj),
                    "enabledPlugins": enabled_map_from_obj(body),
                }
            )
    return {
        "settings_json": settings_map,
        "claude_json_root": claude_root,
        "claude_json_projects": projects,
    }


def all_plugin_ids(maps: dict) -> list[str]:
    ids: set[str] = set(maps.get("settings_json") or {})
    ids.update(maps.get("claude_json_root") or {})
    for proj in maps.get("claude_json_projects") or []:
        ids.update((proj or {}).get("enabledPlugins") or {})
    return sorted(ids)


def side_by_side(maps: dict, runtime: dict[str, bool] | None = None) -> list[dict]:
    """Print enablement from every surface. Never collapse a disagreement."""
    rows = []
    runtime = runtime or {}
    for pid in all_plugin_ids(maps) or sorted(runtime):
        settings = (maps.get("settings_json") or {}).get(pid)
        root = (maps.get("claude_json_root") or {}).get(pid)
        proj_vals = []
        for proj in maps.get("claude_json_projects") or []:
            emap = (proj or {}).get("enabledPlugins") or {}
            if pid in emap:
                proj_vals.append({"project": proj.get("project"), "enabled": emap[pid]})
        rt = runtime.get(pid) if pid in runtime else None
        surfaces = [settings, root] + [p["enabled"] for p in proj_vals]
        present = [v for v in surfaces if v is not None]
        mismatch = len(set(present)) > 1 or (
            settings is not None and rt is not None and settings != rt
        ) or (
            root is not None and rt is not None and root != rt
        )
        # Absent-vs-present across the two files is also a mismatch.
        in_settings = pid in (maps.get("settings_json") or {})
        in_root = pid in (maps.get("claude_json_root") or {})
        in_proj = bool(proj_vals)
        file_presence_mismatch = in_settings != (in_root or in_proj)
        if file_presence_mismatch:
            mismatch = True
        rows.append(
            {
                "id": pid,
                "settings_json": settings,
                "claude_json_root": root,
                "claude_json_projects": proj_vals,
                "runtime_enabled": rt,
                "scope_mismatch": mismatch,
            }
        )
    return rows


def scope_mismatches(rows: list[dict]) -> list[dict]:
    """Findings only. A mismatch is never rewritten to the settings.json value."""
    findings = []
    for row in rows:
        if not row.get("scope_mismatch"):
            continue
        findings.append(
            {
                "id": row["id"],
                "settings_json": row.get("settings_json"),
                "claude_json_root": row.get("claude_json_root"),
                "claude_json_projects": row.get("claude_json_projects") or [],
                "runtime_enabled": row.get("runtime_enabled"),
                "classification": "scope-mismatch",
                "note": (
                    "Right key (enabledPlugins) disagrees across files; "
                    "not normalised to a single winner."
                ),
            }
        )
    return findings


def parse_plugin_list_json(doc: Any) -> dict[str, bool]:
    out: dict[str, bool] = {}
    plugins = None
    if isinstance(doc, dict):
        plugins = doc.get("plugins") or doc.get("installed") or doc.get("items")
    elif isinstance(doc, list):
        plugins = doc
    if not isinstance(plugins, list):
        return out
    for item in plugins:
        if not isinstance(item, dict):
            continue
        pid = item.get("id") or item.get("pluginId")
        if not pid:
            name = item.get("name") or item.get("plugin")
            market = item.get("marketplace") or item.get("source") or ""
            if isinstance(name, str) and name:
                pid = f"{name}@{market}" if market else name
        if not isinstance(pid, str) or not pid.strip():
            continue
        if "enabled" in item:
            flag = as_bool(item.get("enabled"))
        else:
            flag = as_bool(item.get("status") or item.get("state"))
        if flag is None:
            continue
        out[pid.strip()] = flag
    return out


def parse_plugin_list_text(text: str) -> dict[str, bool]:
    out: dict[str, bool] = {}
    current: str | None = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if "@" in line and not line.lower().startswith("status"):
            token = line.split()[0].strip(":-")
            if "@" in token:
                current = token
                low = line.lower()
                if "disabled" in low:
                    out[current] = False
                    current = None
                elif "enabled" in low:
                    out[current] = True
                    current = None
            continue
        if current and line.lower().startswith("status"):
            low = line.lower()
            if "disabled" in low:
                out[current] = False
            elif "enabled" in low:
                out[current] = True
            current = None
    return out


def runtime_from_capture(json_doc: Any, text: str) -> tuple[dict[str, bool], str]:
    """Parse captured `claude plugin list` without calling the binary."""
    from_json = parse_plugin_list_json(json_doc)
    from_text = parse_plugin_list_text(text)
    if from_json and from_text and from_json != from_text:
        # Prefer JSON; keep the disagreement as a parser finding rather than
        # silently picking one.
        return from_json, "json-and-text-disagree"
    if from_json:
        return from_json, "json"
    if from_text:
        return from_text, "text"
    return {}, "empty"


def assert_read_only_argv(argv: tuple[str, ...] | list[str]) -> list[str]:
    """Refuse any argv that could enable/disable/install/remove a plugin."""
    args = [str(a) for a in argv]
    lower = [a.lower() for a in args]
    for tok in MUTATING_SUBCOMMANDS:
        # `plugin list` is the only allowed plugin subcommand here.
        if tok == "plugin":
            continue
        if tok in lower:
            raise ValueError(f"refusing mutating argv token {tok!r}: {args}")
    if "plugin" in lower:
        idx = lower.index("plugin")
        rest = lower[idx + 1 :]
        if rest and rest[0] != "list":
            raise ValueError(f"refusing non-list plugin argv: {args}")
    return args


def attempt_live_plugin_list(timeout: int = 20) -> dict:
    """Evidence B live half. Never mutates. Missing binary is recorded, not faked."""
    binary = shutil.which("claude")
    argv = assert_read_only_argv(PLUGIN_LIST_JSON_ARGV if binary else PLUGIN_LIST_ARGV)
    result: dict[str, Any] = {
        "attempted": True,
        "ok": False,
        "binary": binary,
        "argv": argv,
        "exit_code": None,
        "parsed": {},
        "reason": None,
        "stdout_tail": "",
    }
    if not binary:
        result["reason"] = "claude-binary-absent"
        return result
    try:
        proc = subprocess.run(
            [binary, "plugin", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        result["reason"] = type(exc).__name__
        return result
    result["exit_code"] = proc.returncode
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    result["stdout_tail"] = text[-2000:]
    parsed = {}
    try:
        doc = json.loads(proc.stdout or "")
        parsed = parse_plugin_list_json(doc)
    except json.JSONDecodeError:
        parsed = parse_plugin_list_text(text)
    result["parsed"] = parsed
    if proc.returncode == 0 and parsed:
        result["ok"] = True
        result["reason"] = "parsed"
    elif proc.returncode == 0:
        result["reason"] = "empty-parse"
    else:
        result["reason"] = f"exit:{proc.returncode}"
    return result


def which_map_matches_runtime(maps: dict, runtime: dict[str, bool]) -> dict:
    """Independently: which enablement map equals the runtime list?

    A map matches when every runtime id has the same bool, and the map does
    not claim the opposite for any of those ids. Extra map-only ids do not
    disqualify, but extra runtime-only ids miss.
    """

    def score(label: str, emap: dict[str, bool], extra: dict | None = None) -> dict:
        hits = 0
        misses = 0
        contradictions = 0
        for pid, enabled in runtime.items():
            if pid in emap:
                if emap[pid] == enabled:
                    hits += 1
                else:
                    contradictions += 1
            else:
                misses += 1
        return {
            "label": label,
            "hits": hits,
            "misses": misses,
            "contradictions": contradictions,
            "matches": contradictions == 0 and misses == 0 and bool(runtime),
            "extra": extra or {},
        }

    scored = [
        score("settings.json enabledPlugins", maps.get("settings_json") or {}),
        score("~/.claude.json root enabledPlugins", maps.get("claude_json_root") or {}),
    ]
    for proj in maps.get("claude_json_projects") or []:
        scored.append(
            score(
                f"~/.claude.json projects[{proj.get('project')}] enabledPlugins",
                proj.get("enabledPlugins") or {},
                extra={"project": proj.get("project")},
            )
        )
    winners = [s for s in scored if s["matches"]]
    return {
        "runtime_plugin_count": len(runtime),
        "scored": scored,
        "winners": [s["label"] for s in winners],
        "authoritative": winners[0]["label"] if len(winners) == 1 else None,
        "split": len(winners) > 1,
        "none_match": len(winners) == 0,
    }


def plugin_contributions(plugin_root: Path, plugin_id: str) -> dict:
    commands: list[str] = []
    workflows: list[str] = []
    skills: list[str] = []
    if plugin_root.is_dir():
        for p in sorted(plugin_root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(plugin_root).as_posix()
            low = rel.lower()
            if "/commands/" in f"/{low}" or low.startswith("commands/"):
                commands.append(rel)
            elif "/workflows/" in f"/{low}" or low.startswith("workflows/"):
                workflows.append(rel)
            elif p.name == "SKILL.md":
                skills.append(rel)
    return {
        "id": plugin_id,
        "path": str(plugin_root),
        "present": plugin_root.is_dir(),
        "commands": commands,
        "workflows": workflows,
        "skills": skills,
        "contributes_commands": bool(commands),
        "contributes_workflows": bool(workflows) or bool(commands),
    }


def inventory_plugins(market_root: Path, market_name: str) -> list[dict]:
    rows = []
    plugins_dir = market_root / "plugins"
    if not plugins_dir.is_dir():
        return rows
    for child in sorted(plugins_dir.iterdir()):
        if not child.is_dir():
            continue
        pid = f"{child.name}@{market_name}"
        rows.append(plugin_contributions(child, pid))
    return rows


def inventory_marketplaces(home: Path) -> list[dict]:
    root = home / ".claude" / "plugins" / "marketplaces"
    rows = []
    if not root.is_dir():
        return rows
    for market in sorted(root.iterdir()):
        if not market.is_dir():
            continue
        manifest = market / ".claude-plugin" / "marketplace.json"
        doc, err = load_json(manifest)
        plugins = inventory_plugins(market, market.name)
        rows.append(
            {
                "name": market.name,
                "path": str(market),
                "manifest_present": manifest.is_file(),
                "manifest_error": err,
                "declared_plugin_count": (
                    len(doc.get("plugins") or []) if isinstance(doc, dict) else None
                ),
                "installed_plugin_count": len(plugins),
                "plugins": plugins,
            }
        )
    return rows


def host_path_census(candidates: tuple[str, ...]) -> list[dict]:
    rows = []
    for raw in candidates:
        path = expand(raw)
        rows.append(
            {
                "declared": raw,
                "resolved": str(path),
                "exists": path.exists(),
                "is_file": path.is_file(),
                "bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    return rows


def live_host(repo: Path) -> dict:
    settings = host_path_census(LIVE_SETTINGS_CANDIDATES)
    claude_json = host_path_census(LIVE_CLAUDE_JSON_CANDIDATES)
    registry = host_path_census(REGISTRY_CANDIDATES)
    plugin_roots = []
    for raw in (
        "~/.claude/plugins",
        str(Path.home() / ".claude" / "plugins"),
        "/home/ubuntu/.claude/plugins",
    ):
        path = expand(raw)
        plugin_roots.append(
            {
                "declared": raw,
                "resolved": str(path),
                "exists": path.is_dir(),
            }
        )
    live_list = attempt_live_plugin_list()
    return {
        "home": str(Path.home()),
        "claude_binary": shutil.which("claude"),
        "settings_json_candidates": settings,
        "claude_json_candidates": claude_json,
        "registry_candidates": registry,
        "plugin_tree_candidates": plugin_roots,
        "claude_plugin_list": live_list,
        "any_settings_present": any(r["is_file"] for r in settings),
        "any_claude_json_present": any(r["is_file"] for r in claude_json),
        "any_registry_present": any(r["is_file"] for r in registry),
        "repo": str(repo),
    }


def classify_pair(maps: dict, runtime: dict[str, bool], enabled_id: str, disabled_id: str) -> dict:
    """Both-states: known-enabled vs known-disabled, toggle nothing."""
    settings = maps.get("settings_json") or {}
    root = maps.get("claude_json_root") or {}
    return {
        "enabled_id": enabled_id,
        "disabled_id": disabled_id,
        "settings_enabled": settings.get(enabled_id),
        "settings_disabled": settings.get(disabled_id),
        "runtime_enabled": runtime.get(enabled_id),
        "runtime_disabled": runtime.get(disabled_id),
        "wrong_file_enabled": root.get(enabled_id),
        "wrong_file_disabled": root.get(disabled_id),
        "settings_distinguishes": (
            settings.get(enabled_id) is True and settings.get(disabled_id) is False
        ),
        "runtime_distinguishes": (
            runtime.get(enabled_id) is True and runtime.get(disabled_id) is False
        ),
        "wrong_file_inverts": (
            root.get(enabled_id) is False and root.get(disabled_id) is True
        ),
        "settings_matches_runtime": (
            settings.get(enabled_id) == runtime.get(enabled_id)
            and settings.get(disabled_id) == runtime.get(disabled_id)
            and settings.get(enabled_id) is not None
        ),
        "wrong_file_matches_runtime": (
            root.get(enabled_id) == runtime.get(enabled_id)
            and root.get(disabled_id) == runtime.get(disabled_id)
            and root.get(enabled_id) is not None
        ),
    }
