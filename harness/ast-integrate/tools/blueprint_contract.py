"""Blueprint scaffold that passes its own registration gate.

A blueprint is a JSON object carrying six required elements. The registration
gate reports one distinct, stable violation id per missing element so that a
one-at-a-time omission study can tell the six failures apart; shape problems on
elements that ARE present carry their own ``blueprint-invalid-*`` ids.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REQUIRED_ELEMENTS: tuple[str, ...] = ("id", "version", "stages", "gates", "smoke", "hermetic")

VIOLATION_ID: dict[str, str] = {
    "id": "blueprint-missing-id",
    "version": "blueprint-missing-version",
    "stages": "blueprint-missing-stages",
    "gates": "blueprint-missing-gates",
    "smoke": "blueprint-missing-smoke",
    "hermetic": "blueprint-missing-hermetic",
}

NOT_AN_OBJECT_ID = "blueprint-not-an-object"
INVALID_ID_PREFIX = "blueprint-invalid-"
DANGLING_GATE_STAGE_ID = "blueprint-gate-references-unknown-stage"

_STAGE_KINDS = ("plan", "build", "verify")
# The scaffold declares the interpreter symbolically so its bytes are portable;
# the smoke runner pins the token to the interpreter actually executing.
_INTERPRETER_TOKENS = frozenset({"python", "python3"})


@dataclass
class Violation:
    """One gate finding: a closed ``id`` plus the element it concerns."""

    id: str
    element: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"id": self.id, "element": self.element, "message": self.message}


@dataclass
class GateResult:
    """Outcome of :func:`register_blueprint`."""

    ok: bool
    violations: list[Violation] = field(default_factory=list)

    @property
    def violation_ids(self) -> list[str]:
        return [v.id for v in self.violations]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "violation_ids": self.violation_ids,
            "violations": [v.as_dict() for v in self.violations],
        }


def scaffold_blueprint() -> dict[str, Any]:
    """Return the canonical, deterministic scaffold (no host-specific bytes)."""
    return {
        "id": "blueprint.scaffold",
        "version": 1,
        "stages": [
            {"id": "plan", "kind": "plan"},
            {"id": "build", "kind": "build"},
            {"id": "verify", "kind": "verify"},
        ],
        "gates": [
            {"id": "self", "stage": "verify", "command": ["python3", "-c", "print(0)"]}
        ],
        "smoke": [{"id": "true", "command": ["python3", "-c", "raise SystemExit(0)"]}],
        "hermetic": True,
    }


def dump_blueprint(doc: dict[str, Any]) -> str:
    """Canonical JSON text (sorted keys, LF only)."""
    return json.dumps(doc, sort_keys=True)


def load_blueprint(root: Path) -> dict[str, Any]:
    path = Path(root) / "blueprint.json"
    return json.loads(path.read_text(encoding="utf-8"))


def emit_scaffold(dest: Path) -> Path:
    """Write the scaffold to ``dest/blueprint.json`` byte-for-byte as dumped."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "blueprint.json"
    path.write_bytes(dump_blueprint(scaffold_blueprint()).encode("utf-8"))
    return path


def omit_element(doc: dict[str, Any], element: str) -> dict[str, Any]:
    """Deep-copy ``doc`` with one required ``element`` removed.

    Raises ``KeyError`` when ``element`` is not a required element, so a typo
    in an omission study cannot silently produce an intact mutant.
    """
    if element not in REQUIRED_ELEMENTS:
        raise KeyError(f"{element!r} is not a required blueprint element")
    mutant = copy.deepcopy(doc)
    mutant.pop(element, None)
    return mutant


def _invalid(element: str, message: str) -> Violation:
    return Violation(id=INVALID_ID_PREFIX + element, element=element, message=message)


def _check_id(value: Any) -> Violation | None:
    if not isinstance(value, str) or not value.strip():
        return _invalid("id", "id must be a non-empty string")
    return None


