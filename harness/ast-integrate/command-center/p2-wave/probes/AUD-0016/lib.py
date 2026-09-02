"""AUD-0016 plugin enablement map vs command/skill reachability.

Probe 1 reads enabledPlugins from each settings file (user / project / local)
and records the inert trap at ~/.claude.json. It never walks plugin trees.

Probe 2 walks installed plugin trees for commands/ and skills/ that actually
exist on disk. It never opens settings.json, settings.local.json, or
.enabledPlugins.

The known-disabled control is agentbridge@estate: probe 1 must report it
disabled (user=false; the trap file saying true must not win) and probe 2
must report it unreachable. A contrasting live-skill-plugin@estate must
resolve, otherwise the reachability probe measures nothing.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0016"
OUT_REL = "command-center/audit/AUD-0016-plugin-enablement-map.json"
SCHEMA_REL = "command-center/schema/audit-finding.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0016 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "For every installed plugin, what is its enabled state at user, project, "
    "and local scope, and which reported state is contradicted by whether "
    "its commands and skills are actually reachable this session?"
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0016/probe1_enabled_plugins_map.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0016/probe2_skill_command_reachability.py"
)

AGENTBRIDGE = "agentbridge@estate"
LIVE_SKILL = "live-skill-plugin@estate"
GREEN_NOT_LIVE = "green-not-live@estate"
PROJECT_ONLY = "project-only-plugin@estate"
LOCAL_ONLY = "local-only-plugin@estate"
SCOPE_MISMATCH = "scope-mismatch-plugin@estate"
TRAP_ONLY = "trap-only-plugin@estate"

FIXTURE_HOME_REL = (
    "command-center/p2-wave/probes/AUD-0016/fixtures/estate/user-home"
)
FIXTURE_PROJECT_REL = (
    "command-center/p2-wave/probes/AUD-0016/fixtures/estate/project"
)
FIXTURE_HOME = REPO / FIXTURE_HOME_REL
FIXTURE_PROJECT = REPO / FIXTURE_PROJECT_REL

# Highest-wins among the three live scopes. The trap file never participates.
WIN_ORDER = ("local", "project", "user")
SCOPE_FILES = {
    "user": (".claude", "settings.json"),
    "project": (".claude", "settings.json"),
    "local": (".claude", "settings.local.json"),
    "trap": (".claude.json",),
}


def dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def rel_to_repo(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(path)


def load_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, "absent"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"{type(exc).__name__}"
    if not isinstance(data, dict):
        return None, "not-object"
    return data, None


def parse_enabled_plugins(data: dict[str, Any] | None) -> dict[str, bool]:
    """Return plugin-id -> bool. Other settings keys are discarded (no secrets)."""
    if not isinstance(data, dict):
        return {}
    raw = data.get("enabledPlugins")
    out: dict[str, bool] = {}
    if isinstance(raw, dict):
        for key, val in raw.items():
            out[str(key)] = bool(val)
    elif isinstance(raw, list):
        for item in raw:
            out[str(item)] = True
    return dict(sorted(out.items()))


def _scope_path(root: Path, scope: str) -> Path:
    parts = SCOPE_FILES[scope]
    return root.joinpath(*parts)


def read_scope_maps(home: Path, project: Path) -> dict[str, Any]:
    """Probe 1 field: enabledPlugins maps only. Does not walk plugin trees."""
    files = {
        "trap": _scope_path(home, "trap"),
        "user": _scope_path(home, "user"),
        "project": _scope_path(project, "project"),
        "local": _scope_path(project, "local"),
    }
    rows: dict[str, Any] = {}
    maps: dict[str, dict[str, bool]] = {}
    for scope, path in files.items():
        data, err = load_json_object(path)
        enabled = parse_enabled_plugins(data)
        maps[scope] = enabled
        rows[scope] = {
            "path": rel_to_repo(path) if path.exists() or True else str(path),
            "abs_path": str(path),
            "present": path.is_file(),
            "parse_error": err,
            "enabledPlugins": enabled,
            "declared_true": sorted(k for k, v in enabled.items() if v),
            "declared_false": sorted(k for k, v in enabled.items() if not v),
        }
        # Prefer repo-relative when the file is inside the worktree.
        try:
            rows[scope]["path"] = path.resolve().relative_to(REPO.resolve()).as_posix()
        except ValueError:
            rows[scope]["path"] = str(path)
    ids: set[str] = set()
    for enabled in maps.values():
        ids.update(enabled)
    return {
        "files": rows,
        "maps": maps,
        "plugin_ids": sorted(ids),
    }


def declared_at(maps: dict[str, dict[str, bool]], plugin_id: str, scope: str) -> bool | None:
    table = maps.get(scope) or {}
    if plugin_id not in table:
        return None
    return bool(table[plugin_id])


def winning_declared(maps: dict[str, dict[str, bool]], plugin_id: str) -> dict[str, Any]:
    for scope in WIN_ORDER:
        val = declared_at(maps, plugin_id, scope)
        if val is not None:
            return {
                "winning": val,
                "winning_scope": scope,
                "declared_enabled": val is True,
            }
    return {
        "winning": None,
        "winning_scope": None,
        "declared_enabled": False,
    }


def scope_states(maps: dict[str, dict[str, bool]], plugin_id: str) -> dict[str, Any]:
    user = declared_at(maps, plugin_id, "user")
    project = declared_at(maps, plugin_id, "project")
    local = declared_at(maps, plugin_id, "local")
    trap = declared_at(maps, plugin_id, "trap")
    explicit = [v for v in (user, project, local) if v is not None]
    mismatch = (True in explicit) and (False in explicit)
    partial = 0 < len(explicit) < 3
    win = winning_declared(maps, plugin_id)
    return {
        "id": plugin_id,
        "user": user,
        "project": project,
        "local": local,
        "trap": trap,
        "scope_mismatch": mismatch,
        "scope_partial": partial,
        **win,
    }


def _nonempty_files(root: Path, suffixes: set[str]) -> list[str]:
    if not root.is_dir():
        return []
    found: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in suffixes:
            continue
        if path.stat().st_size <= 0:
            continue
        try:
            found.append(path.relative_to(root).as_posix())
        except ValueError:
            found.append(str(path))
    return found


def _listed_paths(manifest: dict[str, Any], key: str) -> list[str]:
    raw = manifest.get(key)
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str) and raw:
        return [raw]
    return []


def inspect_plugin_tree(plugin_dir: Path) -> dict[str, Any]:
    """Probe 2 field: commands/skills on disk. Does not read enabledPlugins."""
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    data, err = load_json_object(manifest_path)
    manifest = data or {}
    name = str(manifest.get("name") or plugin_dir.name)
    plugin_id = plugin_dir.name
    listed_commands = _listed_paths(manifest, "commands")
    listed_skills = _listed_paths(manifest, "skills")
    command_files = _nonempty_files(plugin_dir / "commands", {".md", ".py", ".js", ".sh", ".json"})
    skill_root = plugin_dir / "skills"
    skill_files: list[str] = []
    if skill_root.is_dir():
        for path in sorted(skill_root.rglob("SKILL.md")):
            if path.is_file() and path.stat().st_size > 0:
                skill_files.append(path.relative_to(plugin_dir).as_posix())
        for path in sorted(skill_root.glob("*.md")):
            rel = path.relative_to(plugin_dir).as_posix()
            if rel not in skill_files and path.stat().st_size > 0:
                skill_files.append(rel)
    listed_missing: list[str] = []
    for rel in listed_commands + listed_skills:
        if not (plugin_dir / rel).is_file():
            listed_missing.append(rel)
    reachable = bool(command_files or skill_files)
    return {
        "id": plugin_id,
        "name": name,
        "path": rel_to_repo(plugin_dir),
        "manifest_present": manifest_path.is_file(),
        "manifest_parse_error": err,
        "listed_commands": listed_commands,
        "listed_skills": listed_skills,
        "command_files": command_files,
        "skill_files": skill_files,
        "listed_missing": listed_missing,
        "reachable": reachable,
    }


def walk_installed(installed_root: Path) -> dict[str, Any]:
    """Probe 2 walker. Settings files are not opened."""
    plugins: list[dict[str, Any]] = []
    present = installed_root.is_dir()
    if present:
        for child in sorted(installed_root.iterdir()):
            if not child.is_dir():
                continue
            marker = child / ".claude-plugin" / "plugin.json"
            if not marker.is_file():
                continue
            plugins.append(inspect_plugin_tree(child))
    return {
        "installed_root": rel_to_repo(installed_root),
        "installed_root_present": present,
        "plugins": plugins,
        "plugin_ids": [p["id"] for p in plugins],
        "reachable_ids": sorted(p["id"] for p in plugins if p["reachable"]),
        "unreachable_ids": sorted(p["id"] for p in plugins if not p["reachable"]),
    }


def live_home() -> Path:
    override = os.environ.get("AUD0016_LIVE_HOME", "").strip()
    if override:
        return Path(override)
    return Path.home()


def live_project() -> Path:
    override = os.environ.get("AUD0016_LIVE_PROJECT", "").strip()
    if override:
        return Path(override)
    return REPO


def try_claude_plugin_list() -> dict[str, Any]:
    """Observational only. Never required for delivery. Output is truncated."""
    exe = shutil.which("claude")
    if not exe:
        return {
            "cli_present": False,
            "rc": None,
            "stdout_tail": "",
            "note": "vendor Claude CLI absent on this worktree",
        }
    try:
        proc = subprocess.run(
            [exe, "plugin", "list"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "cli_present": True,
            "executable": exe,
            "rc": 124 if isinstance(exc, subprocess.TimeoutExpired) else 127,
            "stdout_tail": f"{type(exc).__name__}",
            "note": "claude plugin list did not complete",
        }
    blob = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return {
        "cli_present": True,
        "executable": exe,
        "rc": proc.returncode,
        "stdout_tail": blob[-800:],
        "note": "live CLI invoked read-only; not a probe of enabledPlugins files",
    }


def probe1_payload() -> dict[str, Any]:
    fixture = read_scope_maps(FIXTURE_HOME, FIXTURE_PROJECT)
    live = read_scope_maps(live_home(), live_project())
    fmap = fixture["maps"]
    agent = scope_states(fmap, AGENTBRIDGE)
    trap_only = scope_states(fmap, TRAP_ONLY)
    local_only = scope_states(fmap, LOCAL_ONLY)
    project_only = scope_states(fmap, PROJECT_ONLY)
    live_skill = scope_states(fmap, LIVE_SKILL)
    trap_ignored = agent["trap"] is True and agent["declared_enabled"] is False
    all_three = (
        local_only["local"] is True
        and project_only["project"] is True
        and live_skill["user"] is True
    )
    agent_disabled = agent["declared_enabled"] is False and agent["user"] is False
    trap_only_not_winning = trap_only["declared_enabled"] is False
    control = {
        "agentbridge_disabled": agent_disabled,
        "trap_says_agentbridge_true": agent["trap"] is True,
        "trap_ignored": trap_ignored,
        "trap_only_plugin_does_not_win": trap_only_not_winning,
        "all_three_scopes_read": all_three,
        "ok": agent_disabled and trap_ignored and trap_only_not_winning and all_three,
    }
    return {
        "probe": "probe1-enabled-plugins-map",
        "unit_id": UNIT,
        "scopes_read": ["trap", "user", "project", "local"],
        "win_order": list(WIN_ORDER),
        "fixture": {
            "home": FIXTURE_HOME_REL,
            "project": FIXTURE_PROJECT_REL,
            "files": {
                k: {
                    "path": v["path"],
                    "present": v["present"],
                    "parse_error": v["parse_error"],
                    "enabledPlugins": v["enabledPlugins"],
                }
                for k, v in fixture["files"].items()
            },
            "plugin_ids": fixture["plugin_ids"],
            "agentbridge": agent,
            "trap_only_plugin": trap_only,
            "local_only_plugin": local_only,
            "project_only_plugin": project_only,
            "live_skill_plugin": live_skill,
        },
        "live": {
            "home": str(live_home()),
            "project": str(live_project()),
            "user_settings_present": live["files"]["user"]["present"],
            "trap_present": live["files"]["trap"]["present"],
            "project_settings_present": live["files"]["project"]["present"],
            "local_settings_present": live["files"]["local"]["present"],
            "files": {
                k: {
                    "path": v["path"],
                    "present": v["present"],
                    "parse_error": v["parse_error"],
                    "enabledPlugins": v["enabledPlugins"],
                }
                for k, v in live["files"].items()
            },
            "plugin_ids": live["plugin_ids"],
        },
        "claude_plugin_list": try_claude_plugin_list(),
        "control": control,
    }


def probe2_payload() -> dict[str, Any]:
    fixture = walk_installed(
        FIXTURE_HOME / ".claude" / "plugins" / "installed"
    )
    live = walk_installed(live_home() / ".claude" / "plugins" / "installed")
    by_id = {p["id"]: p for p in fixture["plugins"]}
    agent = by_id.get(AGENTBRIDGE)
    live_skill = by_id.get(LIVE_SKILL)
    green = by_id.get(GREEN_NOT_LIVE)
    agent_installed = agent is not None
    agent_unreachable = bool(agent) and agent["reachable"] is False
    live_ok = bool(live_skill) and live_skill["reachable"] is True
    green_unreach = bool(green) and green["reachable"] is False
    distinguished = agent_installed and agent_unreachable and live_ok
    control = {
        "agentbridge_installed": agent_installed,
        "agentbridge_reachable": False if agent is None else agent["reachable"],
        "live_skill_reachable": False if live_skill is None else live_skill["reachable"],
        "green_not_live_reachable": False if green is None else green["reachable"],
        "distinguished": distinguished,
        "ok": distinguished and green_unreach,
    }
    return {
        "probe": "probe2-skill-command-reachability",
        "unit_id": UNIT,
        "fixture": {
            "installed_root": fixture["installed_root"],
            "installed_root_present": fixture["installed_root_present"],
            "plugins": fixture["plugins"],
            "plugin_ids": fixture["plugin_ids"],
            "reachable_ids": fixture["reachable_ids"],
            "unreachable_ids": fixture["unreachable_ids"],
            "agentbridge": agent,
            "live_skill_plugin": live_skill,
            "green_not_live": green,
        },
        "live": {
            "installed_root": live["installed_root"],
            "installed_root_present": live["installed_root_present"],
            "plugins": live["plugins"],
            "plugin_ids": live["plugin_ids"],
            "reachable_ids": live["reachable_ids"],
            "unreachable_ids": live["unreachable_ids"],
        },
        "control": control,
    }


def classify_row(declared: dict[str, Any], reach: dict[str, Any] | None) -> dict[str, Any]:
    reachable = bool(reach and reach.get("reachable"))
    enabled = bool(declared.get("declared_enabled"))
    if enabled and reachable:
        kind = "enabled-live"
    elif enabled and not reachable:
        kind = "green-not-live"
    elif (not enabled) and reachable:
        kind = "unexpected-live"
    else:
        kind = "disabled"
    tags = [kind]
    if declared.get("scope_mismatch"):
        tags.append("scope-mismatch")
    if declared.get("trap") is True and not enabled:
        tags.append("trap-disagreement")
    return {
        **declared,
        "installed": reach is not None,
        "reachable": reachable,
        "command_files": (reach or {}).get("command_files") or [],
        "skill_files": (reach or {}).get("skill_files") or [],
        "listed_missing": (reach or {}).get("listed_missing") or [],
        "classification": kind,
        "tags": tags,
    }


def join_estate(p1_estate: dict[str, Any], p2_estate: dict[str, Any], maps: dict[str, dict[str, bool]]) -> list[dict[str, Any]]:
    reach_by = {p["id"]: p for p in (p2_estate.get("plugins") or [])}
    ids = set(p1_estate.get("plugin_ids") or []) | set(reach_by)
    rows = [classify_row(scope_states(maps, pid), reach_by.get(pid)) for pid in sorted(ids)]
    return rows


def census() -> dict[str, Any]:
    p1 = probe1_payload()
    p2 = probe2_payload()
    fixture_maps = {
        k: v["enabledPlugins"] for k, v in p1["fixture"]["files"].items()
    }
    fixture_rows = join_estate(p1["fixture"], p2["fixture"], fixture_maps)
    live_maps = {k: v["enabledPlugins"] for k, v in p1["live"]["files"].items()}
    live_rows = join_estate(p1["live"], p2["live"], live_maps)

    def count(rows: list[dict[str, Any]], kind: str) -> int:
        return sum(1 for r in rows if r["classification"] == kind)

    def tagged(rows: list[dict[str, Any]], tag: str) -> int:
        return sum(1 for r in rows if tag in r["tags"])

    contradictions = [
        r for r in fixture_rows if r["classification"] in {"green-not-live", "unexpected-live"}
    ]
    return {
        "probe1": p1,
        "probe2": p2,
        "fixture_rows": fixture_rows,
        "live_rows": live_rows,
        "counts": {
            "fixture_plugins": len(fixture_rows),
            "live_plugins": len(live_rows),
            "fixture_green_not_live": count(fixture_rows, "green-not-live"),
            "fixture_unexpected_live": count(fixture_rows, "unexpected-live"),
            "fixture_enabled_live": count(fixture_rows, "enabled-live"),
            "fixture_disabled": count(fixture_rows, "disabled"),
            "fixture_scope_mismatch": tagged(fixture_rows, "scope-mismatch"),
            "fixture_trap_disagreement": tagged(fixture_rows, "trap-disagreement"),
            "live_green_not_live": count(live_rows, "green-not-live"),
            "live_contradictions": sum(
                1
                for r in live_rows
                if r["classification"] in {"green-not-live", "unexpected-live"}
            ),
            "headline_contradictions": len(contradictions),
        },
        "contradiction_ids": [r["id"] for r in contradictions],
    }
