"""Environment-record gate: missing/empty/invalid fields are inadmissible."""
from __future__ import annotations

import json
import locale as _locale
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

MANDATORY_FIELDS: tuple[str, ...] = (
    "os_build",
    "shell",
    "interpreter_version",
    "package_versions",
    "git_core_autocrlf",
    "locale",
    "timezone",
    "concurrency",
    "commit_sha",
)

_SHA = re.compile(r"^[0-9a-f]{7,40}$", re.I)
_GIT_EOL = frozenset({"true", "false", "input", "lf", "crlf"})


class InadmissibleResult(Exception):
    def __init__(self, verdict: dict[str, Any]) -> None:
        self.verdict = verdict
        super().__init__(verdict.get("reason") or "inadmissible")


def make_complete_record() -> dict[str, Any]:
    return {
        "os_build": {"system": "Linux", "release": "6.8.0", "machine": "x86_64"},
        "shell": {"name": "bash", "path": "/usr/bin/bash", "version": "5.2.21"},
        "interpreter_version": "3.12.3",
        "package_versions": {"jsonschema": "4.23.0"},
        "git_core_autocrlf": "false",
        "locale": "C.UTF-8",
        "timezone": "UTC",
        "concurrency": 4,
        "commit_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    }


def extract_environment(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    env = row.get("environment_record")
    return env if isinstance(env, dict) else None


def _field_ok(name: str, value: Any) -> bool:
    if value is None:
        return False
    if name == "os_build":
        return isinstance(value, dict) and bool(value.get("system") or value.get("release"))
    if name == "shell":
        return isinstance(value, dict) and bool(str(value.get("name") or "").strip())
    if name == "interpreter_version":
        return isinstance(value, str) and bool(value.strip())
    if name == "package_versions":
        return isinstance(value, dict) and bool(value)
    if name == "git_core_autocrlf":
        return str(value).strip().lower() in _GIT_EOL
    if name in {"locale", "timezone"}:
        return isinstance(value, str) and bool(value.strip())
    if name == "concurrency":
        return isinstance(value, int) and value > 0
    if name == "commit_sha":
        return isinstance(value, str) and bool(_SHA.match(value.strip()))
    return value not in ("", None, {}, [])


def judge_environment(env: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(env, dict):
        return {
            "admitted": False,
            "missing_fields": list(MANDATORY_FIELDS),
            "invalid_fields": [],
            "reason": "no-environment-record",
        }
    missing = []
    invalid = []
    for field in MANDATORY_FIELDS:
        if field not in env or not _field_ok(field, env.get(field)):
            missing.append(field)
            if field in env:
                invalid.append(field)
    return {
        "admitted": not missing,
        "missing_fields": missing,
        "invalid_fields": invalid,
        "reason": "ok" if not missing else "missing-or-invalid",
    }


def judge_result(row: dict[str, Any]) -> dict[str, Any]:
    env = extract_environment(row)
    return judge_environment(env)


def append_result(dest: Path, row: dict[str, Any]) -> Path:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    ledger = dest / "runs.jsonl"
    verdict = judge_result(row)
    if not verdict["admitted"]:
        raise InadmissibleResult(verdict)
    with ledger.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    return ledger


def capture_commit_sha(root: Path | None = None) -> str | None:
    """HEAD of the tree under measurement, read-only; ``None`` off a git worktree."""
    for var in ("BENCH_COMMIT_SHA", "GITHUB_SHA", "GIT_COMMIT"):
        val = os.environ.get(var, "").strip()
        if val and _SHA.match(val):
            return val
    cwd = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    sha = (out.stdout or "").strip()
    return sha if out.returncode == 0 and _SHA.match(sha) else None


def _parent_shell() -> dict[str, Any]:
    """Name/path/version of the process that launched this interpreter."""
    ppid = os.getppid()
    name = ""
    path = ""
    try:
        name = Path(f"/proc/{ppid}/comm").read_text(encoding="utf-8").strip()
    except OSError:
        pass
    try:
        path = os.readlink(f"/proc/{ppid}/exe")
    except OSError:
        pass
    if not name:
        name = Path(os.environ.get("SHELL") or "unknown-shell").name
    if not path:
        path = os.environ.get("SHELL") or name
    version = ""
    # The parent may be a renamed copy (git-bash, pwsh7): ask the binary at
    # /proc/<ppid>/exe (or the recorded path) for its own version string.
    probe = f"/proc/{ppid}/exe" if os.path.exists(f"/proc/{ppid}/exe") else path
    try:
        out = subprocess.run(
            [probe, "--version"], capture_output=True, text=True, timeout=5, check=False
        )
        version = ((out.stdout or out.stderr or "").strip().splitlines() or [""])[0]
    except (OSError, subprocess.TimeoutExpired, ValueError):
        version = ""
    return {"name": name, "path": path, "version": version or "unknown"}


def _git_core_autocrlf() -> str:
    try:
        out = subprocess.run(
            ["git", "config", "--get", "core.autocrlf"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        val = (out.stdout or "").strip().lower()
    except (OSError, subprocess.TimeoutExpired):
        val = ""
    return val if val in _GIT_EOL else "false"


def capture_environment() -> dict[str, Any]:
    """Measure the live environment; fields that cannot be measured are absent, never faked."""
    uname = platform.uname()
    record: dict[str, Any] = {
        "os_build": {"system": uname.system, "release": uname.release, "machine": uname.machine},
        "shell": _parent_shell(),
        "interpreter_version": platform.python_version(),
        "package_versions": {"python": platform.python_version(), "json": "stdlib"},
        "git_core_autocrlf": _git_core_autocrlf(),
        "locale": os.environ.get("LC_ALL") or os.environ.get("LANG") or (_locale.getlocale()[0] or "C"),
        "timezone": os.environ.get("TZ") or time.tzname[0] or "UTC",
        "concurrency": os.cpu_count() or 1,
    }
    sha = capture_commit_sha()
    if sha:
        record["commit_sha"] = sha
    return record


def _iter_rows_from_path(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if path.is_dir():
        for child in sorted(path.iterdir()):
            if child.suffix in (".jsonl", ".json") and child.is_file():
                rows.extend(_iter_rows_from_path(child))
        return rows
    if not path.is_file():
        return rows
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".jsonl":
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                obj = {"_unparseable": True, "_source": str(path)}
            rows.append(obj if isinstance(obj, dict) else {"_non_object": True})
        return rows
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return [{"_unparseable": True, "_source": str(path)}]
    if isinstance(doc, list):
        rows.extend(d if isinstance(d, dict) else {"_non_object": True} for d in doc)
    elif isinstance(doc, dict) and isinstance(doc.get("rows"), list):
        rows.extend(d if isinstance(d, dict) else {"_non_object": True} for d in doc["rows"])
    else:
        rows.append(doc if isinstance(doc, dict) else {"_non_object": True})
    return rows


def census_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Count admitted vs inadmissible rows. Debt is reported, never backfilled."""
    admitted = 0
    inadmissible_ids: list[str] = []
    reasons: dict[str, int] = {}
    for idx, row in enumerate(rows):
        verdict = judge_result(row if isinstance(row, dict) else {})
        if verdict["admitted"]:
            admitted += 1
            continue
        rid = str((row or {}).get("id") if isinstance(row, dict) else None) or f"row-{idx}"
        inadmissible_ids.append(rid)
        key = verdict["reason"] + (
            ":" + ",".join(verdict["missing_fields"]) if verdict["reason"] != "no-environment-record" else ""
        )
        reasons[key] = reasons.get(key, 0) + 1
    n = len(rows)
    inadmissible = n - admitted
    return {
        "n": n,
        "admitted": admitted,
        "inadmissible": inadmissible,
        "fraction_inadmissible": (inadmissible / n) if n else 0.0,
        "inadmissible_ids": inadmissible_ids,
        "reasons": reasons,
        "debt_not_backfilled": True,
    }


def census_paths(paths: list[Path | str]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    files: list[str] = []
    absent: list[str] = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            absent.append(str(path))
            continue
        found = _iter_rows_from_path(path)
        rows.extend(found)
        files.append(str(path))
    out = census_rows(rows)
    out["paths"] = files
    out["paths_absent"] = absent
    return out


def overlay_shell(
    record: dict[str, Any],
    name_or_shell: str | dict[str, Any],
    path: str | None = None,
    version: str | None = None,
) -> dict[str, Any]:
    """Same measurement, different shell: only the ``shell`` field changes."""
    out = deepcopy(record)
    if isinstance(name_or_shell, dict):
        out["shell"] = dict(name_or_shell)
    else:
        out["shell"] = {"name": str(name_or_shell), "path": path or "", "version": version or ""}
    return out


def compare_cross_shell(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    va, vb = judge_environment(a), judge_environment(b)
    others = [f for f in MANDATORY_FIELDS if f != "shell"]
    differing = [f for f in others if a.get(f) != b.get(f)]
    shell_differs = (a.get("shell") or {}).get("name") != (b.get("shell") or {}).get("name")
    both_admitted = bool(va["admitted"] and vb["admitted"])
    agree_elsewhere = not differing
    return {
        "shell_differs": shell_differs,
        "shell_a": a.get("shell"),
        "shell_b": b.get("shell"),
        "agree_elsewhere": agree_elsewhere,
        "differing_fields": differing,
        "both_admitted": both_admitted,
        "comparable": both_admitted and agree_elsewhere,
        "verdict_a": va,
        "verdict_b": vb,
    }


def _capture_under_shell(shell_path: Path) -> dict[str, Any]:
    code = (
        "import json,sys; sys.path.insert(0, %r); "
        "from bench.environment_record import capture_environment; "
        "print(json.dumps(capture_environment()))" % str(Path(__file__).resolve().parents[1])
    )
    # A trailing exit stops bash from exec-optimising the single command away;
    # the renamed shell must remain the parent the capture reads.
    cmd = f"{sys.executable} -B -c {json.dumps(code)}; exit $?"
    out = subprocess.run(
        [str(shell_path), "-c", cmd],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if out.returncode != 0:
        raise RuntimeError(f"capture under {shell_path.name} failed: {out.stderr.strip()[-500:]}")
    return json.loads(out.stdout.strip().splitlines()[-1])


def live_named_shell_pair() -> dict[str, Any]:
    """Run the same capture under two differently named parent shells.

    On Windows these are Git Bash and pwsh7; on this host the analogue copies
    ``/bin/bash`` to ``git-bash`` and ``pwsh7`` so the parent process name the
    capture reads really differs while everything else is identical.
    """
    bash = shutil.which("bash") or "/bin/bash"
    with tempfile.TemporaryDirectory(prefix="tst0352-shells-") as td:
        pair: dict[str, dict[str, Any]] = {}
        for name in ("git-bash", "pwsh7"):
            dst = Path(td) / name
            shutil.copy2(bash, dst)
            dst.chmod(0o755)
            pair[name] = _capture_under_shell(dst)
    git_bash, pwsh7 = pair["git-bash"], pair["pwsh7"]
    return {
        "git_bash": git_bash,
        "pwsh7": pwsh7,
        "comparison": compare_cross_shell(git_bash, pwsh7),
    }
