"""Enumerate a package public surface by import and introspection, not grep."""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import re
import sys
import tomllib
from pathlib import Path
from types import ModuleType
from typing import Any


def _purge(prefix: str) -> None:
    for key in list(sys.modules):
        if key == prefix or key.startswith(prefix + "."):
            del sys.modules[key]


def load_package(pkg_dir: Path, modname: str) -> tuple[ModuleType, ModuleType]:
    """Load pkg_api + pkg_api.cli from pkg_dir under a unique module name."""
    _purge(modname)
    init = pkg_dir / "pkg_api" / "__init__.py"
    cli_path = pkg_dir / "pkg_api" / "cli.py"
    spec = importlib.util.spec_from_file_location(
        modname,
        init,
        submodule_search_locations=[str(pkg_dir / "pkg_api")],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load package at {init}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)

    cli_spec = importlib.util.spec_from_file_location(modname + ".cli", cli_path)
    if cli_spec is None or cli_spec.loader is None:
        raise RuntimeError(f"cannot load CLI at {cli_path}")
    cli_mod = importlib.util.module_from_spec(cli_spec)
    sys.modules[modname + ".cli"] = cli_mod
    cli_spec.loader.exec_module(cli_mod)
    setattr(mod, "cli", cli_mod)
    return mod, cli_mod


def public_symbols(mod: ModuleType, logical_pkg: str = "pkg_api") -> list[str]:
    exported = getattr(mod, "__all__", None)
    if isinstance(exported, (list, tuple)) and exported:
        names = [str(n) for n in exported]
    else:
        names = []
        for name, obj in inspect.getmembers(mod):
            if name.startswith("_"):
                continue
            if inspect.ismodule(obj):
                continue
            if inspect.isfunction(obj) or inspect.isclass(obj):
                if getattr(obj, "__module__", "").startswith(mod.__name__):
                    names.append(name)
    return sorted(f"{logical_pkg}.{n}" for n in names)


def private_names_on_module(mod: ModuleType) -> list[str]:
    out = []
    for name, obj in inspect.getmembers(mod):
        if not name.startswith("_") or name.startswith("__"):
            continue
        if inspect.isfunction(obj) or inspect.isclass(obj):
            out.append(name)
    return sorted(out)


def cli_commands(parser: argparse.ArgumentParser, prefix: str | None = None) -> list[str]:
    prog = prefix or (parser.prog or "cli")
    found: list[str] = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                cmd = f"{prog} {name}"
                found.append(cmd)
                found.extend(cli_commands(sub, cmd))
    if not found:
        found.append(prog)
    return sorted(set(found))


def entry_points(pyproject: Path) -> list[str]:
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    scripts = (data.get("project") or {}).get("scripts") or {}
    return sorted(f"{name} = {target}" for name, target in scripts.items())


def grep_defs(pkg_dir: Path) -> list[str]:
    """Text-search enumerator: counts private helpers. Used only as a control."""
    pattern = re.compile(r"^(?:async )?def ([A-Za-z_][A-Za-z0-9_]*)\s*\(|^class ([A-Za-z_][A-Za-z0-9_]*)\s*[:(]")
    names: list[str] = []
    for path in sorted((pkg_dir / "pkg_api").glob("*.py")):
        for line in path.read_text(encoding="utf-8").splitlines():
            m = pattern.match(line)
            if m:
                names.append(m.group(1) or m.group(2))
    return sorted(names)


def enumerate_surface(root: Path, modname: str) -> dict[str, Any]:
    pkg_dir = root
    mod, cli_mod = load_package(pkg_dir, modname)
    parser = cli_mod.build_parser()
    symbols = public_symbols(mod)
    commands = cli_commands(parser)
    eps = entry_points(pkg_dir / "pyproject.toml")
    return {
        "production_method": "introspection",
        "symbols": symbols,
        "cli_commands": commands,
        "entry_points": eps,
        "imported_modules": sorted([mod.__name__, cli_mod.__name__]),
        "private_names_excluded": private_names_on_module(mod),
    }


def grep_control(root: Path, introspected_symbols: list[str]) -> dict[str, Any]:
    grepped = grep_defs(root)
    introspected_short = {s.split(".")[-1] for s in introspected_symbols}
    extra = [n for n in grepped if n not in introspected_short]
    missing_private = [n for n in extra if n.startswith("_")]
    return {
        "grep_def_and_class_names": grepped,
        "names_grep_counts_introspection_drops": extra,
        "private_helpers_grep_only": missing_private,
    }
