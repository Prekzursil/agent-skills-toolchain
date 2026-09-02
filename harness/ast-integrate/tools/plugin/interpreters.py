"""Explicit interpreter declarations for plugin entrypoints."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
MANIFEST_REL = ".claude-plugin/plugin.json"

ALLOWED_INTERPRETERS = {
    "python3": {"floor": (3, 11), "names": ("python3", "python"), "family": "python"},
    "node": {"floor": (20,), "names": ("node",), "family": "node"},
    "pwsh": {"floor": (7,), "names": ("pwsh",), "family": "pwsh"},
    "bash": {"floor": (5,), "names": ("bash",), "family": "bash"},
}


class DeclarationError(ValueError):
    pass


class InterpreterError(RuntimeError):
    """A declared interpreter cannot be used; ``code`` is MISSING or VERSION."""

    def __init__(self, message: str, code: str = "MISSING") -> None:
        super().__init__(message)
        self.code = code


def load_manifest(path: str | Path | None = None) -> dict[str, Any]:
    dest = Path(path) if path else REPO / MANIFEST_REL
    return json.loads(dest.read_text(encoding="utf-8"))


def lint_entrypoints(manifest: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    doc = manifest if manifest is not None else load_manifest()
    rows = list(doc.get("entrypoints") or [])
    out = []
    for row in rows:
        interp = row.get("interpreter")
        minv = row.get("min_version")
        path = row.get("path")
        if not interp or not minv:
            raise DeclarationError(
                f"missing interpreter declaration for {row.get('id') or path}"
            )
        if interp not in ALLOWED_INTERPRETERS:
            raise DeclarationError(f"unknown interpreter {interp}")
        out.append(
            {
                "id": row.get("id"),
                "kind": row.get("kind") or "script",
                "path": path,
                "interpreter": interp,
                "min_version": str(minv),
            }
        )
    return out


def which_family(name: str, *, required: bool = False) -> str:
    """Return the PATH binary for an interpreter family id (or name), else ``""``.

    Every binary name registered for the family is tried, so ``python3``
    also finds ``python``. With ``required=True`` a missing interpreter raises
    ``InterpreterError(code="MISSING")`` instead of returning the empty string.
    """
    names = ALLOWED_INTERPRETERS.get(name, {}).get("names") or (name,)
    for candidate in names:
        exe = shutil.which(candidate)
        if exe:
            return exe
    if required:
        raise InterpreterError(f"interpreter not on PATH: {name}", code="MISSING")
    return ""


def resolve_interpreter(row: dict[str, Any]) -> str:
    family = ALLOWED_INTERPRETERS[row["interpreter"]]
    for name in family["names"]:
        found = shutil.which(name)
        if found:
            return found
    raise InterpreterError(
        f"no binary for declared interpreter {row['interpreter']} (MISSING)", code="MISSING"
    )
