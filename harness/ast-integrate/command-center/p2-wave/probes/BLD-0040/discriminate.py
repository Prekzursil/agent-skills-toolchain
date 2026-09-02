#!/usr/bin/env python3
"""Wrong-but-non-crashing return injection for BLD-0040 probe2.

Copies planted fixtures into a temp dir, rewrites compute_score to return 0,
and checks that test_no_crash_only stays green while test_exact_value goes red.
The shared tree is never mutated.
"""
from __future__ import annotations

import hashlib
import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
SUBJECT = FIXTURES / "subject.py"
TESTS = FIXTURES / "test_oracles.py"
MUTANT = '''"""Isolated mutant: wrong-but-non-crashing compute_score."""


def compute_score(values):
    return 0


def produce_report():
    return {"sum": compute_score([1, 2, 3]), "ok": True}
'''


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path, modname: str):
    spec = importlib.util.spec_from_file_location(modname, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


def _call(mod, name: str) -> str:
    try:
        getattr(mod, name)()
        return "PASS"
    except AssertionError:
        return "FAIL"
    except Exception as exc:
        return f"ERROR:{type(exc).__name__}"


def _run_pair(tmpdir: Path, tag: str) -> dict:
    saved = sys.modules.pop("subject", None)
    inserted = False
    if str(tmpdir) not in sys.path:
        sys.path.insert(0, str(tmpdir))
        inserted = True
    try:
        sys.modules.pop("subject", None)
        tests = _load(tmpdir / "test_oracles.py", f"bld0040_oracles_{tag}")
        return {
            "test_no_crash_only": _call(tests, "test_no_crash_only"),
            "test_exact_value": _call(tests, "test_exact_value"),
        }
    finally:
        if inserted:
            try:
                sys.path.remove(str(tmpdir))
            except ValueError:
                pass
        sys.modules.pop("subject", None)
        sys.modules.pop(f"bld0040_oracles_{tag}", None)
        if saved is not None:
            sys.modules["subject"] = saved


def run_discrimination() -> dict:
    before = sha256_file(SUBJECT)
    with tempfile.TemporaryDirectory(prefix="bld0040-disc-") as raw:
        tmp = Path(raw)
        shutil.copy2(SUBJECT, tmp / "subject.py")
        shutil.copy2(TESTS, tmp / "test_oracles.py")
        baseline = _run_pair(tmp, "base")
        (tmp / "subject.py").write_text(MUTANT, encoding="utf-8")
        mutated = _run_pair(tmp, "mut")
    after = sha256_file(SUBJECT)
    ok = (
        baseline["test_no_crash_only"] == "PASS"
        and baseline["test_exact_value"] == "PASS"
        and mutated["test_no_crash_only"] == "PASS"
        and mutated["test_exact_value"] == "FAIL"
        and before == after
    )
    return {
        "ok": ok,
        "shared_tree_unchanged": before == after,
        "shared_subject_sha256": before,
        "baseline": baseline,
        "mutated": mutated,
        "injected_return": 0,
        "broken_function": "compute_score",
        "no_crash_stayed_green": mutated["test_no_crash_only"] == "PASS",
        "exact_value_went_red": mutated["test_exact_value"] == "FAIL",
    }


if __name__ == "__main__":
    import json

    rec = run_discrimination()
    print(json.dumps(rec, indent=2))
    raise SystemExit(0 if rec["ok"] else 1)


run_discrimination = run_discrimination
