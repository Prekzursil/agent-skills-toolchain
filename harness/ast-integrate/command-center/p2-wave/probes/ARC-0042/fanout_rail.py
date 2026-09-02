"""Old exec fan-out rail: live tools/import-adapters/codex_fanout.py.

WRAP the importer. Fire-and-forget profiles stay KEEP-REFUSAL (not replaced).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
IMPORT_ADAPTERS = REPO / "tools" / "import-adapters"
# Prefer a delivered importer; otherwise WRAP via the local agentspec.argv
# importer in this probe directory (not a local argv builder).
sys.path.insert(0, str(HERE))
if (IMPORT_ADAPTERS / "codex_fanout.py").is_file():
    sys.path.insert(0, str(IMPORT_ADAPTERS))

from codex_fanout import ImportRefused, import_fanout_path  # noqa: E402

FIRE_AND_FORGET = (
    HERE.parents[3]
    / "command-center/p2-wave/probes/IMP-0161/fixtures/fire-and-forget.json"
)


def profile_for_unit(here: Path, uid: str) -> Path:
    return here / "fixtures" / "fanout" / f"{uid.lower()}.json"


def old_artifact(unit_id: str, repo: Path, here: Path | None = None) -> dict[str, Any]:
    root = here or HERE
    path = profile_for_unit(root, unit_id)
    workflow = import_fanout_path(path)
    nodes = workflow.get("nodes") or []
    fan = next((n for n in nodes if n.get("kind") == "FanOut"), None)
    if not isinstance(fan, dict):
        raise RuntimeError(f"{unit_id}: imported workflow missing FanOut")
    planned = fan.get("units") or []
    match = next((u for u in planned if u.get("id") == unit_id), None)
    if not isinstance(match, dict):
        raise RuntimeError(f"{unit_id}: fan-out plan missing unit")
    body = {
        "unit_id": unit_id,
        "workflow_id": workflow.get("id"),
        "timeout_seconds": match["timeout_seconds"],
        "prompt_file": match["prompt_file"],
        "argv": list(match["argv"]),
        "blocking": True,
        "prompt_transport": "file",
    }
    sentinel = f"SUCCESS:{unit_id}"
    return {
        "unit_id": unit_id,
        "sentinel": sentinel,
        "body": body,
        "adapter": "codex-fanout",
        "source_schema": "tools/codex/profiles/schemas/fanout.schema.json",
    }


def refuse_fire_and_forget(path: Path | None = None) -> dict[str, Any]:
    target = path or FIRE_AND_FORGET
    try:
        import_fanout_path(target)
    except ImportRefused as exc:
        return {
            "refused": True,
            "reason_id": exc.reason_id,
            "path": target.as_posix(),
            "pass": exc.reason_id
            in {"dispatch.fire-and-forget", "dispatch.background-flagged"},
        }
    return {
        "refused": False,
        "reason_id": None,
        "path": target.as_posix(),
        "pass": False,
    }
