"""Both-states fixtures for the two measured silent-loss classes.

loaded: skill reachable and hook fires.
skill-repo-not-live: repo has a valid skill.council declaration; live A1
    tree does not. Loader (run on live) cannot reach the skill.
hooks-unloaded: plugin.json installed=true, hook file listed and valid,
    hooks_enabled=false so the dispatcher stays empty.

All declaration JSON in every fixture is syntactically valid (anti-tautology).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

SKILL_REL = "capabilities/skills/skill.council.skill.json"
HOOK_REL = "capabilities/hooks/hook.pre-tool.hook.json"
PLUGIN_REL = "plugin.json"

SKILL_BODY = {
    "id": "skill.council",
    "kind": "skill",
    "enabled": True,
    "canary_token": "council-live",
    "instructions": "Invoke Architect, Skeptic, Pragmatist, Critic as static prompt sections.",
    "origin": "ARC-0008-fixture",
}
HOOK_BODY = {
    "id": "hook.pre-tool",
    "kind": "hook",
    "event": "pre-tool",
    "enabled": True,
    "script": "hooks/pre-tool.sh",
    "canary_token": "hook-live",
}
PLUGIN_ON = {
    "id": "plugin.harness",
    "kind": "plugin",
    "installed": True,
    "hooks_enabled": True,
    "notes": "Test-only estate overlay; not in A1 DESIGN file_set.",
}
PLUGIN_HOOKS_OFF = {
    **PLUGIN_ON,
    "hooks_enabled": False,
    "notes": "Plugin installed; hooks unloaded. Seeded class IMP-0039 / ARC-0008.",
}


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _wipe(root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)


def _write_live(live: Path, *, list_skill: bool, plugin: dict[str, Any]) -> None:
    files = [HOOK_REL]
    if list_skill:
        files = [SKILL_REL, HOOK_REL]
        _write(live / SKILL_REL, SKILL_BODY)
    _write(live / HOOK_REL, HOOK_BODY)
    _write(live / PLUGIN_REL, plugin)
    _write(
        live / "MANIFEST.json",
        {
            "architecture_id": "A1",
            "files": files,
            "notes": "Files not listed are not loaded (DESIGN precedence.unlisted_file).",
        },
    )


def write_loaded(root: Path) -> Path:
    _wipe(root)
    repo = root / "repo"
    live = root / "live"
    _write(repo / SKILL_REL, SKILL_BODY)
    _write_live(live, list_skill=True, plugin=PLUGIN_ON)
    return root


def write_skill_repo_not_live(root: Path) -> Path:
    _wipe(root)
    repo = root / "repo"
    live = root / "live"
    _write(repo / SKILL_REL, SKILL_BODY)
    _write_live(live, list_skill=False, plugin=PLUGIN_ON)
    return root


def write_hooks_unloaded(root: Path) -> Path:
    _wipe(root)
    repo = root / "repo"
    live = root / "live"
    _write(repo / SKILL_REL, SKILL_BODY)
    _write_live(live, list_skill=True, plugin=PLUGIN_HOOKS_OFF)
    return root


def _exercise(live: Path, scratch: Path) -> dict[str, Any]:
    from runtime import (
        SKILL_ID,
        canary_fired,
        declaration_files_valid,
        dispatch_skill,
        fire_hook,
        load_plane,
    )

    plane = load_plane(live)
    skill = dispatch_skill(plane, scratch)
    hook = fire_hook(plane, scratch)
    valid, bad = declaration_files_valid(live.parent if (live.parent / "repo").is_dir() else live)
    repo_skill = live.parent / "repo" / SKILL_REL
    live_skill = live / SKILL_REL
    plugin = plane.get("plugin") or {}
    return {
        "ok": plane.get("ok"),
        "errors": plane.get("errors"),
        "warnings": plane.get("warnings"),
        "loaded_ids": plane.get("loaded_ids"),
        "tool_inventory": plane.get("tool_inventory"),
        "hook_inventory": plane.get("hook_inventory"),
        "log_lines": plane.get("log_lines"),
        "plugin_installed": plugin.get("installed"),
        "plugin_hooks_enabled": plugin.get("hooks_enabled"),
        "skill": skill,
        "hook": hook,
        "skill_reachable": bool(skill.get("reachable") and canary_fired(skill["canary"])),
        "hook_fired": bool(hook.get("fired") and canary_fired(hook["canary"])),
        "declarations_valid": valid,
        "declaration_parse_errors": bad,
        "repo_skill_exists": repo_skill.is_file(),
        "live_skill_exists": live_skill.is_file(),
        "file_existence_would_pass_skill": repo_skill.is_file(),
        "file_existence_would_pass_hook": (live / HOOK_REL).is_file()
        and (live / PLUGIN_REL).is_file(),
    }


def run_scenario() -> dict[str, Any]:
    from runtime import SKILL_ID, HOOK_ID

    loaded_root = write_loaded(FIX / "loaded")
    skill_root = write_skill_repo_not_live(FIX / "skill-repo-not-live")
    hooks_root = write_hooks_unloaded(FIX / "hooks-unloaded")

    good = _exercise(loaded_root / "live", loaded_root / "scratch")
    skill_bad = _exercise(skill_root / "live", skill_root / "scratch")
    hooks_bad = _exercise(hooks_root / "live", hooks_root / "scratch")

    silent_on_loaded = (
        good["skill_reachable"] is True
        and good["hook_fired"] is True
        and SKILL_ID in (good["tool_inventory"] or [])
        and HOOK_ID in (good["hook_inventory"] or [])
        and good["errors"] == []
        and good["declarations_valid"] is True
    )
    skill_fires_unloaded = (
        skill_bad["skill_reachable"] is False
        and SKILL_ID not in (skill_bad["tool_inventory"] or [])
        and skill_bad["repo_skill_exists"] is True
        and skill_bad["live_skill_exists"] is False
        and skill_bad["file_existence_would_pass_skill"] is True
        and skill_bad["declarations_valid"] is True
        and (skill_root / "repo" / SKILL_REL).is_file()
    )
    hooks_fires_unloaded = (
        hooks_bad["hook_fired"] is False
        and HOOK_ID not in (hooks_bad["hook_inventory"] or [])
        and hooks_bad["plugin_installed"] is True
        and hooks_bad["plugin_hooks_enabled"] is False
        and hooks_bad["file_existence_would_pass_hook"] is True
        and hooks_bad["declarations_valid"] is True
        and SKILL_ID in (hooks_bad["tool_inventory"] or [])
    )
    anti_tautology = (
        skill_fires_unloaded
        and hooks_fires_unloaded
        and skill_bad["declarations_valid"]
        and hooks_bad["declarations_valid"]
        and good["declarations_valid"]
    )
    return {
        "pass": bool(silent_on_loaded and skill_fires_unloaded and hooks_fires_unloaded and anti_tautology),
        "silent_on_loaded": silent_on_loaded,
        "skill_class_fires_on_unloaded": skill_fires_unloaded,
        "hooks_class_fires_on_unloaded": hooks_fires_unloaded,
        "anti_tautology": anti_tautology,
        "loaded": good,
        "skill_repo_not_live": skill_bad,
        "hooks_unloaded": hooks_bad,
    }


if __name__ == "__main__":
    import sys

    out = run_scenario()
    print(json.dumps({k: out[k] for k in sorted(out) if k != "pass"}, indent=2, sort_keys=True, default=str)[:4000])
    print(f"pass={out.get('pass')} silent_on_loaded={out.get('silent_on_loaded')} "
          f"skill_unloaded={out.get('skill_class_fires_on_unloaded')} "
          f"hooks_unloaded={out.get('hooks_class_fires_on_unloaded')} "
          f"anti_tautology={out.get('anti_tautology')}")
    sys.exit(0 if out.get("pass") else 1)
