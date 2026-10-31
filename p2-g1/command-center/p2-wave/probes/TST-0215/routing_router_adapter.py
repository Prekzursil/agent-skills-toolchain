"""TST-0215 adapter: build the LIVE platform/routing Router over loader-backed roots.

The clean inventory IS the live home inventory (vault skills + installed
plugins walked by index.discover), matching the receipt's corpus_a. A planted
inventory appends EXACTLY ONE planted description: a fixture skills root
(skill surface) or a fixture plugins.json that carries the same real plugin
keys plus one planted manifest (plugin surface). Router source is unchanged.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "platform"))

from routing.index import Roots, discover  # noqa: E402
from routing.router import Router  # noqa: E402

HOME_SKILLS = [Path.home() / ".agents" / "skills", Path.home() / ".claude" / "skills"]
HOME_PLUGINS = Path.home() / ".claude" / "plugins" / "installed_plugins.json"


def clean_roots() -> Roots:
    return Roots(skills=list(HOME_SKILLS), plugins_json=HOME_PLUGINS)


def planted_roots(planted_root: Path, surface: str) -> Roots:
    if surface == "skill":
        return Roots(skills=[*HOME_SKILLS, planted_root / "skills"], plugins_json=HOME_PLUGINS)
    return Roots(skills=list(HOME_SKILLS), plugins_json=planted_root / "installed_plugins.json")


def build_router(roots: Roots) -> Router:
    return Router.build(discover(roots))


def build_clean_router() -> Router:
    return build_router(clean_roots())
