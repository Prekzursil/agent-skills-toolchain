"""Fixture payloads, isolation proof, and the full-cycle experiment."""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Callable

from census import CLAUDE_JSON_REL, file_census, file_lists, key_diff, load_json, settings_census
from lifecycle import (
    ENABLED_KEY,
    PLUGIN_ID,
    inherit_from_cache_if_present,
    install,
    installed_dir,
    naive_uninstall,
    repair,
    rollback,
    seed_empty_home,
    uninstall,
    update,
)

V1 = "1.0.0"
V2 = "2.0.0"
LIVE_MARK = "ISOLATION-LIVE"
THROW_MARK = "ISOLATION-THROW"
SENTINEL = (
    "SUCCESS:RES-0018 in the receipt AND a per-command filesystem diff from a "
    "provably isolated throwaway profile plus an orphan verdict"
)


def write_payload(root: Path, version: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "plugin.json").write_text(
        json.dumps(
            {
                "name": PLUGIN_ID,
                "version": version,
                "description": "RES-0018 fixture plugin",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "skills").mkdir(exist_ok=True)
    (root / "hooks").mkdir(exist_ok=True)
    (root / "skills" / "skill.md").write_text(
        f"# skill\nversion={version}\nbody-for-{version}\n", encoding="utf-8"
    )
    (root / "hooks" / "pre.json").write_text(
        json.dumps({"event": "PreToolUse", "version": version}, indent=2) + "\n",
        encoding="utf-8",
    )
    if version == V2:
        (root / "skills" / "extra-v2.md").write_text("v2-only file\n", encoding="utf-8")
    return root


def prove_isolation(live: Path, throw: Path) -> dict[str, Any]:
    live_token = (live / LIVE_MARK).read_text(encoding="utf-8") if (live / LIVE_MARK).is_file() else ""
    throw_token = (throw / THROW_MARK).read_text(encoding="utf-8") if (throw / THROW_MARK).is_file() else ""
    throw_text = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in throw.rglob("*")
        if p.is_file()
    )
    live_text = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in live.rglob("*")
        if p.is_file()
    )
    real_claude = Path.home() / ".claude"
    same_path = live.resolve() == throw.resolve()
    throw_inside_live = _is_relative(throw.resolve(), live.resolve())
    live_inside_throw = _is_relative(live.resolve(), throw.resolve())
    isolated = (
        (not same_path)
        and (not throw_inside_live)
        and (not live_inside_throw)
        and LIVE_MARK not in throw_text
        and THROW_MARK not in live_text
        and live_token != throw_token
        and (live / LIVE_MARK).is_file()
        and (throw / THROW_MARK).is_file()
    )
    return {
        "isolated": isolated,
        "proven_before_first_command": True,
        "live_path": str(live),
        "throwaway_path": str(throw),
        "same_path": same_path,
        "throw_inside_live": throw_inside_live,
        "live_inside_throw": live_inside_throw,
        "live_marker_in_throwaway": LIVE_MARK in throw_text,
        "throwaway_marker_in_live": THROW_MARK in live_text,
        "real_home_claude_present": real_claude.exists(),
        "real_home_claude_path": str(real_claude),
        "throwaway_is_not_real_home_claude": (
            throw.resolve() != real_claude.resolve() if real_claude.exists() else True
        ),
        "process_uid": os.getuid(),
        "live_dev": live.stat().st_dev,
        "throw_dev": throw.stat().st_dev,
        "live_ino": live.stat().st_ino,
        "throw_ino": throw.stat().st_ino,
    }


