"""Import Codex fan-out fixtures; refuse fire-and-forget / background."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ImportRefused(Exception):
    def __init__(self, reason_id: str, message: str = "") -> None:
        super().__init__(message or reason_id)
        self.reason_id = reason_id


def import_fanout_profile(path: str | Path) -> dict[str, Any]:
    return import_fanout_path(path)


def import_fanout_path(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise ImportRefused("dispatch.missing-file", f"missing {p}")
    doc = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ImportRefused("dispatch.unparseable", "fixture is not an object")
    if doc.get("background") or doc.get("fire_and_forget"):
        reason = "dispatch.fire-and-forget" if doc.get("fire_and_forget") else "dispatch.background-flagged"
        raise ImportRefused(reason, "fire-and-forget/background fan-out is refused")
    if not doc.get("timeout_seconds"):
        raise ImportRefused("dispatch.missing-timeout", "timeout_seconds required")
    units_in = list(doc.get("units") or [])
    units: list[dict] = []
    for src in units_in:
        extra = list(src.get("extra_argv") or [])
        if src.get("prompt") or "--prompt" in extra:
            raise ImportRefused("dispatch.prompt-on-argv", "prompt body on argv")
        argv = [str(doc.get("binary") or "codex"), "--timeout", str(doc["timeout_seconds"])]
        if src.get("prompt_file"):
            argv.extend(["--prompt-file", str(src["prompt_file"])])
        row = dict(src)
        row["argv"] = argv
        units.append(row)
    fanout = {
        "kind": "FanOut",
        "width": len(units),
        "units": units,
    }
    barrier = {"kind": "Barrier", "after": "FanOut"}
    return {
        "id": doc.get("id"),
        "binary": doc.get("binary"),
        "timeout_seconds": doc.get("timeout_seconds"),
        "nodes": [fanout, barrier],
        "units": units,
    }
