"""Launch pinned hacktricks-mcp-server against D:\\knowledge corpus."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

NODE = Path(r"C:\Program Files\nodejs\node.exe")
SCRIPT = Path(r"D:\opt\cyberstrike-mcp\node_modules\hacktricks-mcp-server\dist\index.js")


def main() -> int:
    if not NODE.is_file() or not SCRIPT.is_file():
        sys.stderr.write("hacktricks-mcp-launch: node or dist/index.js missing\n")
        return 3
    env = os.environ.copy()
    return subprocess.call(
        [str(NODE), str(SCRIPT)],
        cwd=str(SCRIPT.parent.parent),
        env=env,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main())
