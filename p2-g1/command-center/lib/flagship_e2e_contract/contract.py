"""Flagship count floor and e2e postcondition."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

SPEC_FLAGSHIP_COUNT = 40
MIN_BYTES = 64


def flagship_count_ok(count: int) -> bool:
    return int(count) == SPEC_FLAGSHIP_COUNT


def independent_artifact_path(dest: Path, blueprint_id: str) -> Path:
    return Path(dest) / f"{blueprint_id}.json"


def evaluate_e2e(blueprint_id: str, dest: Path, runner: Callable[..., Any]) -> dict[str, Any]:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    produced = runner(blueprint_id, dest)
    path = independent_artifact_path(dest, blueprint_id)
    exists = path.is_file()
    nbytes = path.stat().st_size if exists else 0
    parsed = False
    reason = "missing-artifact"
    if exists:
        try:
            json.loads(path.read_text(encoding="utf-8"))
            parsed = True
            reason = "ok"
        except (OSError, json.JSONDecodeError) as exc:
            reason = f"unparseable:{type(exc).__name__}"
    is_mock = getattr(produced, "__class__", type("x", (), {})).__name__ == "MagicMock" or not exists
    accepted = bool(exists and parsed and nbytes >= MIN_BYTES and not is_mock)
    if is_mock:
        reason = "mocked-only"
    return {
        "accepted": accepted,
        "rejected": not accepted,
        "declared_is_mock": bool(is_mock),
        "postcondition": {
            "bytes": nbytes,
            "parsed": parsed,
            "exists": exists,
            "reason": reason,
        },
    }
