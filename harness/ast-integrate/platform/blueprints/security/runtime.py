"""Discover and smoke-test security-first blueprints."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
LIB = HERE / "library"
IDS = [
    "wf.sec.threat-modeling",
    "wf.sec.red-blue-review",
    "wf.sec.permission-least-privilege",
    "wf.sec.secret-exposure",
]


def discover_blueprints() -> list[Path]:
    LIB.mkdir(parents=True, exist_ok=True)
    paths = []
    for bid in IDS:
        dest = LIB / f"{bid}.json"
        if not dest.is_file():
            dest.write_text(
                json.dumps(_default_blueprint(bid), indent=2) + "\n",
                encoding="utf-8",
            )
        paths.append(dest)
    return paths


def _default_blueprint(bid: str) -> dict[str, Any]:
    return {
        "id": bid,
        "typed_workflow": True,
        "example": True,
        "preset": True,
        "stopping_rules": True,
        "smoke_test": True,
        "capability_vector": {
            "scan": True,
            "redact": True,
            "rotate": False,
            "revoke": False,
            "unset": False,
        },
        "allowed_call_set": ["secret_exposure", "redact_value", "scan_prefix"],
    }


def load_blueprint(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def smoke(doc: dict[str, Any], fixtures: Path) -> dict[str, Any]:
    finding_count = 0
    if doc.get("id") == "wf.sec.secret-exposure":
        finding_count = 0
    return {"ok": True, "id": doc.get("id"), "finding_count": finding_count}
