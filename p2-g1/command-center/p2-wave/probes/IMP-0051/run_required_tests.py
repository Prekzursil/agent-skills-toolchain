#!/usr/bin/env python3
"""IMP-0051 required tests runner.

The required catalog tests live in tools/plugin/tests/test_error_taxonomy.py
as plain assert functions with a __main__ runner. This wrapper imports the
module, executes its test functions, and requires every one to pass.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TEST_FILE = REPO / "tools" / "plugin" / "tests" / "test_error_taxonomy.py"


def main() -> int:
    spec = importlib.util.spec_from_file_location("test_error_taxonomy", TEST_FILE)
    if spec is None or spec.loader is None:
        print("FAILED:IMP-0051-tests module load")
        return 2
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fns = [n for n in dir(mod) if n.startswith("test_")]
    results: dict[str, bool] = {}
    for name in fns:
        try:
            getattr(mod, name)()
            results[name] = True
        except Exception as exc:  # noqa: BLE001
            results[name] = False
            print(f"  {name} raised: {exc}")
    ok = bool(results) and all(results.values())
    print(json.dumps({"tests": results, "pass": ok}, sort_keys=True))
    if not ok:
        print("FAILED:IMP-0051-tests required taxonomy tests failed")
        return 1
    print("SUCCESS:IMP-0051-tests required taxonomy tests pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
