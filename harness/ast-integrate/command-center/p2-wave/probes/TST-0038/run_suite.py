#!/usr/bin/env python3
"""Run TST-0038 conformance tests without requiring pytest to be installed."""

from __future__ import annotations

import importlib.util
import inspect
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[4]
MOD = REPO / "tools" / "command-center" / "tests" / "test_work_unit_conformance.py"


def load_mod():
    sys.path.insert(0, str(REPO / "tools" / "command-center"))
    spec = importlib.util.spec_from_file_location("test_work_unit_conformance", MOD)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {MOD}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    mod = load_mod()
    failed = []
    ran = 0
    for name, fn in inspect.getmembers(mod, inspect.isfunction):
        if not name.startswith("test_"):
            continue
        ran += 1
        params = inspect.signature(fn).parameters
        try:
            if "tmp_path" in params:
                tmp = Path(tempfile.mkdtemp(prefix="tst0038-"))
                try:
                    fn(tmp)
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)
            else:
                fn()
            print(f"  PASS {name}")
        except Exception as exc:
            failed.append(f"{name}: {type(exc).__name__}: {exc}")
            print(f"  FAIL {name}: {type(exc).__name__}: {exc}")
    if failed:
        print(f"FAILED:TST-0038-suite ran={ran} failed={len(failed)}")
        return 1
    print(f"SUCCESS:TST-0038-suite ran={ran} failed=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
