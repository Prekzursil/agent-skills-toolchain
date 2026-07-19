#!/usr/bin/env python
"""PostToolUse hook — orphan-commit gate (fixes broken HEAD from committed-imports-uncommitted).

Mined recurring failure ("confirmed 2x"): a committed file imports/requires a file that was never
`git add`ed, so HEAD builds locally (the untracked file is present in the working tree) but BREAKS on
a fresh checkout — and the green test suite structurally cannot catch it. After a `git commit`, if
untracked SOURCE files remain, warn. Deterministic (git status); inject only; never blocks; fail-open.

Hook LAW: external signal (git status --short) the model can't fake; inject additionalContext; exit 0.
Opt-out:  ORPHAN_COMMIT=off  in env, or  hooks/orphan-commit/.disabled
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
SRC_EXT = (
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".go",
    ".rs",
    ".java",
    ".rb",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".kt",
    ".swift",
    ".scala",
    ".toml",
    ".cfg",
    ".ini",
    ".json",
    ".yaml",
    ".yml",
)


def main() -> int:
    try:
        if (THIS / ".disabled").exists() or os.environ.get(
            "ORPHAN_COMMIT", ""
        ).lower() in ("off", "0", "false"):
            return 0
        data = json.loads(sys.stdin.read() or "{}")
        ti = data.get("tool_input") or {}
        cmd = str(ti.get("command") or "") if isinstance(ti, dict) else ""
        if "git commit" not in cmd:
            return 0  # only act after an actual commit
        cwd = str(data.get("cwd") or os.getcwd())
        r = subprocess.run(
            ["git", "-C", cwd, "status", "--short"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        untracked = []
        for line in (r.stdout or "").splitlines():
            if line.startswith("??"):  # untracked
                p = line[2:].strip().strip('"')
                if p.endswith(SRC_EXT):
                    untracked.append(p)
        if untracked:
            shown = ", ".join(untracked[:8]) + (" ..." if len(untracked) > 8 else "")
            msg = (
                f"**[orphan-commit gate]** {len(untracked)} untracked SOURCE file(s) remain after this "
                f"commit: {shown}. If any committed file imports/requires one of them, **HEAD breaks on a "
                f"fresh checkout** (your green suite cannot catch this — the file is present locally only). "
                f"`git add` the missing file(s) and amend, or confirm they are intentionally excluded and not "
                f"imported by committed code."
            )
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PostToolUse",
                            "additionalContext": msg,
                        }
                    }
                )
            )
    except Exception:
        pass  # fail-open: never crash a session
    return 0


if __name__ == "__main__":
    sys.exit(main())
