#!/usr/bin/env python3
"""Live-client inventory for RES-0020. Names and paths only; no secret values."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

BINARIES = ("claude", "cursor", "code", "npm", "npx")
HOME_MARKERS = (
    ".claude",
    ".cursor",
    ".mcp.json",
    ".claude.json",
    os.path.join(".cursor", "mcp.json"),
    os.path.join(".claude", "settings.json"),
)
WINDOWS_INPUT = (
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
    "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md"
)
VENDOR_DOC_HINTS = (
    "privacy",
    "telemetry",
    "CLAUDE_CODE_DISABLE_TELEMETRY",
)


def _proc_names() -> list[str]:
    found: list[str] = []
    proc = Path("/proc")
    if not proc.is_dir():
        return found
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        comm = entry / "comm"
        try:
            name = comm.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        lower = name.lower()
        if any(tok in lower for tok in ("claude", "cursor", "code")):
            found.append(f"{entry.name}:{name}")
    return found[:40]


def inventory() -> dict[str, Any]:
    home = Path.home()
    binaries = {name: shutil.which(name) for name in BINARIES}
    markers = []
    for rel in HOME_MARKERS:
        p = home / rel
        markers.append({"path": str(p), "exists": p.exists(), "is_dir": p.is_dir()})
    win = Path(WINDOWS_INPUT)
    return {
        "platform": os.uname().sysname,
        "home": str(home),
        "binaries_on_path": binaries,
        "home_markers": markers,
        "windows_catalog_input_present": win.exists(),
        "windows_catalog_input": WINDOWS_INPUT,
        "live_process_names": _proc_names(),
        "vendor_privacy_doc_in_worktree": False,
        "vendor_privacy_doc_note": (
            "No vendor privacy page is stored in this worktree; documented "
            "vendor field names are therefore NOT claimed as observed. "
            f"Searched hints={list(VENDOR_DOC_HINTS)}."
        ),
        "scope": (
            "This inventory is a presence census. It is not a plugin-install "
            "socket capture of Claude Code or Cursor against production hosts."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(inventory(), indent=2, sort_keys=True))
