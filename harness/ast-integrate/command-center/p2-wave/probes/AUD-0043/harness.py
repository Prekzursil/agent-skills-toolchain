"""Live source-pytest vs installed-console-script harness for AUD-0043."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from scenario import (
    CONSOLE_NAME,
    HERE,
    INCLUDE_GOOD,
    INCLUDE_MUTANT,
    PKG_REL,
    REPO,
    WHEELS_REL,
)

PKG = HERE / "pkg"
WHEELS = HERE / "wheels"
PASSED_RE = re.compile(r"(\d+)\s+passed")
COLLECTED_RE = re.compile(r"(\d+)\s+test[s]?\s+collected")
FAILED_RE = re.compile(r"(\d+)\s+failed")


def child_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"):
        env.pop(key, None)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return env


def run(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd),
        env=env or child_env(),
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def outside_repo(path: Path, repo: Path = REPO) -> bool:
    repo = repo.resolve()
    resolved = path.resolve()
    if resolved == repo:
        return False
    try:
        resolved.relative_to(repo)
        return False
    except ValueError:
        return True


def repo_hits(sys_path: list[str], cwd: Path) -> list[str]:
    repo = REPO.resolve()
    hits: list[str] = []
    for entry in sys_path:
        if entry in ("", "."):
            target = cwd.resolve()
        else:
            try:
                target = Path(entry).resolve()
            except OSError:
                continue
        try:
            target.relative_to(repo)
        except ValueError:
            continue
        hits.append(entry if entry not in ("", ".") else f"<cwd:{target}>")
    return hits


def parse_report(stdout: str) -> dict[str, Any]:
    text = (stdout or "").strip()
    if not text:
        return {}
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return {}
        doc = json.loads(text[start : end + 1])
    return doc if isinstance(doc, dict) else {}


def copy_pkg(dest: Path, *, mutant: bool) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(PKG, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    pyproject = dest / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    if INCLUDE_GOOD not in text:
        raise RuntimeError("good-include-line-missing")
    if mutant:
        text = text.replace(INCLUDE_GOOD, INCLUDE_MUTANT, 1)
        if INCLUDE_GOOD in text or INCLUDE_MUTANT not in text:
            raise RuntimeError("failed-to-plant-include-omit")
        pyproject.write_text(text, encoding="utf-8")
    return dest


def make_venv(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    proc = run(["python3", "-m", "venv", str(path)], cwd=REPO, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError("venv-failed " + (proc.stderr or proc.stdout or "")[-1500:])
    return path


def venv_python(venv: Path) -> Path:
    return venv / "bin" / "python"


def venv_script(venv: Path) -> Path:
    return venv / "bin" / CONSOLE_NAME


def pip_install(venv: Path, *args: str, timeout: int = 120) -> str:
    proc = run(
        [str(venv_python(venv)), "-m", "pip", "install", *args],
        cwd=venv,
        timeout=timeout,
    )
    log = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        raise RuntimeError("pip-install-failed " + log[-2000:])
    return log


def install_pytest(venv: Path) -> str:
    wheels = list(WHEELS.glob("pytest-*.whl")) if WHEELS.is_dir() else []
    if wheels:
        return pip_install(
            venv,
            "--no-index",
            "--find-links",
            str(WHEELS),
            "pytest==8.3.3",
        )
    return pip_install(venv, "pytest==8.3.3")


def build_wheel(src: Path, dist: Path) -> Path:
    dist.mkdir(parents=True, exist_ok=True)
    proc = run(
        [
            "python3",
            "-m",
            "pip",
            "wheel",
            str(src),
            "-w",
            str(dist),
            "--no-deps",
            "--no-build-isolation",
        ],
        cwd=src,
        timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "wheel-build-failed "
            + (proc.stdout or "")[-1500:]
            + "\n"
            + (proc.stderr or "")[-1500:]
        )
    wheels = sorted(dist.glob("aud0043_subject-*.whl"))
    if not wheels:
        raise RuntimeError("wheel-missing-after-build " + (proc.stdout or "")[-800:])
    return wheels[-1]


def parse_pytest(stdout: str, stderr: str) -> dict[str, Any]:
    text = (stdout or "") + "\n" + (stderr or "")
    passed = FAILED = collected = None
    m = PASSED_RE.search(text)
    if m:
        passed = int(m.group(1))
    m = FAILED_RE.search(text)
    if m:
        FAILED = int(m.group(1))
    m = COLLECTED_RE.search(text)
    if m:
        collected = int(m.group(1))
    names = [
        line.strip()
        for line in (stdout or "").splitlines()
        if "::" in line and line.strip().startswith("tests/")
    ]
    if collected is None and names:
        collected = len(names)
    return {
        "passed": passed,
        "failed": FAILED,
        "collected": collected,
        "nodeids": names[:20],
        "stdout_tail": (stdout or "")[-2000:],
        "stderr_tail": (stderr or "")[-800:],
    }


def run_source_pytest(src: Path, pytest_python: Path) -> dict[str, Any]:
    env = child_env()
    env["PYTHONPATH"] = str((src / "src").resolve())
    tests = src / "tests"
    collect = run(
        [
            str(pytest_python),
            "-m",
            "pytest",
            str(tests),
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=src,
        env=env,
        timeout=60,
    )
    executed = run(
        [
            str(pytest_python),
            "-m",
            "pytest",
            str(tests),
            "-q",
            "--tb=line",
            "-p",
            "no:cacheprovider",
        ],
        cwd=src,
        env=env,
        timeout=60,
    )
    parsed_collect = parse_pytest(collect.stdout or "", collect.stderr or "")
    parsed_run = parse_pytest(executed.stdout or "", executed.stderr or "")
    collected = parsed_collect["collected"]
    if collected is None:
        collected = parsed_run["collected"]
    command = (
        f"PYTHONPATH=src {pytest_python} -m pytest tests -q --tb=line "
        f"-p no:cacheprovider"
    )
    return {
        "command": command,
        "cwd": str(src.resolve()),
        "pythonpath": env["PYTHONPATH"],
        "collect_returncode": collect.returncode,
        "returncode": executed.returncode,
        "collected": collected,
        "passed": parsed_run["passed"],
        "failed": parsed_run["failed"],
        "nodeids": parsed_collect["nodeids"] or parsed_run["nodeids"],
        "stdout_tail": parsed_run["stdout_tail"],
        "stderr_tail": parsed_run["stderr_tail"],
        "ok": executed.returncode == 0
        and (collected or 0) > 0
        and (parsed_run["passed"] or 0) > 0,
    }


def invoke_console(venv: Path, cwd: Path) -> dict[str, Any]:
    script = venv_script(venv)
    if not script.is_file():
        return {
            "command": [str(script)],
            "cwd": str(cwd),
            "returncode": 127,
            "stdout": "",
            "stderr": "console-script-absent",
            "report": {},
            "script_path": str(script),
            "script_exists": False,
        }
    proc = run([str(script)], cwd=cwd, timeout=30)
    doc = parse_report(proc.stdout or "")
    return {
        "command": [str(script)],
        "cwd": str(cwd),
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-4000:],
        "stderr": (proc.stderr or "")[-2000:],
        "report": doc,
        "script_path": str(script.resolve()),
        "script_exists": True,
    }


def run_installed(src: Path, work: Path) -> dict[str, Any]:
    dist = work / "dist"
    venv = work / "venv"
    scratch = work / "run-cwd"
    scratch.mkdir(parents=True, exist_ok=True)
    wheel = build_wheel(src, dist)
    make_venv(venv)
    pip_log = pip_install(venv, "--no-deps", str(wheel))
    script = venv_script(venv)
    console = invoke_console(venv, scratch)
    report = console.get("report") or {}
    hits = repo_hits(list(report.get("sys_path") or []), scratch)
    ok = (
        console.get("returncode") == 0
        and bool(report.get("ok"))
        and bool(console.get("script_exists"))
        and outside_repo(venv)
        and outside_repo(script)
        and not hits
    )
    return {
        "wheel_path": str(wheel.resolve()),
        "wheel_name": wheel.name,
        "venv_path": str(venv.resolve()),
        "resolved_script_path": str(script.resolve()) if script.exists() else "",
        "script_exists": script.is_file(),
        "script_outside_repo": outside_repo(script) if script.exists() else False,
        "venv_outside_repo": outside_repo(venv),
        "pip_install_output": pip_log[-4000:],
        "scratch_cwd": str(scratch.resolve()),
        "console": console,
        "console_ok": bool(ok),
        "console_repo_hits": hits,
        "report_error": report.get("error"),
        "checks": report.get("checks") or [],
    }


def pytest_python_for(work: Path) -> Path:
    venv = work / "pytest-venv"
    make_venv(venv)
    install_pytest(venv)
    return venv_python(venv)


def run_pair(work: Path | None = None) -> dict[str, Any]:
    owns = work is None
    tmp: tempfile.TemporaryDirectory[str] | None = None
    if work is None:
        tmp = tempfile.TemporaryDirectory(prefix="aud0043-")
        work = Path(tmp.name)
    try:
        good_src = copy_pkg(work / "src-good", mutant=False)
        mutant_src = copy_pkg(work / "src-mutant", mutant=True)
        py = pytest_python_for(work)
        source_good = run_source_pytest(good_src, py)
        source_mutant = run_source_pytest(mutant_src, py)
        installed_good = run_installed(good_src, work / "inst-good")
        installed_mutant = run_installed(mutant_src, work / "inst-mutant")
        both_states = (
            bool(source_good["ok"])
            and bool(source_mutant["ok"])
            and bool(installed_good["console_ok"])
            and not bool(installed_mutant["console_ok"])
        )
        return {
            "pkg_rel": PKG_REL,
            "wheels_rel": WHEELS_REL,
            "pytest_python": str(py),
            "source_good": source_good,
            "source_mutant": source_mutant,
            "installed_good": installed_good,
            "installed_mutant": installed_mutant,
            "parity_on_good_package": bool(source_good["ok"])
            and bool(installed_good["console_ok"]),
            "both_states_exclude_module": both_states,
            "source_stays_green_on_omit": bool(source_mutant["ok"]),
            "installed_turns_red_on_omit": not bool(installed_mutant["console_ok"]),
        }
    finally:
        if owns and tmp is not None:
            tmp.cleanup()
