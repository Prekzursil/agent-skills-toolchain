"""Collect and run test_* functions. Emits pytest-shaped node ids as a set.

pytest is not installed on this worktree; this collector is the executable
stand-in so python -m, console-script, and CI wrappers can be compared as
sets without a pip/network dependency.
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import os
import sys
import traceback
from pathlib import Path


def layout_from_here() -> tuple[Path, Path]:
    """Return (pkg_root_on_sys_path, tests_root) from this file's location."""
    run_dir = Path(__file__).resolve().parent
    parent = run_dir.parent
    installed_tests = parent / "tests"
    if installed_tests.is_dir() and (parent / "tst0128pkg").is_dir():
        return parent, installed_tests
    # Source tree: .../probes/TST-0128/src/tst0128run/collect.py
    src = parent
    root = src.parent
    return src, root / "tests"


def collect_and_run(pkg_root: Path, tests_root: Path) -> dict:
    pkg_root = pkg_root.resolve()
    tests_root = tests_root.resolve()
    # Console-script semantics vs python -m: callers decide whether cwd stays
    # on sys.path. We always put the package root first.
    cleaned = [p for p in sys.path if p not in ("", os.getcwd())]
    sys.path[:] = [str(pkg_root)] + cleaned

    collected: list[str] = []
    outcomes: dict[str, str] = {}
    collection_errors: list[dict] = []

    for path in sorted(tests_root.glob("test_*.py")):
        rel = path.name
        mod_name = f"_tst0128_{path.stem}_{os.getpid()}"
        spec = importlib.util.spec_from_file_location(mod_name, path)
        if spec is None or spec.loader is None:
            collection_errors.append(
                {"path": rel, "error": "SpecError", "msg": "no loader"}
            )
            continue
        try:
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)
        except Exception as exc:
            collection_errors.append(
                {
                    "path": rel,
                    "error": type(exc).__name__,
                    "msg": str(exc),
                    "trace": traceback.format_exc(limit=4),
                }
            )
            sys.modules.pop(mod_name, None)
            continue
        for name, fn in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith("test_"):
                continue
            if fn.__module__ != module.__name__:
                continue
            nid = f"{rel}::{name}"
            collected.append(nid)
            try:
                fn()
            except Exception as exc:
                outcomes[nid] = f"failed:{type(exc).__name__}:{exc}"
            else:
                outcomes[nid] = "passed"

    passed = [n for n, v in outcomes.items() if v == "passed"]
    failed = [n for n, v in outcomes.items() if v != "passed"]
    ok = not collection_errors and not failed and bool(collected)
    return {
        "ok": ok,
        "pkg_root": str(pkg_root),
        "tests_root": str(tests_root),
        "collected_node_ids": collected,
        "collected_set": sorted(set(collected)),
        "outcomes": outcomes,
        "passed": passed,
        "failed": failed,
        "collection_errors": collection_errors,
    }


def emit(entry: str, argv: list[str] | None = None) -> int:
    pkg_root, tests_root = layout_from_here()
    report = collect_and_run(pkg_root, tests_root)
    report["entry"] = entry
    report["argv0"] = sys.argv[0] if argv is None else (argv[0] if argv else "")
    report["cwd"] = os.getcwd()
    report["sys_path0"] = sys.path[0] if sys.path else ""
    print(json.dumps(report, sort_keys=True))
    if report["ok"]:
        print(
            f"SUCCESS:tst0128-{entry} collected={len(report['collected_set'])} "
            f"passed={len(report['passed'])}"
        )
        return 0
    print(
        f"FAILED:tst0128-{entry} collected={len(report['collected_set'])} "
        f"errors={len(report['collection_errors'])} failed={len(report['failed'])}"
    )
    return 1
