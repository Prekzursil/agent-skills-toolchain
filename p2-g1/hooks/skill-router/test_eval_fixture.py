#!/usr/bin/env python3
"""Regression checks for the pruned router baseline's stable eval fixture."""

from __future__ import annotations

import ast
import runpy
from pathlib import Path


HERE = Path(__file__).resolve().parent
EVAL = HERE / "eval.py"
FIXTURE = HERE / "_fixtures" / "route_v1.py"


def test_eval_uses_stable_fixture_not_pruned_backup_name():
    source = EVAL.read_text(encoding="utf-8")
    ast.parse(source, filename=str(EVAL))
    assert '"_fixtures", "route_v1.py"' in source
    assert '"route.py.baseline"' not in source


def test_historical_router_fixture_is_loadable():
    assert FIXTURE.is_file()
    module = runpy.run_path(str(FIXTURE))
    assert callable(module.get("_build_index"))
    assert "gem-hunt" in module["_tok"]("gem-hunt")


def test_eval_preserves_router_cache_in_finally():
    source = EVAL.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(EVAL))
    run_all = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_all"
    )
    guarded = next(node for node in run_all.body if isinstance(node, ast.Try))
    assert guarded.finalbody, "run_all must restore/remove its temporary router cache"
