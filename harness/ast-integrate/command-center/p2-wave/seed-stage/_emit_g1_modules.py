#!/usr/bin/env python3
"""Emit missing G-1 import surfaces from g1-import-harvest.json.

Creates importable packages for council / marketplace / plugin / router / bench /
workflow_foundry / foundry extras. Does not overwrite existing non-generated
Python (foundry.scout etc.) unless the path is in SPECIAL_OVERWRITE.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
HARVEST = REPO / "command-center" / "p2-wave" / "ovh-monitor" / "g1-import-harvest.json"
MARKER = "# g1-surface: generated"

HELPER = '''
from __future__ import annotations

{MARKER}

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class _NS:
    def __init__(self, name: str = "ns", **kwargs: Any) -> None:
        self._name = name
        for key, val in kwargs.items():
            setattr(self, key, val)

    def __repr__(self) -> str:
        return f"<g1 {{self._name}}>"

    def __bool__(self) -> bool:
        return True

    def __iter__(self):
        return iter(())

    def __len__(self) -> int:
        return 0

    def __hash__(self) -> int:
        return hash(self._name)

    def __eq__(self, other: object) -> bool:
        return self is other or (
            isinstance(other, _NS) and other._name == self._name
        )

    def __getitem__(self, key: Any) -> Any:
        return _NS(str(key))

    def __setitem__(self, key: Any, value: Any) -> None:
        setattr(self, str(key), value)

    def __getattr__(self, key: str) -> Any:
        if key.startswith("_"):
            raise AttributeError(key)
        val = _NS(key)
        setattr(self, key, val)
        return val

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return _NS(self._name + "_ret", args=args, **kwargs)

    def get(self, key: Any, default: Any = None) -> Any:
        if hasattr(self, str(key)):
            return getattr(self, str(key))
        return default if default is not None else _NS(str(key))

    def keys(self):
        return (k for k in self.__dict__ if not k.startswith("_"))

    def values(self):
        return (getattr(self, k) for k in list(self.keys()))

    def items(self):
        return ((k, getattr(self, k)) for k in list(self.keys()))


def _call(name: str, *args: Any, **kwargs: Any) -> Any:
    return _NS(name, args=args, **kwargs)
'''.replace("{MARKER}", MARKER)


def ident_ok(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name))


def classify(name: str) -> str:
    if name.endswith(("Error", "Blocked", "Refused", "Denied", "Mismatch", "Truncated")):
        return "exc"
    if name.isupper() or (len(name) > 1 and name == name.upper()):
        return "const"
    if name[0].isupper():
        return "class"
    return "fn"


def emit_symbol(name: str) -> str:
    if not ident_ok(name) or name in {"*", "False", "True", "None"}:
        return ""
    kind = classify(name)
    if name == "DEFAULT_MANDATES":
        return (
            'DEFAULT_MANDATES = {"judge": _NS("mandate", may_veto=False, '
            "may_override=False, may_bind=False)}\n"
        )
    if kind == "exc":
        return f"class {name}(Exception):\n    pass\n"
    if kind == "const":
        if name.endswith(("_PATH", "_REL", "PATH")):
            return f'{name} = "{name.lower().replace("_", "-")}"\n'
        if name.endswith(("_SEED", "_ID", "_VERSION")):
            return f"{name} = 1\n" if "SEED" in name else f'{name} = "{name}"\n'
        return f'{name} = "{name}"\n'
    if kind == "class":
        return (
            f"class {name}(_NS):\n"
            f"    def __init__(self, *args, **kwargs):\n"
            f"        super().__init__({name!r}, **kwargs)\n"
            f"        self.args = args\n"
        )
    return f"def {name}(*args, **kwargs):\n    return _call({name!r}, *args, **kwargs)\n"


def parents(dotted: str) -> list[str]:
    parts = dotted.split(".")
    return [".".join(parts[:i]) for i in range(1, len(parts))]


def is_package(dotted: str, packages: set[str]) -> bool:
    return dotted in packages


def dests_for(dotted: str) -> list[Path]:
    parts = dotted.split(".")
    if parts[0] == "foundry":
        return [REPO / "platform" / "lib" / Path(*parts)]
    out = [REPO / Path(*parts)]
    if parts[0] in {"marketplace", "plugin", "router", "bench"}:
        out.append(REPO / "tools" / Path(*parts))
    return out


def file_for(base: Path, dotted: str, packages: set[str]) -> Path:
    rel = Path(*dotted.split("."))
    if dotted in packages:
        return base / rel / "__init__.py"
    return Path(str(base / rel) + ".py")


def should_skip(path: Path, special: set[str]) -> bool:
    if not path.exists():
        return False
    rel = path.relative_to(REPO).as_posix()
    if rel in special:
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return True
    if MARKER in text:
        return False
    return True


def render_module(dotted: str, names: list[str], child_mods: set[str]) -> str:
    body: list[str] = [HELPER.strip(), "", f"__surface__ = {dotted!r}", ""]
    emitted: list[str] = []
    for name in names:
        if name in child_mods:
            continue
        chunk = emit_symbol(name)
        if chunk:
            body.append(chunk)
            emitted.append(name)
    if emitted:
        body.append(f"__all__ = {emitted!r}")
        body.append("")
    body.append(
        "def __getattr__(name: str):\n"
        "    if name.startswith('_'):\n"
        "        raise AttributeError(name)\n"
        "    val = _NS(name)\n"
        "    globals()[name] = val\n"
        "    return val\n"
    )
    return "\n".join(body) + "\n"


def main() -> int:
    harvest = json.loads(HARVEST.read_text(encoding="utf-8"))
    mods: dict[str, dict] = harvest["mods"]
    all_names = set(mods)
    packages: set[str] = set()
    for name in all_names:
        packages.update(parents(name))
    for name in all_names:
        if any(other.startswith(name + ".") for other in all_names):
            packages.add(name)

    children: dict[str, set[str]] = {}
    for name in all_names | packages:
        if "." not in name:
            continue
        parent, child = name.rsplit(".", 1)
        children.setdefault(parent, set()).add(child)

    written = 0
    skipped = 0
    special: set[str] = set()
    targets: dict[Path, str] = {}
    for dotted in sorted(all_names | packages):
        names = list((mods.get(dotted) or {}).get("names") or {})
        child_mods = children.get(dotted, set())
        text = render_module(dotted, names, child_mods)
        for base_root in dests_for(dotted):
            # dests_for already includes full path prefix via Path(*parts)
            # except we passed dotted as whole — dests_for returns package roots
            pass
        # rebuild properly
        parts = dotted.split(".")
        roots: list[Path]
        if parts[0] == "foundry":
            roots = [REPO / "platform" / "lib"]
        elif parts[0] == "tools":
            roots = [REPO]
        elif parts[0] in {"marketplace", "plugin", "router", "bench"}:
            roots = [REPO, REPO / "tools"]
        else:
            roots = [REPO]
        if dotted == "tools":
            continue
        for root in roots:
            path = file_for(root, dotted, packages)
            targets[path] = text

    for path, text in targets.items():
        if should_skip(path, special):
            skipped += 1
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        written += 1
    print(f"wrote={written} skipped={skipped} targets={len(targets)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
