"""Launch pinned firecrawl-mcp with User-scope FIRECRAWL_API_KEY.

The long-lived CyberStrike TUI often lacks freshly set User env, so
{env:FIRECRAWL_API_KEY} interpolates empty. This loader reads HKCU.
Never prints the key.
"""
from __future__ import annotations

import os
import subprocess
import sys
import winreg
from pathlib import Path

NODE = Path(r"C:\Program Files\nodejs\node.exe")
SCRIPT = Path(r"D:\opt\cyberstrike-mcp\node_modules\firecrawl-mcp\dist\index.js")


def user_env(name: str) -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value or "")
    except OSError:
        return ""


def main() -> int:
    env = os.environ.copy()
    key = env.get("FIRECRAWL_API_KEY") or user_env("FIRECRAWL_API_KEY")
    if not key:
        sys.stderr.write("firecrawl-mcp-launch: FIRECRAWL_API_KEY missing in process and User env\n")
        return 2
    env["FIRECRAWL_API_KEY"] = key
    url = env.get("FIRECRAWL_API_URL") or user_env("FIRECRAWL_API_URL")
    if url:
        env["FIRECRAWL_API_URL"] = url
    if not NODE.is_file() or not SCRIPT.is_file():
        sys.stderr.write("firecrawl-mcp-launch: node or dist/index.js missing\n")
        return 3
    return subprocess.call(
        [str(NODE), str(SCRIPT)],
        cwd=str(SCRIPT.parent),
        env=env,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main())