def _is_relative(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return child != parent
    except ValueError:
        return False


def _effect(before_files, after_files, before_keys, after_keys) -> dict[str, Any]:
    files = file_lists(before_files, after_files)
    keys = key_diff(before_keys, after_keys)
    return {
        "files_created": files["created"],
        "files_mutated": files["mutated"],
        "files_removed": files["removed"],
        "settings_keys_created": keys["created"],
        "settings_keys_mutated": keys["mutated"],
        "settings_keys_removed": keys["removed"],
        "file_change_count": len(files["created"]) + len(files["mutated"]) + len(files["removed"]),
        "key_change_count": len(keys["created"]) + len(keys["mutated"]) + len(keys["removed"]),
    }


def _snap(home: Path) -> tuple[dict[str, str], dict[str, str]]:
    return file_census(home), settings_census(home)


def _run_cmd(
    name: str,
    home: Path,
    fn: Callable[[], Any],
    live: Path,
    live_before: dict[str, str],
) -> dict[str, Any]:
    bf, bk = _snap(home)
    result = fn()
    af, ak = _snap(home)
    live_after = file_census(live)
    claude = load_json(home / CLAUDE_JSON_REL)
    effect = _effect(bf, af, bk, ak)
    effect.update(
        {
            "command": name,
            "result": result,
            "live_profile_unchanged": live_after == live_before,
            "claude_json_gained_enabled_plugins": ENABLED_KEY in claude,
        }
    )
    return effect


def _plugin_owned_files(home: Path) -> list[str]:
    owned: list[str] = []
    for p in home.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(home).as_posix()
        if PLUGIN_ID in rel:
            owned.append(rel)
            continue
        try:
            if PLUGIN_ID in p.read_text(encoding="utf-8"):
                owned.append(rel)
        except (OSError, UnicodeDecodeError):
            continue
    return sorted(owned)


def run_full_cycle(tmp: Path) -> dict[str, Any]:
    live = tmp / "live"
    throw = tmp / "throw"
    payloads = tmp / "payloads"
    seed_empty_home(live, LIVE_MARK)
    seed_empty_home(throw, THROW_MARK)
    v1 = write_payload(payloads / "v1", V1)
    v2 = write_payload(payloads / "v2", V2)
    marker = f"RES0018-PRIOR-STATE-{uuid.uuid4().hex}"
    isolation = prove_isolation(live, throw)
    if not isolation["isolated"]:
        raise RuntimeError(f"throwaway not isolated: {isolation}")
    live_before = file_census(live)
    steps: list[dict[str, Any]] = []

    steps.append(
        _run_cmd("install", throw, lambda: install(throw, v1, V1, marker), live, live_before)
    )
    steps.append(_run_cmd("update", throw, lambda: update(throw, v2, V2), live, live_before))

    broken = installed_dir(throw) / "skills" / "skill.md"
    broken.unlink()
    steps.append(_run_cmd("repair", throw, lambda: repair(throw), live, live_before))
    steps.append(_run_cmd("rollback", throw, lambda: rollback(throw), live, live_before))

    marker_path = installed_dir(throw) / "prior-state.txt"
    marker_before_uninstall = marker_path.read_text(encoding="utf-8").strip()
    steps.append(_run_cmd("uninstall", throw, lambda: uninstall(throw), live, live_before))

    leftover_files = _plugin_owned_files(throw)
    inherited = inherit_from_cache_if_present(throw, v1, V1)
    reinstall_marker_path = installed_dir(throw) / "prior-state.txt"
    reinstall_text = (
        reinstall_marker_path.read_text(encoding="utf-8").strip()
        if reinstall_marker_path.is_file()
        else ""
    )
    inherited_old = inherited == marker or reinstall_text == marker
    uninstall(throw)

    live_after = file_census(live)
    return {
        "isolation": isolation,
        "prior_state_marker": marker,
        "commands": steps,
        "live_profile_unchanged_after_cycle": live_after == live_before,
        "orphan": {
            "marker_present_before_uninstall": marker_before_uninstall == marker,
            "plugin_owned_files_after_uninstall": leftover_files,
            "reinstall_inherited_prior_marker": inherited_old,
            "inherited_value": inherited,
            "verdict": "NO_INHERIT" if not inherited_old else "INHERIT",
        },
    }


def run_orphan_control(tmp: Path) -> dict[str, Any]:
    """Signal 2: marker-string + settings-key inheritance, both states."""
    clean = tmp / "clean"
    naive = tmp / "naive"
    payloads = tmp / "payloads"
    live_dummy = tmp / "live-dummy"
    v1 = write_payload(payloads / "v1", V1)
    v2 = write_payload(payloads / "v2", V2)
    marker_clean = f"RES0018-PRIOR-STATE-CLEAN-{uuid.uuid4().hex}"
    marker_naive = f"RES0018-PRIOR-STATE-NAIVE-{uuid.uuid4().hex}"

    seed_empty_home(clean, THROW_MARK)
    seed_empty_home(naive, THROW_MARK)
    seed_empty_home(live_dummy, LIVE_MARK)
    if not prove_isolation(live_dummy, clean)["isolated"]:
        raise RuntimeError("clean profile not isolated")
    if not prove_isolation(live_dummy, naive)["isolated"]:
        raise RuntimeError("naive profile not isolated")

    install(clean, v1, V1, marker_clean)
    update(clean, v2, V2)
    uninstall(clean)
    inherited_clean = inherit_from_cache_if_present(clean, v1, V1)
    clean_keys = settings_census(clean)
    clean_path = installed_dir(clean) / "prior-state.txt"
    clean_text = clean_path.read_text(encoding="utf-8").strip() if clean_path.is_file() else ""
    clean_inherited = inherited_clean == marker_clean or clean_text == marker_clean

    install(naive, v1, V1, marker_naive)
    update(naive, v2, V2)
    naive_uninstall(naive)
    inherited_naive = inherit_from_cache_if_present(naive, v1, V1)
    naive_path = installed_dir(naive) / "prior-state.txt"
    naive_text = naive_path.read_text(encoding="utf-8").strip() if naive_path.is_file() else ""
    naive_inherited = inherited_naive == marker_naive or naive_text == marker_naive
    naive_keys = settings_census(naive)

    enabled_key = f"settings.json::{ENABLED_KEY}.{PLUGIN_ID}"
    return {
        "clean_uninstall": {
            "inherited_prior_marker": clean_inherited,
            "inherited_value": inherited_clean,
            "reinstall_marker": clean_text,
            "enabled_key_present": enabled_key in clean_keys,
        },
        "naive_uninstall_control": {
            "inherited_prior_marker": naive_inherited,
            "inherited_value": inherited_naive,
            "reinstall_marker": naive_text,
            "enabled_key_present": enabled_key in naive_keys,
            "cache_left_on_disk": (naive / "plugins" / "cache" / PLUGIN_ID).is_dir(),
        },
        "detector_silent_on_clean": not clean_inherited,
        "detector_fires_on_naive": naive_inherited,
        "both_states": (not clean_inherited) and naive_inherited,
        "verdict": "NO_INHERIT" if not clean_inherited else "INHERIT",
    }
