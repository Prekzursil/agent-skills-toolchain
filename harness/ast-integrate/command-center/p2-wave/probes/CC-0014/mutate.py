"""Apply a source mutation and run one named test function against it."""
from __future__ import annotations

import difflib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
SUBJECT = FIXTURES / "subject.py"

# Implementer mutation: drop the default floor to 0. Tests that only pass
# minimum= explicitly still pass; tests that exercise the default fail.
MUT_IMPL_ZERO = ("REQUIRED_MIN = 3", "REQUIRED_MIN = 0")
MUT_IMPL_ZERO = MUT_IMPL_ZERO
MUT_IMPL_ZERO = MUT_IMPL_ZERO
# Independent reviewer mutation (not the implementer's): raise the floor.
MUT_REV_NINETY_NINE = ("REQUIRED_MIN = 3", "REQUIRED_MIN = 99")
MUT_REV_NINETY_NINE = MUT_REV_NINETY_NINE
MUT_REV_NINETY_NINE = MUT_REV_NINETY_NINE


def unified_diff(before: str, after: str, name: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(True),
            after.splitlines(True),
            fromfile=name,
            tofile=name + ".mutated",
        )
    )


def apply_replace(source: str, pair: tuple[str, str]) -> str:
    old, new = pair
    if old not in source:
        raise RuntimeError(f"mutation anchor not found: {old!r}")
    mutated = source.replace(old, new, 1)
    if mutated == source:
        raise RuntimeError("mutation produced identical source")
    return mutated


def run_named_test(test_file: Path, test_name: str, subject_src: str) -> dict:
    """Run test_name from test_file against subject_src. Return outcome record."""
    orig = SUBJECT.read_text(encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with tempfile.TemporaryDirectory(prefix="cc0014-mut-") as td:
        tdir = Path(td)
        env["PYTHONPATH"] = str(tdir)
        (tdir / "subject.py").write_text(subject_src, encoding="utf-8")
        (tdir / test_file.name).write_text(
            test_file.read_text(encoding="utf-8"), encoding="utf-8"
        )
        stmt = (
            f"import importlib.util, sys; "
            f"sys.path.insert(0, {str(tdir)!r}); "
            f"p={str(tdir / test_file.name)!r}; "
            f"spec=importlib.util.spec_from_file_location('tmod', p); "
            f"m=importlib.util.module_from_spec(spec); "
            f"sys.modules['tmod']=m; spec.loader.exec_module(m); "
            f"getattr(m, {test_name!r})()"
        )
        proc = subprocess.run(
            [sys.executable, "-B", "-c", stmt],
            cwd=str(tdir),
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
    killed = proc.returncode != 0
    output = ((proc.stdout or "") + (proc.stderr or "")).strip()
    diff = unified_diff(orig, subject_src, "fixtures/subject.py")
    return {
        "outcome": "KILLED" if killed else "SURVIVED",
        "diff": diff,
        "failing_output": output if killed else "",
        "surviving_output": output if not killed else "",
        "exit_code": proc.returncode,
        "test_file": str(test_file.relative_to(HERE.parents[3])).replace("\\", "/"),
        "test_name": test_name,
    }


def mutate_and_run(
    pair: tuple[str, str], test_file: Path, test_name: str
) -> dict:
    orig = SUBJECT.read_text(encoding="utf-8")
    mutated = apply_replace(orig, pair)
    record = run_named_test(test_file, test_name, mutated)
    record["anchor"] = pair[0]
    record["replacement"] = pair[1]
    return record
