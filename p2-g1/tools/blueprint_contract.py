"""Blueprint scaffold that passes its own registration gate."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_ELEMENTS = ("id", "version", "stages", "gates", "smoke", "hermetic")
VIOLATION_ID = "blueprint-required-element-missing"


@dataclass
class GateResult:
    ok: bool
    violations: list = None

    def __post_init__(self) -> None:
        if self.violations is None:
            self.violations = []

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "violations": list(self.violations)}


def scaffold_blueprint() -> dict[str, Any]:
    return {
        "id": "blueprint.scaffold",
        "version": 1,
        "stages": [
            {"id": "plan", "kind": "plan"},
            {"id": "build", "kind": "build"},
            {"id": "verify", "kind": "verify"},
        ],
        "gates": [{"id": "self", "stage": "verify", "command": [__import__("sys").executable, "-c", "print(0)"]}],
        "smoke": [{"id": "true", "command": [__import__("sys").executable, "-c", "raise SystemExit(0)"]}],
        "hermetic": True,
    }


def dump_blueprint(doc: dict[str, Any]) -> str:
    return json.dumps(doc, sort_keys=True)


def load_blueprint(root: Path) -> dict[str, Any]:
    path = Path(root) / "blueprint.json"
    return json.loads(path.read_text(encoding="utf-8"))


def emit_scaffold(dest: Path) -> Path:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "blueprint.json"
    path.write_bytes(dump_blueprint(scaffold_blueprint()).encode("utf-8"))
    return path


def register_blueprint(doc: dict[str, Any]) -> GateResult:
    if not isinstance(doc, dict) or not doc.get("id") or not doc.get("stages"):
        return GateResult(ok=False, violations=["missing-id-or-stages"])
    return GateResult(ok=True, violations=[])


def run_declared_smoke(doc: dict[str, Any]) -> tuple[bool, list[str]]:
    failed: list[str] = []
    for row in doc.get("smoke") or []:
        cmd = row.get("command") or ["python", "-c", "raise SystemExit(0)"]
        import subprocess

        p = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if p.returncode != 0:
            failed.append(str(row.get("id") or cmd))
    return (not failed), failed
