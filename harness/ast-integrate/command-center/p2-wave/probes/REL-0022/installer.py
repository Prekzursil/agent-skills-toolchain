#!/usr/bin/env python3
"""Canary-isolated plugin installer under test for REL-0022.

All writes go to --home. A child process writes the cache beacon.
Does not touch host systemd, the owner's login HOME, or the network.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from canary import IsolationError, assert_isolated  # noqa: E402

PLUGIN_JSON = {
    "id": "rel0022.canary",
    "version": "1.0.0",
    "hooks": ["pre-tool"],
}
HOOK_INDEX = {"hooks": [{"id": "pre-tool", "path": "hooks/pre-tool.json"}]}
HOOK_PRE = {"event": "pre-tool", "command": "true"}
MCP = {"mcpServers": {"rel0022-echo": {"command": "echo", "args": ["ok"]}}}
SKILL = "# skill.echo\n\nEcho skill seeded by the REL-0022 canary installer.\n"
TIMER = "# rel0022 file-backed timer (NOT a host systemd unit)\nOnBootSec=0\n"
CACHE_INDEX = b"REL0022-CACHE-INDEX-v1\n"


def write_tree(
    home: Path,
    *,
    extra_unrecorded: bool = False,
    skip_id: str | None = None,
    spawn_child: bool = True,
) -> list[str]:
    home = Path(home).resolve()
    assert_isolated(home)
    root = home / ".ast-plugin"
    (root / "skills").mkdir(parents=True, exist_ok=True)
    (root / "hooks").mkdir(parents=True, exist_ok=True)
    (root / "cache").mkdir(parents=True, exist_ok=True)
    (root / "tasks").mkdir(parents=True, exist_ok=True)

    written: list[str] = []

    def maybe(action_id: str, rel: str, data: str | bytes) -> None:
        if skip_id == action_id:
            return
        path = home / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            path.write_bytes(data)
        else:
            path.write_text(data, encoding="utf-8")
        written.append(rel)

    maybe(
        "write-plugin-manifest",
        ".ast-plugin/plugin.json",
        json.dumps(PLUGIN_JSON, indent=2) + "\n",
    )
    maybe("write-echo-skill", ".ast-plugin/skills/skill.echo.md", SKILL)
    maybe(
        "write-hooks-index",
        ".ast-plugin/hooks.json",
        json.dumps(HOOK_INDEX, indent=2) + "\n",
    )
    maybe(
        "write-hook-pre-tool",
        ".ast-plugin/hooks/pre-tool.json",
        json.dumps(HOOK_PRE, indent=2) + "\n",
    )
    maybe(
        "write-mcp-entry",
        ".ast-plugin/mcp.json",
        json.dumps(MCP, indent=2) + "\n",
    )
    maybe("seed-cache-index", ".ast-plugin/cache/index.bin", CACHE_INDEX)
    maybe("write-scheduled-task-file", ".ast-plugin/tasks/rel0022.timer", TIMER)

    if skip_id != "edit-settings-plugin-enabled":
        settings_path = home / "settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        settings["plugin.enabled"] = True
        settings_path.write_text(
            json.dumps(settings, indent=2) + "\n", encoding="utf-8"
        )
        written.append("settings.json")

    if spawn_child and skip_id != "child-cache-beacon":
        beacon = root / "cache" / "child-beacon.txt"
        child = subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                (
                    "import pathlib,sys;"
                    "p=pathlib.Path(sys.argv[1]);"
                    "p.write_text('child-process-side-effect\\n', encoding='utf-8')"
                ),
                str(beacon),
            ],
            check=True,
        )
        if child.returncode != 0:
            raise RuntimeError("child beacon writer failed")
        written.append(".ast-plugin/cache/child-beacon.txt")

    if extra_unrecorded:
        hole = root / "cache" / "unrecorded.bin"
        hole.write_bytes(b"UNRECORDED-SIDE-EFFECT\n")
        written.append(".ast-plugin/cache/unrecorded.bin")

    return written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", required=True)
    parser.add_argument("--extra-unrecorded", action="store_true")
    parser.add_argument("--skip-id", default="")
    parser.add_argument("--no-child", action="store_true")
    args = parser.parse_args()
    home = Path(args.home).resolve()
    os.environ["HOME"] = str(home)
    os.environ["USERPROFILE"] = str(home)
    try:
        write_tree(
            home,
            extra_unrecorded=args.extra_unrecorded,
            skip_id=(args.skip_id or None),
            spawn_child=not args.no_child,
        )
    except IsolationError as exc:
        print(f"FAILED:isolation {exc}", file=sys.stderr)
        return 2
    print("SUCCESS:install")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
