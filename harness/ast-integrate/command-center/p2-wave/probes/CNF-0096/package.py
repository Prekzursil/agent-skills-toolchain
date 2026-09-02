"""Build the published installable plugin (file-backed local artifact).

Starts from the A2 typed registry, adds the extra hooks needed for the
removal control, generates descriptors, then ships real hook scripts so
installed-on-disk is not the same as fired.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GEN_DIR = REPO / "command-center" / "p2-wave" / "probes" / "ARC-0010"

from common import DECLARED_HOOKS, MARKER  # noqa: E402

HOOK_BODY = '''#!/usr/bin/env python3
"""CNF-0096 hook script: write a process-level side effect, then exit 0."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

hook_id = os.environ["CNF0096_HOOK_ID"]
effect_dir = Path(os.environ["CNF0096_EFFECT_DIR"])
effect_dir.mkdir(parents=True, exist_ok=True)
payload = {
    "hook_id": hook_id,
    "pid": os.getpid(),
    "ppid": os.getppid(),
    "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "event": os.environ.get("CNF0096_EVENT", ""),
    "marker": os.environ.get("CNF0096_MARKER", ""),
}
path = effect_dir / (hook_id + ".json")
path.write_text(json.dumps(payload, sort_keys=True) + "\\n", encoding="utf-8")
'''


def _extend_registry(registry: dict[str, Any]) -> dict[str, Any]:
    doc = copy.deepcopy(registry)
    existing = {e["id"] for e in doc["entries"]}
    extra = [
        {
            "id": "hook.post-tool",
            "kind": "hook",
            "event": "PostToolUse",
            "script": "hooks/post-tool.py",
            "enabled": True,
        },
        {
            "id": "hook.session-start",
            "kind": "hook",
            "event": "SessionStart",
            "script": "hooks/session-start.py",
            "enabled": True,
        },
    ]
    for hook in extra:
        if hook["id"] not in existing:
            doc["entries"].append(hook)
    for entry in doc["entries"]:
        if entry.get("kind") == "plugin_manifest" and entry.get("id") == "plugin.harness":
            ids = list(entry.get("hook_ids") or [])
            for hook in DECLARED_HOOKS:
                if hook["id"] not in ids:
                    ids.append(hook["id"])
            entry["hook_ids"] = ids
    return doc


def build_published_artifact(dest: Path) -> Path:
    """Write the installable tree under dest/harness-1.0.0 and return that path."""
    sys.path.insert(0, str(GEN_DIR))
    from generator import DEFAULT_REGISTRY, generate, load_json  # type: ignore

    registry = _extend_registry(load_json(DEFAULT_REGISTRY))
    files = generate(registry)
    root = dest / "harness-1.0.0"
    if root.exists():
        for p in sorted(root.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()
    for rel, blob in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
    hooks_dir = root / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    for hook in DECLARED_HOOKS:
        script = root / hook["script"]
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(HOOK_BODY, encoding="utf-8")
        script.chmod(0o755)
    dispatch = {
        "hooks": [
            {
                "id": h["id"],
                "event": h["event"],
                "script": h["script"],
                "enabled": True,
                "side_effect": "hook-side-effects/" + h["id"] + ".json",
            }
            for h in DECLARED_HOOKS
        ]
    }
    (root / "hooks.json").write_text(
        json.dumps(dispatch, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    marker = {
        "kind": "published-installable-artifact",
        "plugin": "harness",
        "version": "1.0.0",
        "marker": MARKER,
        "declared_hooks": [h["id"] for h in DECLARED_HOOKS],
        "note": "File-backed local package generated from A2 registry plus hook scripts.",
    }
    (root / "ARTIFACT.json").write_text(
        json.dumps(marker, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return root
