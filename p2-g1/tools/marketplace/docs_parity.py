"""Declared vs documented surface parity."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json


@dataclass(frozen=True)
class Ident:
    kind: str
    name: str


@dataclass
class ParityReport:
    declared: set[Ident]
    documented: set[Ident]

    @property
    def declared_minus_documented(self) -> set[Ident]:
        return self.declared - self.documented

    @property
    def documented_minus_declared(self) -> set[Ident]:
        return self.documented - self.declared

    @property
    def both_empty(self) -> bool:
        return not self.declared_minus_documented and not self.documented_minus_declared

    def named_commands(self) -> list[str]:
        return sorted(i.name for i in self.declared_minus_documented if i.kind == "command")

    def as_dict(self) -> dict[str, Any]:
        return {
            "declared": sorted((i.kind, i.name) for i in self.declared),
            "documented": sorted((i.kind, i.name) for i in self.documented),
            "declared_minus_documented": sorted(
                (i.kind, i.name) for i in self.declared_minus_documented
            ),
            "documented_minus_declared": sorted(
                (i.kind, i.name) for i in self.documented_minus_declared
            ),
            "both_empty": self.both_empty,
        }


def _declared(root: Path) -> set[Ident]:
    data = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    out: set[Ident] = set()
    for item in data.get("commands") or []:
        if isinstance(item, dict) and item.get("id"):
            out.add(Ident("command", str(item["id"])))
        elif isinstance(item, str):
            out.add(Ident("command", item))
    for path in data.get("skills") or []:
        out.add(Ident("skill", Path(path).parent.name))
    for path in data.get("hooks") or []:
        out.add(Ident("hook", Path(path).stem))
    return out


def _documented(root: Path) -> set[Ident]:
    path = root / "docs" / "SURFACE.md"
    text = path.read_text(encoding="utf-8")
    kind = None
    out: set[Ident] = set()
    mapping = {"commands": "command", "skills": "skill", "hooks": "hook"}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            kind = mapping.get(stripped[3:].strip().lower())
            continue
        if kind and stripped.startswith("- "):
            out.add(Ident(kind, stripped[2:].strip().strip("`")))
    return out


def compute_parity(root: Path | str) -> ParityReport:
    root = Path(root)
    return ParityReport(declared=_declared(root), documented=_documented(root))


def drop_documented_entry(root: Path | str, name: str, kind: str) -> None:
    root = Path(root)
    path = root / "docs" / "SURFACE.md"
    keep = []
    current = None
    mapping = {"commands": "command", "skills": "skill", "hooks": "hook"}
    for line in path.read_text(encoding="utf-8").splitlines(True):
        stripped = line.strip()
        if stripped.startswith("## "):
            current = mapping.get(stripped[3:].strip().lower())
            keep.append(line)
            continue
        if current == kind and stripped.startswith("- "):
            ident = stripped[2:].strip().strip("`")
            if ident == name:
                continue
        keep.append(line)
    path.write_text("".join(keep), encoding="utf-8")
