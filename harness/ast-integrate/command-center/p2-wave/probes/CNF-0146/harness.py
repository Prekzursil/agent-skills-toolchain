#!/usr/bin/env python3
"""Fresh USERPROFILE-redirected plugin install + Codex-strict hook loader.

Two independent live signals (catalog evidence_requirement):
  (a) a beacon written only by the hook script under .cnf0146-runtime/fired/
  (b) the loader inventory at .cnf0146-runtime/inventory.json
settings.json / file presence are claims, never either signal.

Codex-measured hole (spec 11303): a top-level $schema key on hooks.json is
deny_unknown_fields → ZERO hooks loaded while files remain on disk.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE_SRC = HERE / "package"
EVENTS = ("SessionStart", "PreToolUse", "Stop")
ALLOWED_HOOK_KEYS = frozenset({"hooks"})
DEV_MARKERS = (
    ".claude/settings.json",
    ".codex/hooks.json",
    ".cursor/argv.json",
    "AppData/Roaming/Claude/claude.json",
)
PLUGIN_NAME = "cnf0146-canary"


class IsolationError(RuntimeError):
    pass


def windows_env(profile: Path) -> dict[str, str]:
    env = os.environ.copy()
    profile = profile.resolve()
    env["USERPROFILE"] = str(profile)
    env["HOME"] = str(profile)
    env["HOMEDRIVE"] = "C:"
    env["HOMEPATH"] = "\\Users\\" + profile.name
    env["APPDATA"] = str(profile / "AppData" / "Roaming")
    env["LOCALAPPDATA"] = str(profile / "AppData" / "Local")
    env["USERNAME"] = profile.name
    env["USER"] = profile.name
    return env


def assert_isolated(profile: Path) -> None:
    real = Path.home().resolve()
    got = profile.resolve()
    if got == real:
        raise IsolationError(f"profile equals host HOME: {got}")
    if real in got.parents:
        raise IsolationError(f"profile nested under host HOME: {got}")


def make_fresh_profile(root: Path, name: str = "cnf0146-fresh") -> Path:
    profile = root / "Users" / name
    if profile.exists():
        shutil.rmtree(profile)
    (profile / "AppData" / "Roaming").mkdir(parents=True)
    (profile / "AppData" / "Local").mkdir(parents=True)
    assert_isolated(profile)
    return profile


def plant_developer_profile(root: Path) -> Path:
    dev = root / "Users" / "developer-loaded"
    if dev.exists():
        shutil.rmtree(dev)
    for rel in DEV_MARKERS:
        path = dev / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"developer-harness {rel}\n", encoding="utf-8")
    return dev


def contamination(profile: Path) -> list[str]:
    return [rel for rel in DEV_MARKERS if (profile / rel).exists()]


def plugin_dir(profile: Path) -> Path:
    return profile / ".claude" / "plugins" / PLUGIN_NAME


def settings_path(profile: Path) -> Path:
    return profile / ".claude" / "settings.json"


def hooks_path(profile: Path) -> Path:
    return plugin_dir(profile) / "hooks" / "hooks.json"


def inventory_path(profile: Path) -> Path:
    return profile / ".cnf0146-runtime" / "inventory.json"


def beacon_path(profile: Path, event: str) -> Path:
    return profile / ".cnf0146-runtime" / "fired" / f"{event}.beacon"


def listing_says_installed(profile: Path) -> bool:
    """Disqualified acceptance signal: files exist. Passes on unloaded hooks."""
    return hooks_path(profile).is_file() and settings_path(profile).is_file()


def install_plugin(profile: Path, *, inject_schema: bool = False) -> dict:
    """Copy package into the isolated profile. Does not write beacons or inventory."""
    assert_isolated(profile)
    dest = plugin_dir(profile)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(PACKAGE_SRC, dest)
    doc = json.loads(hooks_path(profile).read_text(encoding="utf-8"))
    python = sys.executable
    hooks_dir = dest / "hooks"
    for _event, matchers in doc.get("hooks", {}).items():
        for matcher in matchers:
            for hook in matcher.get("hooks", []):
                script = hooks_dir / hook["script"]
                hook["command"] = [python, str(script)]
    if inject_schema:
        mutated = {"$schema": "https://json-schema.org/draft/2020-12/schema"}
        mutated.update(doc)
        doc = mutated
    hooks_path(profile).write_text(
        json.dumps(doc, indent=2) + "\n", encoding="utf-8"
    )
    settings = {
        "enabledPlugins": {PLUGIN_NAME: True},
        "claim": "installer-success-is-not-hook-execution",
    }
    settings_path(profile).parent.mkdir(parents=True, exist_ok=True)
    settings_path(profile).write_text(
        json.dumps(settings, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "plugin_dir": str(dest),
        "settings": str(settings_path(profile)),
        "hooks": str(hooks_path(profile)),
        "inject_schema": inject_schema,
        "listing_says_installed": listing_says_installed(profile),
    }


def uninstall_plugin(profile: Path) -> None:
    dest = plugin_dir(profile)
    if dest.exists():
        shutil.rmtree(dest)
    sp = settings_path(profile)
    if sp.exists():
        sp.unlink()
    runtime = profile / ".cnf0146-runtime"
    if runtime.exists():
        shutil.rmtree(runtime)


def _write_inventory(profile: Path, inventory: dict) -> None:
    path = inventory_path(profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_hooks(profile: Path) -> dict:
    """Harness inventory. Unknown top-level keys → loaded_count=0."""
    assert_isolated(profile)
    hp = hooks_path(profile)
    inventory: dict = {
        "loaded_count": 0,
        "events": {},
        "hook_ids": [],
        "load_error": None,
        "hooks_file_present": hp.is_file(),
        "settings_present": settings_path(profile).is_file(),
    }
    if not hp.is_file():
        inventory["load_error"] = "hooks-file-absent"
        _write_inventory(profile, inventory)
        return inventory
    doc = json.loads(hp.read_text(encoding="utf-8"))
    extra = sorted(set(doc.keys()) - ALLOWED_HOOK_KEYS)
    if extra:
        inventory["load_error"] = "deny_unknown_fields:" + ",".join(extra)
        _write_inventory(profile, inventory)
        return inventory
    events: dict[str, list[str]] = {}
    ids: list[str] = []
    for event, matchers in (doc.get("hooks") or {}).items():
        names: list[str] = []
        for matcher in matchers:
            for hook in matcher.get("hooks") or []:
                hid = str(hook.get("id") or hook.get("script") or event)
                names.append(hid)
                ids.append(hid)
        events[event] = names
    inventory["events"] = events
    inventory["hook_ids"] = ids
    inventory["loaded_count"] = len(ids)
    _write_inventory(profile, inventory)
    return inventory


def trigger(profile: Path, event: str) -> dict:
    """Execute loaded hooks for one event. Unloaded → no beacon."""
    env = windows_env(profile)
    inventory = json.loads(inventory_path(profile).read_text(encoding="utf-8"))
    if inventory.get("loaded_count", 0) <= 0:
        return {
            "event": event,
            "ran": False,
            "reason": inventory.get("load_error") or "unloaded",
            "beacon": False,
        }
    hp = hooks_path(profile)
    doc = json.loads(hp.read_text(encoding="utf-8"))
    ran = 0
    for matcher in (doc.get("hooks") or {}).get(event, []):
        for hook in matcher.get("hooks") or []:
            cmd = hook.get("command")
            if not isinstance(cmd, list) or not cmd:
                continue
            proc = subprocess.run(
                cmd,
                cwd=str(plugin_dir(profile)),
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode != 0:
                return {
                    "event": event,
                    "ran": False,
                    "reason": f"hook-exit:{proc.returncode}",
                    "stderr": (proc.stderr or "")[-400],
                    "beacon": beacon_path(profile, event).is_file(),
                }
            ran += 1
    bp = beacon_path(profile, event)
    return {
        "event": event,
        "ran": ran > 0,
        "runs": ran,
        "beacon": bp.is_file(),
        "beacon_path": str(bp) if bp.is_file() else None,
    }


def fire_all(profile: Path) -> dict:
    inventory = load_hooks(profile)
    triggers = [trigger(profile, event) for event in EVENTS]
    beacons = {event: beacon_path(profile, event).is_file() for event in EVENTS}
    return {
        "inventory": inventory,
        "triggers": triggers,
        "beacons": beacons,
        "listing_says_installed": listing_says_installed(profile),
        "settings_present": settings_path(profile).is_file(),
        "both_signals": (
            inventory.get("loaded_count", 0) == len(EVENTS)
            and all(beacons.values())
        ),
    }


def both_signals_agree_loaded(obs: dict) -> bool:
    inv = obs["inventory"]
    return (
        inv.get("loaded_count") == len(EVENTS)
        and all(obs["beacons"].values())
        and inv.get("load_error") is None
    )


def both_signals_agree_unloaded(obs: dict) -> bool:
    inv = obs["inventory"]
    return inv.get("loaded_count", 0) == 0 and not any(obs["beacons"].values())
