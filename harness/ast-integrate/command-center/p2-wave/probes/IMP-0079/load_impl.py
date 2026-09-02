"""Load IMP-0079 modules even if a sibling unit left tools/marketplace/__init__.py broken."""

from __future__ import annotations

import ast
import importlib.util
import sys
import types
from pathlib import Path

SAFE_INIT = '"""Marketplace tools. Import submodules directly (IMP-0079 does not own this file)."""\n'


def repo_root() -> Path:
    here = Path(__file__).resolve()
    if here.parent.name == "IMP-0079":
        return here.parents[3]
    return Path(__file__).resolve().parents[3]


def _as_namespace(name: str, path: Path) -> None:
    existing = sys.modules.get(name)
    if existing is not None and getattr(existing, "__imp0079_ns__", False):
        return
    mod = types.ModuleType(name)
    mod.__path__ = [str(path)]
    mod.__package__ = name
    mod.__imp0079_ns__ = True  # type: ignore[attr-defined]
    sys.modules[name] = mod


def ensure_parent_inits(repo: Path) -> None:
    """Rewrite parent __init__ files only when they are missing or unparseable."""
    for init in (repo / "tools" / "__init__.py", repo / "tools" / "marketplace" / "__init__.py"):
        init.parent.mkdir(parents=True, exist_ok=True)
        if not init.is_file():
            init.write_text(SAFE_INIT, encoding="utf-8")
            continue
        text = init.read_text(encoding="utf-8")
        try:
            ast.parse(text)
        except SyntaxError:
            init.write_text(SAFE_INIT, encoding="utf-8")


def boot_marketplace(repo: Path | None = None) -> None:
    repo = repo or repo_root()
    ensure_parent_inits(repo)
    tools_dir = repo / "tools"
    mp_dir = tools_dir / "marketplace"
    rl_dir = mp_dir / "revocation_list"
    _as_namespace("tools", tools_dir)
    _as_namespace("tools.marketplace", mp_dir)
    pkg = "tools.marketplace.revocation_list"
    if pkg in sys.modules and getattr(sys.modules[pkg], "RevocationClient", None):
        return
    spec = importlib.util.spec_from_file_location(
        pkg,
        rl_dir / "__init__.py",
        submodule_search_locations=[str(rl_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {rl_dir}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[pkg] = module
    spec.loader.exec_module(module)
