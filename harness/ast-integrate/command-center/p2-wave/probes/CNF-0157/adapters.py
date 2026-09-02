#!/usr/bin/env python3
"""Per-client adapter layer for CNF-0157 (non-author reproduction harness).

This is not the production adapter tree (no client-loadable plugin.json
with hooks/skills/mcp at .claude-plugin or tools/plugin). tools/plugin may
exist as an unrelated Python toolkit. This harness encodes
the claimed capability split so the matrix can observe REPRODUCES,
LOUD-DEGRADE, FAIL-SILENT, and RED. Spec 10983: silent degradation is the
defect; loud refusal of an unsupported capability is the required behaviour.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE / "fixtures" / "plugin"
ADVERTISED_SKILL = "skill.council"
PLANTED_UNROUTED_SKILL = "skill.installed-but-unrouted"
MCP_TOOL = "matrix-echo"

VERDICT_REPRODUCES = "REPRODUCES"
VERDICT_LOUD = "LOUD-DEGRADE"
VERDICT_SILENT = "FAIL-SILENT"
VERDICT_RED = "RED"

SPECS: dict[str, dict[str, Any]] = {
    "claude-code": {
        "supported": frozenset({"plugin", "hook", "skill", "mcp-adapter"}),
        "silent_execution": frozenset(),
        "routable_skills": frozenset({ADVERTISED_SKILL, PLANTED_UNROUTED_SKILL}),
    },
    "codex-cli": {
        # Hook is declared supported (plugin appears installed) but execution
        # returns empty success — the measured "zero hooks / config key" class.
        "supported": frozenset({"plugin", "hook", "skill", "mcp-adapter"}),
        "silent_execution": frozenset({"hook"}),
        "routable_skills": frozenset({ADVERTISED_SKILL}),
    },
    "antigravity": {
        "supported": frozenset({"plugin", "skill", "mcp-adapter"}),
        "silent_execution": frozenset(),
        "routable_skills": frozenset({ADVERTISED_SKILL}),
    },
    "mcp-generic": {
        "supported": frozenset({"mcp-adapter"}),
        "silent_execution": frozenset(),
        "routable_skills": frozenset(),
    },
}


class LoudDegradation(Exception):
    def __init__(self, client_id: str, capability: str, message: str) -> None:
        self.client_id = client_id
        self.capability = capability
        self.message = message
        super().__init__(message)

    def names_capability(self) -> bool:
        return self.capability in self.message and self.client_id in self.message


def plugin_root() -> Path:
    return PLUGIN_ROOT


def load_manifest(root: Path | None = None) -> dict[str, Any]:
    path = (root or PLUGIN_ROOT) / "plugin.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _loud(client_id: str, capability: str) -> dict[str, Any]:
    msg = (
        f"unsupported capability {capability} on {client_id}: this adapter "
        f"refuses silently-downgraded interchangeability and names the gap"
    )
    exc = LoudDegradation(client_id, capability, msg)
    return {
        "verdict": VERDICT_LOUD,
        "observed_behaviour": msg,
        "error": msg,
        "capability_named_in_error": exc.names_capability(),
        "hooks_run": 0,
        "selected_skill": None,
        "mcp_tools": [],
    }


def _silent(client_id: str, capability: str, why: str) -> dict[str, Any]:
    return {
        "verdict": VERDICT_SILENT,
        "observed_behaviour": (
            f"{client_id} {capability}: empty success without naming the gap ({why})"
        ),
        "error": None,
        "capability_named_in_error": False,
        "hooks_run": 0,
        "selected_skill": None,
        "mcp_tools": [],
        "silent_degradation": True,
        "why": why,
    }


def _red(client_id: str, capability: str) -> dict[str, Any]:
    return {
        "verdict": VERDICT_RED,
        "observed_behaviour": f"adapter disabled for {client_id}; {capability} not exercised",
        "error": "adapter-disabled",
        "capability_named_in_error": True,
        "hooks_run": 0,
        "selected_skill": None,
        "mcp_tools": [],
    }


def _ok(behaviour: str, **extra: Any) -> dict[str, Any]:
    row = {
        "verdict": VERDICT_REPRODUCES,
        "observed_behaviour": behaviour,
        "error": None,
        "capability_named_in_error": False,
        "hooks_run": 0,
        "selected_skill": None,
        "mcp_tools": [],
    }
    row.update(extra)
    return row


def execute_hook(root: Path, side_effect: Path) -> None:
    spec = json.loads((root / "hooks" / "hook.pre-tool.json").read_text(encoding="utf-8"))
    script = root / str(spec["script"])
    env = os.environ.copy()
    env["CNF0157_SIDE_EFFECT"] = str(side_effect)
    proc = subprocess.run(
        [sys.executable, "-B", str(script)],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"hook script exit {proc.returncode}: {(proc.stderr or proc.stdout or '')[-400:]}"
        )


def list_installed_skills(root: Path) -> list[str]:
    skills_dir = root / "skills"
    ids = []
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            if (child / "SKILL.md").is_file():
                ids.append(child.name)
    return ids


def select_skill(root: Path, skill_id: str, routable: frozenset[str]) -> str | None:
    installed = list_installed_skills(root)
    if skill_id not in installed:
        return None
    if skill_id in routable:
        return skill_id
    return None


def list_mcp_tools(root: Path) -> list[str]:
    doc = json.loads((root / "mcp" / "tools.json").read_text(encoding="utf-8"))
    names = []
    for tool in doc.get("tools") or []:
        if isinstance(tool, dict) and tool.get("name"):
            names.append(str(tool["name"]))
    return names


def exercise_claim(
    client_id: str,
    claim_id: str,
    *,
    disabled: Iterable[str] = (),
    root: Path | None = None,
    work: Path | None = None,
) -> dict[str, Any]:
    spec = SPECS[client_id]
    plugin = root or PLUGIN_ROOT
    disabled_set = frozenset(disabled)
    if client_id in disabled_set:
        row = _red(client_id, claim_id)
        row["artifact"] = str(plugin / "plugin.json")
        return row
    supported: frozenset[str] = spec["supported"]
    silent: frozenset[str] = spec["silent_execution"]
    if claim_id not in supported:
        row = _loud(client_id, claim_id)
        row["artifact"] = str(plugin / "plugin.json")
        return row
    if claim_id in silent:
        row = _silent(
            client_id,
            claim_id,
            "declared-supported-empty-success",
        )
        row["artifact"] = str(plugin / "plugin.json")
        return row

    if claim_id == "plugin":
        manifest = load_manifest(plugin)
        required = ("name", "version", "hooks", "skills", "mcp", "supported_clients")
        missing = [k for k in required if k not in manifest]
        if missing:
            row = _silent(client_id, "plugin", f"manifest-missing-{missing}")
            row["artifact"] = str(plugin / "plugin.json")
            return row
        row = _ok(
            f"{client_id} loaded plugin {manifest['name']}@{manifest['version']}",
            artifact=str(plugin / "plugin.json"),
            plugin_name=manifest["name"],
            plugin_version=manifest["version"],
        )
        return row

    if claim_id == "hook":
        if work is None:
            raise ValueError("hook exercise requires work dir for side-effect")
        side = work / f"hook-side-effect-{client_id}.txt"
        if side.exists():
            side.unlink()
        execute_hook(plugin, side)
        fired = side.is_file() and "hook-fired" in side.read_text(encoding="utf-8")
        if not fired:
            row = _silent(client_id, "hook", "side-effect-missing")
            row["artifact"] = str(side)
            return row
        row = _ok(
            f"{client_id} hook executed; side-effect {side.name} contains hook-fired",
            artifact=str(side),
            hooks_run=1,
        )
        return row

    if claim_id == "skill":
        installed = list_installed_skills(plugin)
        selected = select_skill(plugin, ADVERTISED_SKILL, spec["routable_skills"])
        unrouted = select_skill(
            plugin, PLANTED_UNROUTED_SKILL, spec["routable_skills"]
        )
        if ADVERTISED_SKILL not in installed:
            row = _silent(client_id, "skill", "advertised-skill-absent-on-disk")
            row["artifact"] = str(plugin / "skills")
            return row
        if selected != ADVERTISED_SKILL:
            row = _silent(client_id, "skill", "router-failed-to-select-installed-skill")
            row["artifact"] = str(plugin / "skills" / ADVERTISED_SKILL / "SKILL.md")
            row["installed_skills"] = installed
            return row
        row = _ok(
            f"{client_id} router selected {ADVERTISED_SKILL}",
            artifact=str(plugin / "skills" / ADVERTISED_SKILL / "SKILL.md"),
            selected_skill=selected,
            installed_skills=installed,
            planted_unrouted_selected=unrouted == PLANTED_UNROUTED_SKILL,
        )
        return row

    if claim_id == "mcp-adapter":
        tools = list_mcp_tools(plugin)
        if MCP_TOOL not in tools:
            row = _silent(client_id, "mcp-adapter", "matrix-echo-absent")
            row["artifact"] = str(plugin / "mcp" / "tools.json")
            row["mcp_tools"] = tools
            return row
        row = _ok(
            f"{client_id} MCP adapter listed {MCP_TOOL}",
            artifact=str(plugin / "mcp" / "tools.json"),
            mcp_tools=tools,
        )
        return row

    row = _loud(client_id, claim_id)
    row["artifact"] = str(plugin / "plugin.json")
    return row


def force_unsupported(client_id: str, capability: str) -> dict[str, Any]:
    """Loud-degradation oracle: request a capability the adapter must refuse by name."""
    return _loud(client_id, capability)


def skill_router_plant(client_id: str, root: Path | None = None) -> dict[str, Any]:
    """Spec 11330: installed skill that the router fails to select."""
    spec = SPECS[client_id]
    plugin = root or PLUGIN_ROOT
    installed = list_installed_skills(plugin)
    selected = select_skill(plugin, PLANTED_UNROUTED_SKILL, spec["routable_skills"])
    on_disk = PLANTED_UNROUTED_SKILL in installed
    if on_disk and selected is None:
        return {
            "verdict": VERDICT_SILENT,
            "client_id": client_id,
            "skill_id": PLANTED_UNROUTED_SKILL,
            "on_disk": True,
            "selected": False,
            "observed_behaviour": (
                f"{client_id} has {PLANTED_UNROUTED_SKILL} on disk but router "
                "returned empty (spec:11330)"
            ),
        }
    if on_disk and selected:
        return {
            "verdict": VERDICT_REPRODUCES,
            "client_id": client_id,
            "skill_id": PLANTED_UNROUTED_SKILL,
            "on_disk": True,
            "selected": True,
            "observed_behaviour": f"{client_id} selected planted skill",
        }
    return {
        "verdict": VERDICT_RED,
        "client_id": client_id,
        "on_disk": on_disk,
        "selected": selected,
        "observed_behaviour": "plant missing from plugin package",
    }
