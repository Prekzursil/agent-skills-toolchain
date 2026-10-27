#!/usr/bin/env python3
# REL-0022 canary installer under observation (rebuilt 2026-10-25).
# Writes plugin, hook, MCP, settings, cache and a file-backed timer under the
# canary HOME, and spawns a CHILD process that writes a cache beacon - the
# child side effect is the observer reach test. --variant unrecorded-write
# adds an UNRECORDED side effect (cache/unrecorded.bin) for the hole control.
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def write_tree(home, skip_timer=False):
    p = home / ".ast-plugin"
    (p / "cache").mkdir(parents=True, exist_ok=True)
    (p / "hooks").mkdir(parents=True, exist_ok=True)
    (p / "skills").mkdir(parents=True, exist_ok=True)
    (p / "tasks").mkdir(parents=True, exist_ok=True)
    (p / "cache" / "index.bin").write_bytes(b"\x00\x01index")
    (p / "hooks" / "pre-tool.json").write_text(
        json.dumps({"matcher": "Bash", "hooks": ["pre.py"]}), encoding="utf-8", newline=chr(10))
    (p / "hooks.json").write_text(
        json.dumps({"PreToolUse": ["hooks/pre-tool.json"]}), encoding="utf-8", newline=chr(10))
    (p / "mcp.json").write_text(json.dumps({"mcpServers": {}}), encoding="utf-8", newline=chr(10))
    (p / "plugin.json").write_text(
        json.dumps({"name": "rel0022-canary", "version": "1.0.0"}), encoding="utf-8", newline=chr(10))
    (p / "skills" / "skill.echo.md").write_text("# echo" + chr(10), encoding="utf-8", newline=chr(10))
    if not skip_timer:
        (p / "tasks" / "rel0022.timer").write_text(
            "[timer]" + chr(10) + "interval=30m" + chr(10), encoding="utf-8", newline=chr(10))
    settings = home / "settings.json"
    body = {}
    if settings.is_file():
        body = json.loads(settings.read_text(encoding="utf-8"))
    body["installer_touched"] = True
    settings.write_text(json.dumps(body, indent=1), encoding="utf-8", newline=chr(10))
    script = ("import os, pathlib, sys" + chr(10) +
              "b = pathlib.Path(sys.argv[1]) / '.ast-plugin' / 'cache' / 'child-beacon.txt'" + chr(10) +
              "b.parent.mkdir(parents=True, exist_ok=True)" + chr(10) +
              "b.write_text('beacon from child pid ' + str(os.getpid()) + chr(10))" + chr(10))
    sp = Path(tempfile.mkdtemp(prefix="rel0022-child-")) / "child_writer.py"
    sp.write_text(script, encoding="utf-8", newline=chr(10))
    subprocess.run([sys.executable, "-B", str(sp), str(home)], capture_output=True, timeout=120, check=True)
    sp.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", required=True)
    ap.add_argument("--variant", default="clean", choices=["clean", "unrecorded-write", "skip-timer"])
    a = ap.parse_args()
    write_tree(Path(a.home), skip_timer=(a.variant == "skip-timer"))
    if a.variant == "unrecorded-write":
        extra = Path(a.home) / ".ast-plugin" / "cache" / "unrecorded.bin"
        extra.write_bytes(b"unrecorded side effect")
    print("installer-variant=" + a.variant)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
