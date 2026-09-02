"""Canary client: load installed hooks and fire contracted events.

Loader rule matching the named failure class (spec 11303 / Codex precedent):
a `$schema` key on hooks.json loads ZERO hooks while the files still look
installed. A hook whose type is not `command` or whose command is empty is
not loaded. File presence is not execution.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

from fence import IsolationError, OwnerFence
from package_spec import CONTRACTED_EVENTS, EFFECTS_DIRNAME, INSTALL_SUBDIR


PAYLOADS = {
    "SessionStart": {"hook_event_name": "SessionStart", "source": "startup"},
    "PreToolUse": {
        "hook_event_name": "PreToolUse",
        "tool_name": "Read",
        "tool_input": {"path": "canary.txt"},
    },
    "PostToolUse": {
        "hook_event_name": "PostToolUse",
        "tool_name": "Read",
        "tool_response": {"ok": True},
    },
    "Stop": {"hook_event_name": "Stop", "stop_hook_active": True},
}


def plugin_dir(profile: Path) -> Path:
    return profile / INSTALL_SUBDIR


def load_hooks(hooks_json: Path) -> dict:
    data = json.loads(hooks_json.read_text(encoding="utf-8"))
    if "$schema" in data:
        return {"loaded": {}, "reason": "schema-key-unloads-all", "raw": data}
    loaded: dict[str, list[dict]] = {}
    for event, matchers in (data.get("hooks") or {}).items():
        for matcher in matchers or []:
            for hook in matcher.get("hooks") or []:
                command = str(hook.get("command") or "").strip()
                if hook.get("type") != "command" or not command:
                    continue
                loaded.setdefault(event, []).append(hook)
    return {"loaded": loaded, "reason": "ok", "raw": data}


class CanaryClient:
    def __init__(self, profile: Path, fence: OwnerFence) -> None:
        self.profile = fence.assert_throwaway(profile)
        self.fence = fence
        self.plugin = plugin_dir(self.profile)
        self.hooks_json = self.plugin / "hooks.json"
        self.load_record: dict = {}
        self.started = False

    def start(self) -> dict:
        if not self.hooks_json.is_file():
            raise FileNotFoundError(f"hooks.json missing at {self.hooks_json}")
        self.load_record = load_hooks(self.hooks_json)
        self.started = True
        return {
            "loaded_events": sorted(self.load_record["loaded"]),
            "loaded_hook_count": sum(len(v) for v in self.load_record["loaded"].values()),
            "plugin_dir": str(self.plugin),
            "reason": self.load_record["reason"],
            "started": True,
        }

    def trigger(self, event: str) -> dict:
        if not self.started:
            raise RuntimeError("client not started")
        t0 = time.time_ns()
        hooks = self.load_record["loaded"].get(event) or []
        runs = []
        for hook in hooks:
            command = hook["command"]
            argv = shlex.split(command, posix=os.name != "nt")
            env = os.environ.copy()
            env["HOME"] = str(self.profile)
            env["CANARY_EFFECTS"] = str(self.profile / EFFECTS_DIRNAME)
            env["CLAUDE_PLUGIN_ROOT"] = str(self.plugin)
            env["HOOK_EVENT"] = event
            if self.fence.is_forbidden(Path(env["CANARY_EFFECTS"])):
                raise IsolationError("ISOLATION-VIOLATION: effects dir under owner home")
            proc = subprocess.run(
                argv,
                cwd=str(self.plugin),
                env=env,
                input=json.dumps(PAYLOADS.get(event, {"hook_event_name": event})),
                text=True,
                capture_output=True,
                timeout=20,
            )
            runs.append(
                {
                    "argv": argv,
                    "exit_code": proc.returncode,
                    "stderr_tail": (proc.stderr or "")[-400:],
                }
            )
        t1 = time.time_ns()
        effect = self.profile / EFFECTS_DIRNAME / f"{event}.json"
        return {
            "event": event,
            "hooks_run": len(runs),
            "loaded": bool(hooks),
            "observed": effect.is_file(),
            "runs": runs,
            "side_effect_path": str(effect) if effect.is_file() else None,
            "t0_ns": t0,
            "t1_ns": t1,
        }

    def trigger_all(self, events: tuple[str, ...] = CONTRACTED_EVENTS) -> list[dict]:
        return [self.trigger(event) for event in events]