def _check_version(value: Any) -> Violation | None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return _invalid("version", "version must be an int or string")
    if isinstance(value, int) and value < 1:
        return _invalid("version", "integer version must be >= 1")
    if isinstance(value, str) and not value.strip():
        return _invalid("version", "string version must be non-empty")
    return None


def _check_stages(value: Any) -> Violation | None:
    if not isinstance(value, list) or not value:
        return _invalid("stages", "stages must be a non-empty list")
    seen: set[str] = set()
    for row in value:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            return _invalid("stages", "each stage needs a string id")
        if row.get("kind") not in _STAGE_KINDS:
            return _invalid("stages", f"stage kind must be one of {_STAGE_KINDS}")
        if row["id"] in seen:
            return _invalid("stages", f"duplicate stage id {row['id']!r}")
        seen.add(row["id"])
    return None


def _check_command_rows(element: str, value: Any) -> Violation | None:
    if not isinstance(value, list) or not value:
        return _invalid(element, f"{element} must be a non-empty list")
    for row in value:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            return _invalid(element, f"each {element} entry needs a string id")
        cmd = row.get("command")
        if not isinstance(cmd, list) or not cmd or not all(isinstance(t, str) for t in cmd):
            return _invalid(element, f"{element} entry {row.get('id')!r} needs a non-empty argv list")
    return None


def _check_hermetic(value: Any) -> Violation | None:
    if value is not True:
        return _invalid("hermetic", "hermetic must be exactly true")
    return None


def register_blueprint(doc: dict[str, Any]) -> GateResult:
    """Gate a blueprint document.

    Missing required elements each yield their closed :data:`VIOLATION_ID`;
    shape checks run only on elements that are present, and the gate/stage
    cross-reference runs only when both sides are present and well-formed, so
    a single omission never cascades into a second finding.
    """
    if not isinstance(doc, dict):
        return GateResult(
            ok=False,
            violations=[Violation(NOT_AN_OBJECT_ID, "document", "blueprint must be a JSON object")],
        )

    violations: list[Violation] = []
    for element in REQUIRED_ELEMENTS:
        if element not in doc:
            violations.append(
                Violation(VIOLATION_ID[element], element, f"required element {element!r} is absent")
            )

    checkers = {
        "id": _check_id,
        "version": _check_version,
        "stages": _check_stages,
        "gates": lambda v: _check_command_rows("gates", v),
        "smoke": lambda v: _check_command_rows("smoke", v),
        "hermetic": _check_hermetic,
    }
    shape_ok: set[str] = set()
    for element, check in checkers.items():
        if element not in doc:
            continue
        found = check(doc[element])
        if found is not None:
            violations.append(found)
        else:
            shape_ok.add(element)

    if {"stages", "gates"} <= shape_ok:
        stage_ids = {row["id"] for row in doc["stages"]}
        for gate in doc["gates"]:
            if "stage" in gate and gate["stage"] not in stage_ids:
                violations.append(
                    Violation(
                        DANGLING_GATE_STAGE_ID,
                        "gates",
                        f"gate {gate.get('id')!r} references unknown stage {gate['stage']!r}",
                    )
                )

    return GateResult(ok=not violations, violations=violations)


def _pin_interpreter(cmd: list[str]) -> list[str]:
    if cmd and cmd[0] in _INTERPRETER_TOKENS:
        return [sys.executable, *cmd[1:]]
    return list(cmd)


def run_declared_smoke(doc: dict[str, Any]) -> tuple[bool, list[str]]:
    """Run every declared smoke command; return ``(all_passed, failed_ids)``."""
    failed: list[str] = []
    for row in doc.get("smoke") or []:
        cmd = row.get("command")
        if not isinstance(cmd, list) or not cmd:
            failed.append(str(row.get("id") or "<no-command>"))
            continue
        proc = subprocess.run(_pin_interpreter(cmd), capture_output=True, text=True, timeout=10)
        if proc.returncode != 0:
            failed.append(str(row.get("id") or cmd))
    return (not failed), failed
