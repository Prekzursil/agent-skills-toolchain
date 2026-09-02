"""Windows-layout isolated profile, installer, and process-level hook client."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import DECLARED_HOOKS, MARKER, POISON_KEY, PROFILE_USER


def win_join(*parts: str) -> str:
    return "\\".join(parts)


class WindowsProfile:
    """Isolated USERPROFILE with Windows AppData layout on this Linux host."""

    def __init__(self, root: Path) -> None:
        self.host_root = root
        self.userprofile = root / "Users" / PROFILE_USER
        self.appdata = self.userprofile / "AppData" / "Roaming"
        self.localappdata = self.userprofile / "AppData" / "Local"
        self.temp = self.localappdata / "Temp"
        self.install_root = self.appdata / "harness" / "plugins" / "harness"
        self.effect_dir = self.appdata / "harness" / "hook-side-effects"
        self.win_userprofile = win_join("C:", "Users", PROFILE_USER)
        self.win_appdata = win_join(self.win_userprofile, "AppData", "Roaming")
        self.win_install = win_join(
            self.win_appdata, "harness", "plugins", "harness"
        )

    def materialize_empty(self) -> None:
        self.temp.mkdir(parents=True, exist_ok=True)
        self.appdata.mkdir(parents=True, exist_ok=True)

    def listing(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self.userprofile.exists():
            return rows
        for p in sorted(self.userprofile.rglob("*")):
            rel = p.relative_to(self.userprofile).as_posix()
            rows.append({"path": rel, "is_dir": p.is_dir(), "bytes": p.stat().st_size if p.is_file() else 0})
        return rows

    def harness_contamination(self) -> list[str]:
        hits: list[str] = []
        for row in self.listing():
            path = row["path"]
            if path.startswith(".claude") or "/.claude" in path:
                hits.append(path)
            if "harness/plugins" in path or path.endswith("hooks.json"):
                hits.append(path)
        return hits

    def env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["USERPROFILE"] = str(self.userprofile)
        env["HOME"] = str(self.userprofile)
        env["HOMEDRIVE"] = "C:"
        env["HOMEPATH"] = "\\Users\\" + PROFILE_USER
        env["APPDATA"] = str(self.appdata)
        env["LOCALAPPDATA"] = str(self.localappdata)
        env["TEMP"] = str(self.temp)
        env["TMP"] = str(self.temp)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env


def install_artifact(published: Path, profile: WindowsProfile) -> dict[str, Any]:
    dest = profile.install_root
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(published, dest)
    plugin = dest / "plugin.json"
    dispatch = dest / "hooks.json"
    ok = plugin.is_file() and dispatch.is_file()
    return {
        "source": str(published),
        "target": str(dest),
        "target_windows": profile.win_install,
        "ok": ok,
        "plugin_present": plugin.is_file(),
        "dispatch_present": dispatch.is_file(),
    }


def _declared_from_plugin(install_root: Path) -> list[str]:
    plugin_path = install_root / "plugin.json"
    if not plugin_path.is_file():
        return []
    plugin = json.loads(plugin_path.read_text(encoding="utf-8"))
    ids: list[str] = []
    for rel in plugin.get("hooks") or []:
        desc = install_root / str(rel).replace("\\", "/")
        if desc.is_file():
            body = json.loads(desc.read_text(encoding="utf-8"))
            hid = str(body.get("id") or Path(rel).stem)
            ids.append(hid)
        else:
            ids.append(Path(str(rel)).stem)
    return ids


def load_dispatch(install_root: Path) -> tuple[list[dict[str, Any]], str]:
    path = install_root / "hooks.json"
    if not path.is_file():
        return [], "hook-not-loaded:missing-dispatch"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [], "hook-not-loaded:malformed-dispatch"
    if not isinstance(data, dict):
        return [], "hook-not-loaded:dispatch-not-object"
    if POISON_KEY in data:
        # Estate precedent: a $schema key made a client load ZERO hooks
        # while every hook file was still present on disk.
        return [], "hook-not-loaded:poison-$schema-zero-load"
    hooks = data.get("hooks")
    if not isinstance(hooks, list):
        return [], "hook-not-loaded:missing-hooks-array"
    loaded: list[dict[str, Any]] = []
    for item in hooks:
        if not isinstance(item, dict):
            continue
        if item.get("enabled") is False:
            continue
        script_rel = str(item.get("script") or "")
        script = install_root / script_rel.replace("\\", "/")
        if not script.is_file():
            continue
        loaded.append(
            {
                "id": str(item.get("id") or ""),
                "event": str(item.get("event") or ""),
                "script": script_rel.replace("\\", "/"),
                "side_effect": str(item.get("side_effect") or ""),
            }
        )
    return loaded, "ok"


def fire_hook(
    profile: WindowsProfile, hook: dict[str, Any], parent_pid: int
) -> dict[str, Any]:
    script = profile.install_root / hook["script"]
    env = profile.env()
    env["CNF0096_HOOK_ID"] = hook["id"]
    env["CNF0096_EVENT"] = hook["event"]
    env["CNF0096_EFFECT_DIR"] = str(profile.effect_dir)
    env["CNF0096_MARKER"] = MARKER
    proc = subprocess.run(
        [sys.executable, "-B", str(script)],
        cwd=str(profile.install_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    effect_path = profile.effect_dir / (hook["id"] + ".json")
    observed: dict[str, Any] | None = None
    if effect_path.is_file() and effect_path.stat().st_size > 0:
        try:
            observed = json.loads(effect_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            observed = None
    fired = bool(
        proc.returncode == 0
        and isinstance(observed, dict)
        and observed.get("marker") == MARKER
        and observed.get("hook_id") == hook["id"]
        and int(observed.get("pid") or 0) != parent_pid
        and int(observed.get("pid") or 0) > 0
    )
    return {
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "")[-500:],
        "stderr": (proc.stderr or "")[-500:],
        "effect_path": str(effect_path) if effect_path.is_file() else None,
        "effect_path_windows": win_join(
            profile.win_appdata, "harness", "hook-side-effects", hook["id"] + ".json"
        ),
        "observed": observed,
        "fired": fired,
        "parent_pid": parent_pid,
    }


def observe_session(
    profile: WindowsProfile,
    *,
    trigger: bool = True,
    declared_ids: list[str] | None = None,
) -> dict[str, Any]:
    parent_pid = os.getpid()
    installed_ids = set(_declared_from_plugin(profile.install_root))
    loaded, load_reason = load_dispatch(profile.install_root)
    loaded_ids = {h["id"] for h in loaded if h.get("id")}
    if declared_ids is None:
        declared_ids = [h["id"] for h in DECLARED_HOOKS]
    fires: dict[str, dict[str, Any]] = {}
    if trigger:
        profile.effect_dir.mkdir(parents=True, exist_ok=True)
        for hook in loaded:
            fires[hook["id"]] = fire_hook(profile, hook, parent_pid)
    rows: list[dict[str, Any]] = []
    for spec in DECLARED_HOOKS:
        hid = spec["id"]
        desc = profile.install_root / spec["descriptor"]
        script = profile.install_root / spec["script"]
        installed = hid in installed_ids and desc.is_file()
        loaded_ok = hid in loaded_ids
        fire = fires.get(hid) or {}
        fired = bool(fire.get("fired"))
        if fired:
            side = {
                "triggering_action": spec["event"],
                "path": fire.get("effect_path"),
                "path_windows": fire.get("effect_path_windows"),
                "ts": (fire.get("observed") or {}).get("ts"),
                "pid": (fire.get("observed") or {}).get("pid"),
                "ppid": (fire.get("observed") or {}).get("ppid"),
                "marker": (fire.get("observed") or {}).get("marker"),
                "parent_pid": parent_pid,
                "distinct_process": True,
            }
            not_observed = None
        else:
            side = None
            if hid not in declared_ids:
                not_observed = "not-in-declared-inventory"
            elif not installed:
                not_observed = "descriptor-or-plugin-listing-absent"
            elif not loaded_ok:
                not_observed = load_reason if load_reason != "ok" else "not-in-runtime-inventory"
            elif not trigger:
                not_observed = "not-triggered"
            else:
                not_observed = "triggered-but-no-side-effect"
        rows.append(
            {
                "id": hid,
                "event": spec["event"],
                "script": spec["script"],
                "descriptor": spec["descriptor"],
                "descriptor_exists": desc.is_file(),
                "script_exists": script.is_file(),
                "installed": installed,
                "loaded": loaded_ok,
                "fired": fired,
                "side_effect": side,
                "not_observed": not_observed,
            }
        )
    fired_count = sum(1 for r in rows if r["fired"] and r["id"] in declared_ids)
    declared_rows = [r for r in rows if r["id"] in declared_ids]
    zero = fired_count == 0
    naive = (profile.install_root / "plugin.json").is_file()
    process_healthy = bool(declared_rows) and all(r["fired"] for r in declared_rows)
    p0 = naive and zero and not process_healthy
    return {
        "parent_pid": parent_pid,
        "load_reason": load_reason,
        "installed_ids": sorted(installed_ids),
        "loaded_ids": sorted(loaded_ids),
        "declared_ids": list(declared_ids),
        "hooks": rows,
        "fired_count": fired_count,
        "health": {
            "process_healthy": process_healthy,
            "naive_healthy": naive,
            "zero_hooks_fired": zero,
            "false_healthy_p0": p0,
            "reason": (
                "all-declared-fired"
                if process_healthy
                else ("zero-hooks-fired" if zero else "partial-or-unfired")
            ),
        },
    }
