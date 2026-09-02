#!/usr/bin/env python3
"""Live project census and declared-enforcement runner for AUD-0051."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from coverage_extract import extract_coverage

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0051"
OUT_REL = "command-center/audit/AUD-0051-coverage-baseline.json"
SCHEMA_REL = "command-center/schema/audit-metric-baseline.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0051 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "What is the measured line and branch coverage per project today, does "
    "each project have a .coverage-thresholds.json, and does its declared "
    "enforcement command actually run?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0051/probe1_enforcement.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0051/probe2_not_checked.py"
)
SKIP = {
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "dist",
    "build",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
}
PROBE_MARK = "/p2-wave/probes/"
FIXTURE_GATED = (
    "command-center/p2-wave/probes/AUD-0051/fixtures/gated_inoperable"
)
FIXTURE_PLAIN = (
    "command-center/p2-wave/probes/AUD-0051/fixtures/plain_project"
)
CI_WORKFLOW = ".github/workflows/quality.yml"


def skipped(path: Path) -> bool:
    return any(part in SKIP for part in path.parts)


def in_probe_tree(path: Path) -> bool:
    posix = path.as_posix().replace("\\", "/")
    return PROBE_MARK in posix


def run_cmd(argv: list[str], cwd: Path, timeout: int = 60) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        p = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except OSError as exc:
        return 127, f"OSError:{type(exc).__name__}:{exc}"
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def _manifests(root: Path) -> list[str]:
    names = []
    for name in (
        "pyproject.toml",
        "package.json",
        "pytest.ini",
        "setup.py",
        "setup.cfg",
        ".coverage-thresholds.json",
    ):
        if (root / name).is_file():
            names.append(name)
    return names


def _kinds(root: Path, manifests: list[str]) -> list[str]:
    kinds: list[str] = []
    if any(
        m in manifests
        for m in ("pyproject.toml", "pytest.ini", "setup.py", "setup.cfg")
    ) or any(root.glob("*.py")) or (root / "tests").is_dir():
        kinds.append("python")
    if "package.json" in manifests:
        kinds.append("node")
    if not kinds:
        kinds.append("unknown")
    return kinds


def inspect_project(rel: str) -> dict:
    root = REPO / rel
    manifests = _manifests(root)
    kinds = _kinds(root, manifests)
    tf = root / ".coverage-thresholds.json"
    has = tf.is_file()
    thresholds = None
    cmd = None
    if has:
        try:
            data = json.loads(tf.read_text(encoding="utf-8"))
            thresholds = data.get("thresholds")
            cmd = (data.get("enforcement") or {}).get("command")
        except Exception as exc:  # noqa: BLE001
            thresholds = f"UNPARSEABLE:{type(exc).__name__}"
    tests_dir = (root / "tests").is_dir()
    guessed = f"python3 -m pytest {rel}/tests -q" if tests_dir else None
    if has:
        provenance = (
            "thresholds file present; coverage number awaits a successful "
            "enforcement run that emits a coverage table"
        )
    else:
        provenance = (
            "no .coverage-thresholds.json in this project -- absence is "
            "reported as NOT-CHECKED, never folded into a pass"
        )
    py_count = 0
    if root.is_dir():
        py_count = sum(
            1
            for p in root.rglob("*.py")
            if not skipped(p) and not in_probe_tree(p)
        )
    return {
        "path": rel,
        "kinds": kinds,
        "manifests": manifests,
        "has_thresholds_file": has,
        "thresholds": thresholds,
        "enforcement_command": cmd,
        "coverage": "NOT-CHECKED",
        "coverage_provenance": provenance,
        "has_tests_dir": tests_dir,
        "guessed_test_command": guessed,
        "enforcement_command_runs": None,
        "python_file_count": py_count,
    }


def discover_live() -> list[dict]:
    projects: dict[str, dict] = {}
    tools = REPO / "tools"
    if tools.is_dir():
        for child in sorted(tools.iterdir()):
            if not child.is_dir() or child.name.startswith(".") or child.name in SKIP:
                continue
            rel = child.relative_to(REPO).as_posix()
            py_files = [
                p
                for p in child.rglob("*.py")
                if not skipped(p)
            ]
            if py_files or (child / "tests").is_dir():
                projects[rel] = inspect_project(rel)

    for pat, _kind in (
        ("pyproject.toml", "python"),
        ("package.json", "node"),
        ("pytest.ini", "python"),
        (".coverage-thresholds.json", "gated"),
    ):
        for path in REPO.rglob(pat):
            if skipped(path) or in_probe_tree(path):
                continue
            rel = path.parent.relative_to(REPO).as_posix() or "."
            if rel not in projects:
                projects[rel] = inspect_project(rel)
            elif pat == ".coverage-thresholds.json":
                projects[rel] = inspect_project(rel)
    return sorted(projects.values(), key=lambda r: r["path"])


def read_ci_coverage_job() -> dict:
    rel = CI_WORKFLOW
    path = REPO / rel
    if not path.is_file():
        return {
            "path": rel,
            "present": False,
            "job_name_contains_coverage": False,
            "command_has_coverage_instrumentation": False,
            "text": "",
        }
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    instrumented = any(
        token in lowered
        for token in ("--cov", "pytest-cov", "coverage run", "test:coverage")
    )
    return {
        "path": rel,
        "present": True,
        "job_name_contains_coverage": "gate-tests-coverage" in lowered
        or "coverage" in lowered,
        "command_has_coverage_instrumentation": instrumented,
        "declares_pytest_without_cov": "python -m pytest" in lowered
        and not instrumented,
        "text": text,
    }


def parse_argv(command: str) -> list[str]:
    import shlex

    return shlex.split(command)


def run_enforcement(command: str, cwd: Path, timeout: int = 60) -> dict:
    argv = parse_argv(command) if command else []
    code, out = (
        run_cmd(argv, cwd=cwd, timeout=timeout)
        if argv
        else (127, "no command declared")
    )
    val, why = extract_coverage(out)
    return {
        "declared_command": command,
        "argv": argv,
        "cwd": cwd.relative_to(REPO).as_posix() if cwd != REPO else ".",
        "exit_code": code,
        "coverage": val,
        "coverage_provenance": why,
        "output_tail": out[-1500:],
    }


def run_live_enforcement(projects: list[dict]) -> list[dict]:
    runs = []
    for row in projects:
        if not row.get("has_thresholds_file"):
            continue
        cmd = row.get("enforcement_command")
        wd = REPO / row["path"]
        result = run_enforcement(cmd if isinstance(cmd, str) else "", wd)
        result["project"] = row["path"]
        result["kind"] = "live-thresholds"
        pkg = wd / "package.json"
        script_present = None
        if pkg.is_file() and isinstance(cmd, str):
            try:
                scripts = json.loads(pkg.read_text(encoding="utf-8")).get("scripts") or {}
                target = cmd.split()[-1] if cmd.split() else ""
                script_present = target in scripts
                row["declared_scripts"] = sorted(scripts)
            except Exception:  # noqa: BLE001
                script_present = None
        result["script_present_in_package_json"] = script_present
        row["coverage"] = result["coverage"]
        row["coverage_provenance"] = result["coverage_provenance"]
        row["enforcement_command_runs"] = result["exit_code"] == 0
        runs.append(result)
    return runs


def run_inoperable_fixture() -> dict:
    rel = FIXTURE_GATED
    row = inspect_project(rel)
    cmd = row.get("enforcement_command") or ""
    result = run_enforcement(cmd, REPO, timeout=30)
    result["project"] = rel
    result["kind"] = "control-inoperable-gate"
    result["has_thresholds_file"] = row["has_thresholds_file"]
    result["script_present_in_package_json"] = None
    return result


def run_plain_pytest_without_coverage() -> dict:
    test_path = f"{FIXTURE_PLAIN}/test_plain.py"
    argv = ["python3", "-m", "pytest", test_path, "-q", "--tb=no"]
    code, out = run_cmd(argv, cwd=REPO, timeout=45)
    val, why = extract_coverage(out)
    return {
        "project": FIXTURE_PLAIN,
        "kind": "control-pytest-without-coverage-flag",
        "declared_command": " ".join(argv),
        "argv": argv,
        "cwd": ".",
        "exit_code": code,
        "coverage": val,
        "coverage_provenance": why,
        "output_tail": out[-1500:],
        "used_coverage_flag": False,
    }


def coverage_tooling() -> dict:
    tools = {}
    for mod in ("coverage", "pytest_cov"):
        code, out = run_cmd(
            ["python3", "-c", f"import {mod}"],
            cwd=REPO,
            timeout=15,
        )
        tools[mod] = {"importable": code == 0, "output_tail": out[-200:]}
    return tools
