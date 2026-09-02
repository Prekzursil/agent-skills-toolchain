"""Seeded shuffle plugin for AUD-0052.

Works two ways:
  * as a pytest plugin (``-p shuffle_plugin --aud0052-seed N``) when pytest is present
  * as a standalone collector/runner used by this unit's probes (pytest is not installed
    in this worktree)

The shuffle is ``random.Random(seed).shuffle`` of the collected item list. A green
result without a recorded order difference between seeds would mean the shuffle
never happened; callers must assert that.
"""
from __future__ import annotations

import ast
import importlib.util
import os
import random
import sys
import traceback
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LAB = HERE / "lab"
STATE = LAB / "_state"
BOX = STATE / "box.txt"
FLAKE_COUNTER = STATE / "flake_counter.txt"
REPEAT_ENV = "AUD0052_REPEAT_MODE"


def pytest_addoption(parser):  # pragma: no cover - pytest hook
    group = parser.getgroup("aud0052")
    group.addoption("--aud0052-seed", action="store", default=None)
    group.addoption("--aud0052-record-order", action="store", default=None)


def pytest_collection_modifyitems(session, config, items):  # pragma: no cover
    seed = config.getoption("--aud0052-seed")
    if seed not in (None, ""):
        items[:] = shuffle_items(list(items), int(seed))
    path = config.getoption("--aud0052-record-order")
    if path:
        Path(path).write_text(
            __import__("json").dumps([i.nodeid for i in items], indent=1) + "\n",
            encoding="utf-8",
        )


def shuffle_items(items: list, seed: int) -> list:
    out = list(items)
    random.Random(int(seed)).shuffle(out)
    return out


def collect_tests(root: Path, repo: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    root = root.resolve()
    repo = repo.resolve()
    for path in sorted(root.rglob("test_*.py")):
        if "__pycache__" in path.parts or path.name.startswith("_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        rel = path.relative_to(repo).as_posix()
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                args = [a.arg for a in node.args.args]
                items.append(
                    {
                        "nodeid": f"{rel}::{node.name}",
                        "path": rel,
                        "qualname": node.name,
                        "lineno": node.lineno,
                        "kind": "function",
                        "fixture_args": args,
                        "executable": args == [],
                    }
                )
            elif isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, ast.FunctionDef) and child.name.startswith(
                        "test_"
                    ):
                        args = [a.arg for a in child.args.args]
                        items.append(
                            {
                                "nodeid": f"{rel}::{node.name}::{child.name}",
                                "path": rel,
                                "qualname": f"{node.name}.{child.name}",
                                "lineno": child.lineno,
                                "kind": "method",
                                "fixture_args": args,
                                "executable": False,
                            }
                        )
    return items


def nodeids(items: list) -> list[str]:
    out = []
    for item in items:
        if isinstance(item, dict):
            out.append(str(item["nodeid"]))
        else:
            out.append(str(getattr(item, "nodeid", item)))
    return out


def reset_box() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    if BOX.exists():
        BOX.unlink()


def reset_flake_counter() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    if FLAKE_COUNTER.exists():
        FLAKE_COUNTER.unlink()


def _purge_lab_modules() -> None:
    for key in list(sys.modules):
        if key.startswith("aud0052_lab_"):
            del sys.modules[key]


def _load(path: Path, key: str):
    spec = importlib.util.spec_from_file_location(key, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def run_session(
    items: list[dict[str, Any]],
    *,
    repo: Path,
    repeat_mode: bool = False,
) -> dict[str, Any]:
    """Execute executable items in the given order in one process.

    Shared module/file state is preserved across items in the session so that
    order dependence is visible. Box file is cleared at session start.
    """
    _purge_lab_modules()
    reset_box()
    env_was = os.environ.get(REPEAT_ENV)
    if repeat_mode:
        os.environ[REPEAT_ENV] = "1"
    else:
        os.environ.pop(REPEAT_ENV, None)
    loaded: dict[str, Any] = {}
    outcomes: dict[str, str] = {}
    messages: dict[str, str] = {}
    order = nodeids(items)
    try:
        for item in items:
            nid = item["nodeid"]
            if not item.get("executable"):
                outcomes[nid] = "not-run"
                continue
            path = repo / item["path"]
            key = "aud0052_lab_" + item["path"].replace("/", "_").replace(".", "_")
            try:
                if key not in loaded:
                    loaded[key] = _load(path, key)
                fn = getattr(loaded[key], item["qualname"])
                fn()
                outcomes[nid] = "passed"
            except AssertionError as exc:
                outcomes[nid] = "failed"
                messages[nid] = str(exc) or "AssertionError"
            except Exception as exc:
                outcomes[nid] = "error"
                messages[nid] = f"{type(exc).__name__}: {exc}"
                traceback.format_exc()
    finally:
        if env_was is None:
            os.environ.pop(REPEAT_ENV, None)
        else:
            os.environ[REPEAT_ENV] = env_was
    return {
        "order": order,
        "outcomes": outcomes,
        "messages": messages,
        "repeat_mode": repeat_mode,
    }


def orders_differ(orders: list[list[str]]) -> bool:
    tuples = {tuple(o) for o in orders}
    return len(tuples) >= 2
