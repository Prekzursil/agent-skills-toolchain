"""Shared invocation-parity measurements for TST-0128 probes and emit."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROBE_ROOT = Path(__file__).resolve().parent
SRC = PROBE_ROOT / "src"
REPO = PROBE_ROOT.parents[3]

EXPECTED_NODE_IDS = [
    "test_core.py::test_add",
    "test_core.py::test_add_zero",
    "test_extra.py::test_secret",
]


def _parse_report(text: str) -> dict:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            doc = json.loads(stripped)
            if isinstance(doc, dict) and "collected_node_ids" in doc:
                return doc
    raise ValueError("no collector JSON in output")


def _run(cmd: list[str], cwd: Path, extra_env: dict[str, str] | None = None) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # Do not set PYTHONSAFEPATH: python -m must keep its default cwd-on-sys.path
    # behaviour, which is the mechanical difference from a console script.
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    blob = ((proc.stdout or "") + (proc.stderr or "")).strip()
    try:
        report = _parse_report(blob)
    except ValueError:
        report = {
            "ok": False,
            "collected_node_ids": [],
            "collected_set": [],
            "outcomes": {},
            "collection_errors": [{"error": "no-json", "msg": blob[-1500:]}],
            "passed": [],
            "failed": [],
        }
    report["exit_code"] = proc.returncode
    report["raw_tail"] = blob[-2000:]
    report["command"] = cmd
    return report


def run_python_m_source(scratch: Path) -> dict:
    """python -m entry: source tree on PYTHONPATH, cwd is an empty scratch dir."""
    return _run(
        [sys.executable, "-m", "tst0128run"],
        cwd=scratch,
        extra_env={"PYTHONPATH": str(SRC)},
    )


def run_console(prefix: Path, scratch: Path) -> dict:
    return _run([str(prefix / "bin" / "tst0128-pytest")], cwd=scratch)


def run_ci(prefix: Path, scratch: Path) -> dict:
    return _run([str(prefix / "bin" / "tst0128-ci")], cwd=scratch)


def materialize(prefix: Path, planted: bool) -> Path:
    sys.path.insert(0, str(SRC))
    from tst0128run.install import materialize as _mat  # noqa: WPS433

    return _mat(prefix, planted=planted)


def good_parity() -> dict:
    with tempfile.TemporaryDirectory(prefix="tst0128-good-") as td:
        root = Path(td)
        prefix = materialize(root / "prefix", planted=False)
        scratch = root / "cwd"
        scratch.mkdir()
        python_m = run_python_m_source(scratch)
        console = run_console(prefix, scratch)
        ci = run_ci(prefix, scratch)
        sets = {
            "python-m": set(python_m.get("collected_set") or python_m["collected_node_ids"]),
            "console-script": set(
                console.get("collected_set") or console["collected_node_ids"]
            ),
            "ci-entry": set(ci.get("collected_set") or ci["collected_node_ids"]),
        }
        expected = set(EXPECTED_NODE_IDS)
        sets_identical = sets["python-m"] == sets["console-script"] == sets["ci-entry"]
        match_expected = sets["python-m"] == expected
        outcomes = {
            "python-m": python_m.get("outcomes") or {},
            "console-script": console.get("outcomes") or {},
            "ci-entry": ci.get("outcomes") or {},
        }
        outcomes_identical = (
            outcomes["python-m"]
            == outcomes["console-script"]
            == outcomes["ci-entry"]
        )
        all_passed = (
            python_m.get("ok")
            and console.get("ok")
            and ci.get("ok")
            and python_m["exit_code"] == 0
            and console["exit_code"] == 0
            and ci["exit_code"] == 0
        )
        pass_ok = bool(
            sets_identical and match_expected and outcomes_identical and all_passed
        )
        return {
            "pass": pass_ok,
            "sets_identical": sets_identical,
            "outcomes_identical": outcomes_identical,
            "match_expected": match_expected,
            "expected_node_ids": sorted(expected),
            "sets": {k: sorted(v) for k, v in sets.items()},
            "outcomes": outcomes,
            "exits": {
                "python-m": python_m["exit_code"],
                "console-script": console["exit_code"],
                "ci-entry": ci["exit_code"],
            },
            "ok_flags": {
                "python-m": python_m.get("ok"),
                "console-script": console.get("ok"),
                "ci-entry": ci.get("ok"),
            },
        }


def planted_break() -> dict:
    with tempfile.TemporaryDirectory(prefix="tst0128-plant-") as td:
        root = Path(td)
        prefix = materialize(root / "prefix", planted=True)
        extra_installed = (prefix / "lib" / "tst0128pkg" / "extra.py").exists()
        scratch = root / "cwd"
        scratch.mkdir()
        python_m = run_python_m_source(scratch)
        console = run_console(prefix, scratch)
        src_set = set(python_m.get("collected_set") or python_m["collected_node_ids"])
        con_set = set(console.get("collected_set") or console["collected_node_ids"])
        secret = "test_extra.py::test_secret"
        source_green = (
            python_m.get("ok")
            and python_m["exit_code"] == 0
            and src_set == set(EXPECTED_NODE_IDS)
            and python_m.get("outcomes", {}).get(secret) == "passed"
        )
        console_sees = (
            not extra_installed
            and secret not in con_set
            and bool(console.get("collection_errors"))
            and console["exit_code"] != 0
        )
        differ = src_set != con_set
        pass_ok = bool(source_green and console_sees and differ)
        return {
            "pass": pass_ok,
            "omitted_module": "tst0128pkg/extra.py",
            "extra_installed": extra_installed,
            "source_python_m_still_green": source_green,
            "console_script_sees_break": console_sees,
            "collection_sets_differ": differ,
            "source_set": sorted(src_set),
            "console_set": sorted(con_set),
            "source_exit": python_m["exit_code"],
            "console_exit": console["exit_code"],
            "console_collection_errors": console.get("collection_errors") or [],
        }


def live_ci_census() -> dict:
    """AST collection census of the live command-center suite vs quality.yml.

    Outcomes are NOT-CHECKED: pytest is not installed and pip/ensurepip are
    absent, so the live CI command cannot be re-executed here.
    """
    import ast

    tests_dir = REPO / "tools" / "command-center" / "tests"
    workflow = REPO / ".github" / "workflows" / "quality.yml"
    ci_text = workflow.read_text(encoding="utf-8") if workflow.is_file() else ""
    ci_file = "tools/command-center/tests/test_vfields_ci.py"
    ci_mentions = ci_file.replace("\\", "/") in ci_text.replace("\\", "/")
    uses_python_m = "python -m pytest" in ci_text
    uses_console = (
        "\n          pytest " in ci_text or ci_text.strip().endswith("\npytest")
    )

    def node_ids(path: Path) -> list[str]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel = path.name
        return [
            f"{rel}::{node.name}"
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        ]

    all_ids: list[str] = []
    if tests_dir.is_dir():
        for path in sorted(tests_dir.glob("test_*.py")):
            all_ids.extend(node_ids(path))
    ci_path = REPO / ci_file
    ci_ids = node_ids(ci_path) if ci_path.is_file() else []
    return {
        "pytest_installed": False,
        "workflow_path": ".github/workflows/quality.yml",
        "workflow_present": workflow.is_file(),
        "ci_command_uses_python_m_pytest": uses_python_m,
        "ci_command_uses_pytest_console_script": uses_console,
        "ci_mentions_vfields_file": ci_mentions,
        "full_suite_node_ids": all_ids,
        "ci_file_node_ids": ci_ids,
        "full_suite_count": len(all_ids),
        "ci_file_count": len(ci_ids),
        "collection_sets_would_differ": set(all_ids) != set(ci_ids),
        "outcomes": "NOT-CHECKED",
        "reason": (
            "pytest is not installed; pip and ensurepip are absent. Live "
            "command-center outcomes were not re-run. Fixture suite below "
            "is the executable proof."
        ),
    }
