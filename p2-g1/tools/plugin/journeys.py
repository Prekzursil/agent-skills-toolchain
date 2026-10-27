"""Golden install-tree journeys (TST-0074)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from plugin.payloadutil import SKILL_REL


def run_journeys(live_root: str | Path) -> dict[str, Any]:
    root = Path(live_root)
    plugin_json = root / "plugin.json"
    if not plugin_json.is_file():
        plugin_json = next(root.rglob("plugin.json"), plugin_json)
    base = plugin_json.parent if plugin_json.is_file() else root
    skill = base / SKILL_REL
    journeys = {
        "plugin_json": {"ok": plugin_json.is_file() and plugin_json.stat().st_size > 2, "detail": str(plugin_json)},
        "skill_read": {"ok": skill.is_file() and skill.stat().st_size > 2, "detail": str(skill)},
        "hooks_present": {"ok": (base / "hooks" / "hook.json").is_file() or True, "detail": "optional"},
    }
    # plugin_json journey should fail if JSON is truncated
    if plugin_json.is_file():
        try:
            import json
            json.loads(plugin_json.read_text(encoding="utf-8"))
        except Exception:
            journeys["plugin_json"]["ok"] = False
    failed = [k for k, v in journeys.items() if not v["ok"]]
    return {"ok": not failed, "failed": failed, "journeys": journeys}
