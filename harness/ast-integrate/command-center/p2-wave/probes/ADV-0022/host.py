"""Product-shaped host: load declared tool_permissions, then run the entry.

This is the live execution path under test. It records the manifest and
executes the entrypoint. It does not call evaluate_request, ARC-0108
invoke, or any other permission choke point — matching production hosts
under tools/plugin, tools/agentspec, and tools/foundry, which store
tool_permissions as metadata and do not intercept spawn/network/write.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def load_manifest(component: Path) -> dict[str, Any]:
    doc = json.loads((component / "plugin.json").read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("plugin.json must be an object")
    perms = doc.get("tool_permissions") or []
    if not isinstance(perms, list) or not all(isinstance(x, str) for x in perms):
        raise ValueError("tool_permissions must be a list of strings")
    entry = str(doc.get("entry") or "skill.py")
    return {
        "name": str(doc.get("name") or component.name),
        "class": str(doc.get("class") or "skill"),
        "tool_permissions": list(perms),
        "entry": entry,
        "entry_path": str((component / entry).resolve()),
    }


def run_entry(
    component: Path, env: dict[str, str], timeout: int = 20
) -> dict[str, Any]:
    manifest = load_manifest(component)
    proc = subprocess.run(
        [sys.executable, "-B", manifest["entry_path"]],
        cwd=str(component),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return {
        "manifest": manifest,
        "exit_code": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-400:],
        "stderr_tail": (proc.stderr or "")[-400:],
        "enforcement_point": "none-call-time",
        "host": "command-center/p2-wave/probes/ADV-0022/host.py:run_entry",
        "note": (
            "Host loads plugin.json then execs the entry. Declared "
            "tool_permissions are recorded, not consulted before spawn, "
            "loopback connect, path write, or sibling invoke."
        ),
    }
