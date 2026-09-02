"""Console-script vs ``python -m`` parity in a FRESH venv (TST-0333).

Builds the fixture package's wheel directly (pure-python zip + dist-info, so
no network and no build backend is needed), installs it into a freshly created
venv with ``pip --no-index`` (never editable), and runs the in-package
critical suite through BOTH arms. Equal exit codes with different collected
counts are divergence, not parity. The broken state strips the console-script
entry point from the wheel: that arm must fail while ``python -m`` still
passes.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

PKG = "tst0333_crit"
DIST = "tst0333-crit"
VERSION = "0.0.1"
FIXTURE_REL = "command-center/p2-wave/probes/TST-0333/fixture_pkg"


def _build_wheel(fixture: Path, out_dir: Path, *, strip_entry_point: bool = False) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    wheel = out_dir / f"{PKG}-{VERSION}-py3-none-any.whl"
    src = fixture / "src" / PKG
    distinfo = f"{PKG}-{VERSION}.dist-info"
    names: list[str] = []
    with zipfile.ZipFile(wheel, "w", zipfile.ZIP_DEFLATED) as zf:
        for py in sorted(src.glob("*.py")):
            arc = f"{PKG}/{py.name}"
            zf.writestr(arc, py.read_text(encoding="utf-8"))
            names.append(arc)
        zf.writestr(
            f"{distinfo}/METADATA",
            f"Metadata-Version: 2.1\nName: {DIST}\nVersion: {VERSION}\n",
        )
        names.append(f"{distinfo}/METADATA")
        zf.writestr(
            f"{distinfo}/WHEEL",
            "Wheel-Version: 1.0\nGenerator: testinfra-entry-parity\n"
            "Root-Is-Purelib: true\nTag: py3-none-any\n",
        )
        names.append(f"{distinfo}/WHEEL")
        if not strip_entry_point:
            zf.writestr(
                f"{distinfo}/entry_points.txt",
                f"[console_scripts]\n{DIST} = {PKG}.cli:main\n",
            )
            names.append(f"{distinfo}/entry_points.txt")
        record = "".join(f"{name},,\n" for name in names) + f"{distinfo}/RECORD,,\n"
        zf.writestr(f"{distinfo}/RECORD", record)
    return wheel


def _fresh_venv(venv_dir: Path, wheel: Path) -> dict[str, Any]:
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        check=True, capture_output=True, timeout=120,
    )
    py = venv_dir / ("Scripts" if sys.platform == "win32" else "bin") / "python"
    proc = subprocess.run(
        [str(py), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)],
        capture_output=True, text=True, timeout=120,
    )
    return {
        "python": str(py),
        "bin": str(py.parent),
        "pip_exit": proc.returncode,
        "pip_tail": ((proc.stdout or "") + (proc.stderr or ""))[-400:],
    }


def _run_arm(argv: list[str], cwd: Path) -> dict[str, Any]:
    try:
        proc = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, timeout=90)
        exit_code = proc.returncode
        stdout = proc.stdout or ""
    except FileNotFoundError:
        return {"exit_code": 127, "collected": None, "import_file": None, "cmd": argv}
    except subprocess.TimeoutExpired:
        return {"exit_code": 124, "collected": None, "import_file": None, "cmd": argv}
    collected = None
    import_file = None
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            collected = doc.get("collected")
            import_file = doc.get("import_file")
    return {"exit_code": exit_code, "collected": collected, "import_file": import_file, "cmd": argv}


def _console_path(venv_bin: str) -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    return Path(venv_bin) / f"{DIST}{suffix}"


def evaluate_good_path(repo: Path | str) -> dict[str, Any]:
    repo = Path(repo)
    fixture = repo / FIXTURE_REL
    tmp = Path(tempfile.mkdtemp(prefix="tst0333-good-"))
    try:
        wheel = _build_wheel(fixture, tmp / "dist")
        venv = _fresh_venv(tmp / "venv", wheel)
        if venv["pip_exit"] != 0:
            return {"pass": False, "why": "pip-install-failed", "venv": venv, "tests": []}
        module = _run_arm([venv["python"], "-m", PKG], tmp)
        console = _run_arm([str(_console_path(venv["bin"]))], tmp)
        parity = (
            module["exit_code"] == 0
            and console["exit_code"] == 0
            and module["collected"] == console["collected"]
            and module["collected"] == 3
        )
        import_file = str(module.get("import_file") or "")
        inside_venv = str(tmp / "venv") in import_file
        inside_worktree = str(fixture) in import_file
        not_editable = bool(import_file) and inside_venv and not inside_worktree
        tests = [
            {
                "id": "test_both_invocations_same_commit",
                "module_exit_code": module["exit_code"],
                "console_exit_code": console["exit_code"],
                "module_collected": module["collected"],
                "console_collected": console["collected"],
                "module_cmd": module["cmd"],
                "console_cmd": console["cmd"],
                "pass": parity,
            },
            {
                "id": "test_fresh_venv_not_editable",
                "not_editable": not_editable,
                "import_file": import_file,
                "pass": not_editable,
            },
        ]
        return {
            "pass": parity and not_editable,
            "tests": tests,
            "wheel": wheel.name,
            "venv": venv,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_break_entry_point_console_fails_module_passes(repo: Path | str) -> dict[str, Any]:
    repo = Path(repo)
    fixture = repo / FIXTURE_REL
    tmp = Path(tempfile.mkdtemp(prefix="tst0333-broken-"))
    try:
        good_wheel = _build_wheel(fixture, tmp / "dist-good", strip_entry_point=False)
        good_venv = _fresh_venv(tmp / "venv-good", good_wheel)
        good_console = _run_arm([str(_console_path(good_venv["bin"]))], tmp)

        broken_wheel = _build_wheel(fixture, tmp / "dist-broken", strip_entry_point=True)
        broken_venv = _fresh_venv(tmp / "venv-broken", broken_wheel)
        broken_console = _run_arm([str(_console_path(broken_venv["bin"]))], tmp)
        broken_module = _run_arm([broken_venv["python"], "-m", PKG], tmp)

        silent_on_good = good_console["exit_code"] == 0 and good_console["collected"] == 3
        fires_on_broken = broken_console["exit_code"] != 0
        module_still_green = broken_module["exit_code"] == 0 and broken_module["collected"] == 3
        return {
            "pass": silent_on_good and fires_on_broken and module_still_green,
            "verbatim": {
                "good": {
                    "console_exit_code": good_console["exit_code"],
                    "console_collected": good_console["collected"],
                    "console_cmd": good_console["cmd"],
                },
                "broken": {
                    "console_exit_code": broken_console["exit_code"],
                    "module_exit_code": broken_module["exit_code"],
                    "module_collected": broken_module["collected"],
                    "console_cmd": broken_console["cmd"],
                    "module_cmd": broken_module["cmd"],
                },
            },
            "silent_on_good_state": silent_on_good,
            "fired_on_bad_state": fires_on_broken,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


__all__ = ["evaluate_good_path", "test_break_entry_point_console_fails_module_passes"]
