"""Run extracted documented commands against a prefix-installed published wheel."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from extract import HERE, REPO, extract_docs, extract_file
from install import (
    build_wheel,
    clean_profile,
    install_wheel,
    isolated_python_cmd,
    repo_on_path,
    with_workspace,
)

EXPECTED_FAILURES_PATH = HERE / "expected_failures.json"
GOOD_FIXTURE = HERE / "fixtures" / "detector-good.md"
BAD_FIXTURE = HERE / "fixtures" / "detector-bad.md"


def load_expected_failures() -> dict[str, str]:
    if not EXPECTED_FAILURES_PATH.is_file():
        return {}
    raw = json.loads(EXPECTED_FAILURES_PATH.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        out: dict[str, str] = {}
        for item in raw:
            if isinstance(item, dict) and item.get("command") and item.get("reason"):
                out[str(item["command"]).strip()] = str(item["reason"])
        return out
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    return {}


def _run_command(command: str, bindir: Path, profile: Path, timeout: int = 30) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTHONPATH", None)
    env["AST_EXAMPLES_PROFILE"] = str(profile)
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    proc = subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", command],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(profile),
        timeout=timeout,
    )
    return {
        "command": command,
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "")[-4000:],
        "stderr": (proc.stderr or "")[-4000:],
    }


def _explain(command: str, exit_code: int, expected: dict[str, str]) -> dict[str, Any]:
    reason = expected.get(command.strip())
    if exit_code == 0:
        return {
            "ok": True,
            "expected_failure": False,
            "unexplained_nonzero": False,
            "reason": None,
        }
    if reason:
        return {
            "ok": True,
            "expected_failure": True,
            "unexplained_nonzero": False,
            "reason": reason,
        }
    return {
        "ok": False,
        "expected_failure": False,
        "unexplained_nonzero": True,
        "reason": None,
    }


def run_commands(
    commands: list[dict[str, Any]],
    bindir: Path,
    profile: Path,
    expected: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    expected = expected if expected is not None else load_expected_failures()
    rows: list[dict[str, Any]] = []
    for spec in commands:
        ran = _run_command(spec["command"], bindir, profile)
        explained = _explain(ran["command"], ran["exit_code"], expected)
        rows.append({**spec, **ran, **explained})
    return rows


def publish_and_install(work: Path) -> dict[str, Any]:
    wheel = build_wheel(work)
    paths = install_wheel(wheel, work / "prefix")
    profile = clean_profile(work)
    loc = subprocess.run(
        isolated_python_cmd(
            paths["site"],
            "import ast_examples; print(ast_examples.__file__); print(ast_examples.ORIGIN)",
        ),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": ""},
    )
    if loc.returncode != 0:
        raise RuntimeError(f"import-installed {loc.stderr}")
    file_line, origin_line = loc.stdout.strip().splitlines()[:2]
    if repo_on_path(file_line):
        raise RuntimeError(f"installed-module-in-repo {file_line}")
    if origin_line.strip() != "wheel":
        raise RuntimeError(f"origin {origin_line!r}")
    return {
        "wheel": str(wheel),
        "wheel_bytes": wheel.stat().st_size,
        "paths": paths,
        "profile": profile,
        "installed_module": file_line,
        "origin": origin_line.strip(),
        "module_in_repo": False,
    }


def run_live_docs() -> dict[str, Any]:
    extracted = extract_docs()
    expected = load_expected_failures()
    with with_workspace() as tmp:
        work = Path(tmp)
        pub = publish_and_install(work)
        rows = run_commands(extracted, pub["paths"]["bindir"], pub["profile"], expected)
        unexplained = [r for r in rows if r["unexplained_nonzero"]]
        return {
            "extracted": extracted,
            "extracted_count": len(extracted),
            "attempted_count": len(rows),
            "exit_codes": [
                {
                    "id": r.get("id"),
                    "source_id": r.get("source_id"),
                    "path": r.get("path"),
                    "command": r["command"],
                    "exit_code": r["exit_code"],
                    "expected_failure": r["expected_failure"],
                    "reason": r["reason"],
                    "ok": r["ok"],
                }
                for r in rows
            ],
            "unexplained_nonzero": [
                {"command": r["command"], "exit_code": r["exit_code"]} for r in unexplained
            ],
            "all_attempted": len(rows) == len(extracted) and len(extracted) > 0,
            "all_explained": not unexplained,
            "pass": bool(extracted)
            and len(rows) == len(extracted)
            and not unexplained,
            "installed_module": pub["installed_module"],
            "origin": pub["origin"],
            "wheel_bytes": pub["wheel_bytes"],
            "readme_count": sum(1 for r in extracted if r["source_id"] == "README"),
            "quickstart_count": sum(1 for r in extracted if r["source_id"] == "quickstart"),
        }


def run_detector() -> dict[str, Any]:
    good_cmds = extract_file(GOOD_FIXTURE, "detector-good")
    bad_cmds = extract_file(BAD_FIXTURE, "detector-bad")
    if len(good_cmds) != 1 or len(bad_cmds) != 1:
        return {
            "pass": False,
            "error": "detector fixtures must each contain exactly one shell command",
            "good_count": len(good_cmds),
            "bad_count": len(bad_cmds),
        }
    with with_workspace() as tmp:
        work = Path(tmp)
        pub = publish_and_install(work)
        good_rows = run_commands(good_cmds, pub["paths"]["bindir"], pub["profile"], {})
        bad_rows = run_commands(bad_cmds, pub["paths"]["bindir"], pub["profile"], {})
        good = good_rows[0]
        bad = bad_rows[0]
        silent_on_good = good["exit_code"] == 0 and good["ok"]
        fired_on_bad = bad["exit_code"] != 0 and bad["unexplained_nonzero"]
        return {
            "pass": silent_on_good and fired_on_bad,
            "silent_on_good": silent_on_good,
            "fired_on_bad": fired_on_bad,
            "good": {
                "command": good["command"],
                "exit_code": good["exit_code"],
                "ok": good["ok"],
            },
            "bad": {
                "command": bad["command"],
                "exit_code": bad["exit_code"],
                "unexplained_nonzero": bad["unexplained_nonzero"],
            },
            "installed_module": pub["installed_module"],
            "origin": pub["origin"],
        }
