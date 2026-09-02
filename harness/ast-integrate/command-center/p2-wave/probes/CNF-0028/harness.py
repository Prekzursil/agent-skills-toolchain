"""Live clean-venv wheel install harness for CNF-0028."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PKG = HERE / "pkg"
PAYLOAD_TOKEN = "CNF-0028-PACKAGED-PAYLOAD-v1"
DECOY_TOKEN = "DECOY-CWD-PAYLOAD-NOT-PACKAGED"
CONSOLE_NAME = "cnf0028-fix"
MODULE_NAME = "cnf0028_fix"
CATALOG_SENTINEL = (
    "SUCCESS:CNF-0028 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and sys.path was printed and "
    "contains no repo path, and both invocation routes were exercised. Any other "
    "terminal state is FAILED:CNF-0028 <classification> with the diagnostic tail attached."
)
DECOY_TOKEN = DECOY_TOKEN
PAYLOAD_TOKEN = PAYLOAD_TOKEN
CATALOG_SENTINEL = CATALOG_SENTINEL


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
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd),
        env=child_env(),
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def repo_hits(sys_path: list[str], cwd: Path, repo: Path = REPO) -> list[str]:
    repo = repo.resolve()
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


def parse_report(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
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


def build_wheel(src: Path, dist: Path) -> Path:
    dist.mkdir(parents=True, exist_ok=True)
    proc = run(
        [
            sys.executable,
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
    wheels = sorted(dist.glob("cnf0028_fix-*.whl"))
    if not wheels:
        raise RuntimeError("wheel-missing-after-build " + (proc.stdout or "")[-800:])
    return wheels[-1]


def make_venv(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    proc = run([sys.executable, "-m", "venv", str(path)], cwd=REPO, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError("venv-failed " + (proc.stderr or proc.stdout or "")[-1500:])
    return path


def venv_python(venv: Path) -> Path:
    return venv / "bin" / "python"


def venv_script(venv: Path) -> Path:
    return venv / "bin" / CONSOLE_NAME


def pip_install(venv: Path, wheel: Path) -> str:
    proc = run(
        [
            str(venv_python(venv)),
            "-m",
            "pip",
            "install",
            "--no-deps",
            str(wheel),
        ],
        cwd=venv,
        timeout=120,
    )
    log = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        raise RuntimeError("pip-install-failed " + log[-2000:])
    return log


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
    return {
        "command": [str(script)],
        "cwd": str(cwd),
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-4000:],
        "stderr": (proc.stderr or "")[-2000:],
        "report": parse_report(proc.stdout or ""),
        "script_path": str(script.resolve()),
        "script_exists": True,
    }


def invoke_python_m(py: Path, cwd: Path) -> dict[str, Any]:
    proc = run([str(py), "-m", MODULE_NAME], cwd=cwd, timeout=30)
    return {
        "command": [str(py), "-m", MODULE_NAME],
        "cwd": str(cwd),
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-4000:],
        "stderr": (proc.stderr or "")[-2000:],
        "report": parse_report(proc.stdout or ""),
        "executable": str(py.resolve()),
    }


def prepare_scratch(root: Path) -> Path:
    scratch = root / "run-cwd"
    scratch.mkdir(parents=True, exist_ok=True)
    (scratch / "payload.txt").write_text(DECOY_TOKEN + "\n", encoding="utf-8")
    return scratch


def _sys_path_of(report: dict[str, Any]) -> list[str]:
    return list(report.get("sys_path") or report.get("sys_path") or [])


def _route_ok(inv: dict[str, Any], scratch: Path) -> tuple[bool, list[str], str]:
    report = inv.get("report") or {}
    payload = str(report.get("payload") or "") if isinstance(report, dict) else ""
    if inv.get("returncode") != 0:
        return False, [], payload
    if not isinstance(report, dict) or not (report.get("ok") or report.get("ok")):
        return False, [], payload
    if payload != PAYLOAD_TOKEN or payload == DECOY_TOKEN:
        return False, [], payload
    hits = repo_hits(_sys_path_of(report), scratch)
    return (len(hits) == 0), hits, payload


def run_installed(pkg_src: Path, work: Path) -> dict[str, Any]:
    dist = work / "dist"
    venv = work / "venv"
    scratch = prepare_scratch(work)
    wheel = build_wheel(pkg_src, dist)
    make_venv(venv)
    pip_log = pip_install(venv, wheel)
    console = invoke_console(venv, scratch)
    python_m = invoke_python_m(venv_python(venv), scratch)
    console_ok, console_hits, console_payload = _route_ok(console, scratch)
    pym_ok, pym_hits, pym_payload = _route_ok(python_m, scratch)
    script = venv_script(venv)
    script_ok = script.is_file() and outside_repo(script)
    venv_ok = outside_repo(venv)
    result = {
        "wheel_path": str(wheel.resolve()),
        "wheel_name": wheel.name,
        "venv_path": str(venv.resolve()),
        "resolved_script_path": str(script.resolve()) if script.exists() else "",
        "script_exists": script.is_file(),
        "script_outside_repo": script_ok,
        "venv_outside_repo": venv_ok,
        "pip_install_output": pip_log[-8000:],
        "scratch_cwd": str(scratch.resolve()),
        "decoy_payload_path": str((scratch / "payload.txt").resolve()),
        "console": console,
        "python_m": python_m,
        "console_ok": console_ok,
        "python_m_ok": pym_ok,
        "console_repo_hits": console_hits,
        "python_m_repo_hits": pym_hits,
        "console_payload": console_payload,
        "python_m_payload": pym_payload,
        "repo_on_sys_path": bool(console_hits or pym_hits),
        "good": console_ok and pym_ok and script_ok and venv_ok,
    }
    result.update(
        {
            "python_m": python_m,
            "python_m_ok": pym_ok,
            "python_m_payload": pym_payload,
            "python_m_repo_hits": pym_hits,
            "venv_path": result["venv_path"],
            "wheel_path": result["wheel_path"],
            "scratch_cwd": result["scratch_cwd"],
            "decoy_payload_path": result["decoy_payload_path"],
            "script_outside_repo": script_ok,
            "venv_outside_repo": venv_ok,
            "pip_install_output": result["pip_install_output"],
        }
    )
    return result


def copy_pkg(dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(PKG, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return dest


def mutant_missing_script(dest: Path) -> Path:
    copy_pkg(dest)
    pyproject = (dest / "pyproject.toml").read_text(encoding="utf-8")
    pyproject = pyproject.replace(
        '[project.scripts]\ncnf0028-fix = "cnf0028_fix.cli:main"\n',
        "",
    )
    if "cnf0028-fix =" in pyproject:
        raise RuntimeError("failed-to-strip-console-script")
    (dest / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    return dest


def mutant_missing_dep(dest: Path) -> Path:
    copy_pkg(dest)
    cli = dest / "src" / "cnf0028_fix" / "cli.py"
    text = cli.read_text(encoding="utf-8")
    needle = "from cnf0028_fix import PAYLOAD_TOKEN, packaged_payload\n"
    if needle not in text:
        raise RuntimeError("mutant-edit-missed-cli")
    text = text.replace(
        needle,
        needle + "import jsonschema  # undeclared runtime dependency (mutant)\n",
        1,
    )
    cli.write_text(text, encoding="utf-8")
    return dest


def in_tree_host(pkg_src: Path, scratch: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", MODULE_NAME],
        cwd=str(scratch),
        env={**child_env(), "PYTHONPATH": str((pkg_src / "src").resolve())},
        text=True,
        capture_output=True,
        timeout=30,
    )
    return {
        "command": [sys.executable, "-m", MODULE_NAME],
        "cwd": str(scratch),
        "pythonpath": str((pkg_src / "src").resolve()),
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-4000:],
        "stderr": (proc.stderr or "")[-2000:],
        "report": parse_report(proc.stdout or ""),
        "note": "in-tree host python + PYTHONPATH=src; this is the Phase-0 broken detector",
    }


def run_good(work: Path | None = None) -> dict[str, Any]:
    owns = work is None
    tmp: tempfile.TemporaryDirectory[str] | None = None
    if work is None:
        tmp = tempfile.TemporaryDirectory(prefix="cnf0028-good-")
        work = Path(tmp.name)
    try:
        return run_installed(PKG, work)
    finally:
        if owns and tmp is not None:
            tmp.cleanup()


def run_mutants(work: Path | None = None) -> dict[str, Any]:
    owns = work is None
    tmp: tempfile.TemporaryDirectory[str] | None = None
    if work is None:
        tmp = tempfile.TemporaryDirectory(prefix="cnf0028-mut-")
        work = Path(tmp.name)
    try:
        missing_script_src = mutant_missing_script(work / "mut-script")
        missing_dep_src = mutant_missing_dep(work / "mut-dep")
        script_run = run_installed(missing_script_src, work / "work-script")
        dep_run = run_installed(missing_dep_src, work / "work-dep")
        in_tree = in_tree_host(missing_dep_src, prepare_scratch(work / "in-tree-cwd"))
        in_tree_ok = in_tree.get("returncode") == 0 and bool(
            (in_tree.get("report") or {}).get("ok")
            or (in_tree.get("report") or {}).get("ok")
        )
        missing_script = {
            "console_script_missing": not script_run["script_exists"],
            "python_m_ok": script_run["python_m_ok"],
            "console_returncode": script_run["console"]["returncode"],
            "blind_spot_demonstrated": (not script_run["script_exists"])
            and script_run["python_m_ok"],
            "detail": {
                "script_exists": script_run["script_exists"],
                "python_m_returncode": script_run["python_m"]["returncode"],
                "console_stderr": script_run["console"]["stderr"][-500:],
            },
        }
        missing_dep = {
            "undeclared_import": "jsonschema",
            "in_tree_host_python_m_ok": in_tree_ok,
            "clean_venv_console_ok": dep_run["console_ok"],
            "clean_venv_python_m_ok": dep_run["python_m_ok"],
            "surfaced_in_clean_venv": (not dep_run["console_ok"])
            and (not dep_run["python_m_ok"])
            and in_tree_ok,
            "clean_venv_stderr": (
                (dep_run["console"]["stderr"] or "")
                + "\n"
                + (dep_run["python_m"]["stderr"] or "")
            )[-1500:],
            "in_tree_returncode": in_tree.get("returncode"),
        }
        return {
            "missing_script": missing_script,
            "missing_runtime_dependency": missing_dep,
            "missing_script": missing_script,
            "missing_runtime_dependency": missing_dep,
        }
    finally:
        if owns and tmp is not None:
            tmp.cleanup()


run_good = run_good
run_mutants = run_mutants
