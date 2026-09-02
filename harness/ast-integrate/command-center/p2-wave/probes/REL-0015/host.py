#!/usr/bin/env python3
"""Generic MCP host used as the canary-equivalent install-and-smoke driver.

Acceptance is a hook side-effect file, never installer exit and never a
directory listing of the plugin tree.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

HOST_NAME = "rel-0015-generic-mcp-host"
HOST_VERSION = "1.0.0"


def build_string() -> str:
    py = ".".join(str(p) for p in sys.version_info[:3])
    return (
        f"{HOST_NAME}/{HOST_VERSION} "
        f"(python-{py}; {platform.system()}-{platform.release()})"
    )


def install_plugin(plugin_src: Path, isolated_home: Path) -> Path:
    dest = isolated_home / "opt" / "plugin"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(plugin_src, dest)
    return dest


def listing_ok(plugin_dest: Path) -> bool:
    return (plugin_dest / "plugin.json").is_file()


def fire_pre_tool_use(plugin_dest: Path, isolated_home: Path, observed_build: str) -> Path:
    manifest = json.loads((plugin_dest / "plugin.json").read_text(encoding="utf-8"))
    hooks = manifest.get("hooks") or []
    hook = next((h for h in hooks if h.get("event") == "PreToolUse"), None)
    if hook is None:
        raise RuntimeError("plugin has no PreToolUse hook")
    script = plugin_dest / str(hook["script"])
    side = isolated_home / "var" / "hook-fired.json"
    env = os.environ.copy()
    env["HOME"] = str(isolated_home)
    env["REL0015_SIDE_EFFECT"] = str(side)
    env["REL0015_EVENT"] = "PreToolUse"
    env["REL0015_CLIENT_BUILD"] = observed_build
    # aliases used by the fixture hook
    env["REL0015_SIDE_EFFECT"] = str(side)
    env["REL0015_EVENT"] = "PreToolUse"
    env["REL0015_CLIENT_BUILD"] = observed_build
    interp = str(hook.get("interpreter") or sys.executable)
    if interp in {"python", "python3"}:
        interp = sys.executable
    subprocess.run(
        [interp, str(script)],
        cwd=str(plugin_dest),
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return side


def smoke(plugin_src: Path, isolated_home: Path) -> dict:
    observed = build_string()
    dest = install_plugin(plugin_src, isolated_home)
    listed = listing_ok(dest)
    side = fire_pre_tool_use(dest, isolated_home, observed)
    passed = side.is_file() and side.stat().st_size > 0
    observed_from_hook = ""
    if passed:
        try:
            payload = json.loads(side.read_text(encoding="utf-8"))
            observed_from_hook = str(
                payload.get("observed_client_build_string")
                or payload.get("observed_client_build_string")
                or ""
            )
        except (OSError, json.JSONDecodeError):
            passed = False
        if observed_from_hook != observed:
            passed = False
    return {
        "pass": passed,
        "observed_client_build_string": observed,
        "observed_from_hook": observed_from_hook,
        "listing_ok": listed,
        "side_effect_path": str(side),
        "side_effect_present": side.is_file(),
        "plugin_dest": str(dest),
        "acceptance_signal": "hook-side-effect-file-with-observed-build-string",
        "listing_disqualified": True,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--build-string", action="store_true")
    p.add_argument("--plugin", type=Path)
    p.add_argument("--home", type=Path)
    args = p.parse_args()
    if args.build_string:
        print(build_string())
        return 0
    if args.plugin and args.home:
        result = smoke(args.plugin, args.home)
        print(json.dumps(result, indent=2))
        return 0 if result["pass"] else 1
    print("usage: host.py --build-string | --plugin DIR --home DIR", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
