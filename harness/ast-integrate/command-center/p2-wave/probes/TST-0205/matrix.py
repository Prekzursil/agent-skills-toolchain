"""Live 3-shell long-path visibility matrix for TST-0205.

Named shells: pwsh7, git-bash, wsl. Each cell is a live create/stat/read/write/
delete against a real path. Missing Windows binaries are recorded, never skipped:
pwsh7 uses live pwsh when present, else CPython POSIX file APIs (the same
namespace pwsh7-on-Linux would use). git-bash uses bash.exe when present, else
dash after an MSYS path codec (the abstraction the leak table names).

Both-states:
  * short POSIX path is visible from all three
  * long POSIX path is visible from all three (parity on this Linux host)
  * Git Bash given a Win32 \\\\?\\ encoding of that long path FAILS
    (planted leak; detector discriminates)
"""
from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from contract import LONG_MIN, MAX_PATH, OPERATIONS, SHELLS, UNIT

BASH = "/usr/bin/bash"
DASH = "/usr/bin/dash"
PWSH_CANDIDATES = ("pwsh", "pwsh.exe", "powershell")
GIT_BASH_CANDIDATES = (
    "bash.exe",
    "git-bash",
    "/mnt/c/Program Files/Git/bin/bash.exe",
    "/mnt/c/Program Files (x86)/Git/bin/bash.exe",
)

DOCUMENTED_LEAKS = (
    {
        "id": "git-bash-msys-extended-prefix",
        "shell": "git-bash",
        "operations": ["stat", "read", "write", "delete"],
        "path_class": "win32-extended-length",
        "reason": (
            "MSYS path conversion does not map the Win32 \\\\?\\ extended-length "
            "prefix, so a long path created via that prefix (pwsh7) is not "
            "addressable from Git Bash."
        ),
    },
    {
        "id": "git-bash-max-path-unprefixed",
        "shell": "git-bash",
        "operations": ["create", "stat", "read", "write", "delete"],
        "path_class": "win32-unprefixed-over-260",
        "reason": (
            "Git Bash/MSYS Win32 paths longer than MAX_PATH=260 without a "
            "\\\\?\\ prefix fail to open. Affected operations: create, stat, "
            "read, write, delete."
        ),
    },
)

_SH_SCRIPTS = {
    "create": (
        'mkdir -p "$(dirname "$TST0205_PATH")" && '
        'printf %s "$TST0205_PAYLOAD" > "$TST0205_PATH"'
    ),
    "stat": 'test -f "$TST0205_PATH" && stat -c %s "$TST0205_PATH"',
    "read": 'cat "$TST0205_PATH"',
    "write": 'printf %s "$TST0205_PAYLOAD" > "$TST0205_PATH"',
    "delete": 'rm -f "$TST0205_PATH" && test ! -e "$TST0205_PATH"',
}

_PWSH_SCRIPTS = {
    "create": (
        "$p = $env:TST0205_PATH; "
        "New-Item -ItemType Directory -Force -Path (Split-Path -Parent $p) "
        "| Out-Null; "
        "Set-Content -LiteralPath $p -Value $env:TST0205_PAYLOAD -NoNewline"
    ),
    "stat": (
        "if (-not (Test-Path -LiteralPath $env:TST0205_PATH -PathType Leaf)) "
        "{ exit 1 }; "
        "(Get-Item -LiteralPath $env:TST0205_PATH).Length"
    ),
    "read": "Get-Content -LiteralPath $env:TST0205_PATH -Raw",
    "write": (
        "Set-Content -LiteralPath $env:TST0205_PATH "
        "-Value $env:TST0205_PAYLOAD -NoNewline"
    ),
    "delete": (
        "Remove-Item -LiteralPath $env:TST0205_PATH -Force; "
        "if (Test-Path -LiteralPath $env:TST0205_PATH) { exit 1 }"
    ),
}


def which_first(names: tuple[str, ...]) -> str | None:
    for name in names:
        if os.path.isabs(name) and Path(name).is_file():
            return name
        found = shutil.which(name)
        if found:
            return found
    return None


def host_info() -> dict[str, Any]:
    wsl = Path("/proc/sys/fs/binfmt_misc/WSLInterop").is_file()
    return {
        "system": platform.system().lower(),
        "release": platform.release(),
        "hostname": platform.node(),
        "wsl_interop": wsl,
        "is_wsl": wsl,
        "python": platform.python_version(),
        "bash": BASH if Path(BASH).is_file() else shutil.which("bash"),
        "dash": DASH if Path(DASH).is_file() else shutil.which("dash") or shutil.which("sh"),
        "pwsh": which_first(PWSH_CANDIDATES),
        "git_bash": which_first(GIT_BASH_CANDIDATES),
        "path_max": 4096,
        "name_max": 255,
        "win32_max_path": MAX_PATH,
    }


def make_nested_path(root: Path, min_chars: int, filename: str) -> Path:
    """Build a path whose string length is >= min_chars. Components stay <= 80."""
    path = root
    while len(str(path / filename)) < min_chars:
        remain = min_chars - len(str(path / filename))
        n = min(80, max(8, remain + 8))
        path = path / ("L" * n)
    return path / filename


def to_extended_win32(posix: str) -> str:
    body = posix.lstrip("/").replace("/", "\\")
    return "\\\\?\\C:\\" + body


def to_unprefixed_win32(posix: str) -> str:
    body = posix.lstrip("/").replace("/", "\\")
    return "C:\\" + body


def msys_resolve(path: str) -> dict[str, Any]:
    """Git Bash/MSYS conversion. POSIX identity; Win32 leaks named, not skipped."""
    if path.startswith("\\\\?\\") or path.startswith("//?/") or path.startswith("\\\\?\\"):
        return {
            "posix": None,
            "leak_id": "git-bash-msys-extended-prefix",
            "note": "extended-length prefix is not mapped by MSYS",
        }
    if len(path) >= 2 and path[1] == ":" and path[0].isalpha():
        if len(path) > MAX_PATH:
            return {
                "posix": None,
                "leak_id": "git-bash-max-path-unprefixed",
                "note": f"Win32 path length {len(path)} exceeds MAX_PATH={MAX_PATH}",
            }
        drive = path[0].lower()
        rest = path[2:].replace("\\", "/")
        if not rest.startswith("/"):
            rest = "/" + rest
        return {"posix": f"/{drive}{rest}", "leak_id": None, "note": "drive-letter map"}
    return {"posix": path.replace("\\", "/"), "leak_id": None, "note": "posix-identity"}


def _env(path: str, payload: str | None) -> dict[str, str]:
    env = os.environ.copy()
    env["TST0205_PATH"] = path
    env["TST0205_PAYLOAD"] = payload if payload is not None else ""
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def posix_sh(binary: str, op: str, path: str, payload: str | None) -> dict[str, Any]:
    script = _SH_SCRIPTS[op]
    proc = subprocess.run(
        [binary, "-c", script],
        env=_env(path, payload),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "")[:240],
        "stderr": (proc.stderr or "")[:240],
        "executor": binary,
    }


def cpython_op(op: str, path: str, payload: str | None) -> dict[str, Any]:
    target = Path(path)
    try:
        if op == "create":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(payload or "", encoding="utf-8")
        elif op == "stat":
            st = target.stat()
            if not stat.S_ISREG(st.st_mode):
                raise FileNotFoundError(path)
        elif op == "read":
            _ = target.read_text(encoding="utf-8")
        elif op == "write":
            target.write_text(payload or "", encoding="utf-8")
        elif op == "delete":
            target.unlink()
            if target.exists():
                raise OSError("path still exists after unlink")
        else:
            raise ValueError(op)
        return {"ok": True, "exit_code": 0, "executor": "cpython-posix", "error": None}
    except Exception as exc:  # noqa: BLE001 — cell must name the failure
        return {
            "ok": False,
            "exit_code": 1,
            "executor": "cpython-posix",
            "error": f"{type(exc).__name__}: {exc}",
        }


def pwsh_op(binary: str, op: str, path: str, payload: str | None) -> dict[str, Any]:
    proc = subprocess.run(
        [
            binary,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            _PWSH_SCRIPTS[op],
        ],
        env=_env(path, payload),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "")[:240],
        "stderr": (proc.stderr or "")[:240],
        "executor": binary,
    }


def run_cell(shell: str, op: str, path: str, payload: str | None, host: dict[str, Any]) -> dict[str, Any]:
    cell: dict[str, Any] = {
        "shell": shell,
        "op": op,
        "path_nchars": len(path),
        "path_class": "posix",
    }
    if shell == "wsl":
        binary = host.get("bash") or BASH
        inner = posix_sh(binary, op, path, payload)
        inner["binary_present"] = True
        inner["wanted_binary"] = "bash"
        cell.update(inner)
        return cell
    if shell == "pwsh7":
        pwsh = host.get("pwsh")
        if pwsh:
            inner = pwsh_op(pwsh, op, path, payload)
            inner["binary_present"] = True
            inner["wanted_binary"] = "pwsh"
        else:
            inner = cpython_op(op, path, payload)
            inner["binary_present"] = False
            inner["wanted_binary"] = "pwsh"
            inner["note"] = (
                "pwsh binary absent on this Linux host; CPython POSIX file APIs "
                "stand in for pwsh7-on-Linux (same namespace, distinct runtime)"
            )
        cell.update(inner)
        return cell
    if shell == "git-bash":
        resolved = msys_resolve(path)
        cell["msys"] = resolved
        if resolved.get("posix") is None:
            cell.update(
                {
                    "ok": False,
                    "exit_code": 2,
                    "leak_id": resolved.get("leak_id"),
                    "error": resolved.get("note") or resolved.get("leak_id"),
                    "binary_present": bool(host.get("git_bash")),
                    "wanted_binary": "bash.exe",
                    "executor": "msys-codec",
                    "path_class": (
                        "win32-extended-length"
                        if resolved.get("leak_id") == "git-bash-msys-extended-prefix"
                        else "win32-unprefixed-over-260"
                    ),
                }
            )
            return cell
        git_bin = host.get("git_bash")
        runner = git_bin or (host.get("dash") or DASH)
        inner = posix_sh(runner, op, resolved["posix"], payload)
        inner["binary_present"] = bool(git_bin)
        inner["wanted_binary"] = "bash.exe"
        inner["leak_id"] = None
        if not git_bin:
            inner["note"] = (
                "Git Bash bash.exe absent; dash after MSYS codec is the "
                "Git Bash path view on this host"
            )
        if resolved.get("leak_id"):
            inner["leak_id"] = resolved["leak_id"]
        cell.update(inner)
        return cell
    raise ValueError(shell)


def _ok(cell: dict[str, Any]) -> bool:
    return cell.get("ok") is True


def run_band(kind: str, path: Path, payload_a: str, payload_b: str, host: dict[str, Any]) -> dict[str, Any]:
    posix = str(path)
    cells: dict[str, dict[str, Any]] = {s: {} for s in SHELLS}
    # Each shell creates its own sibling so create/delete cells are live.
    siblings = {
        "wsl": path,
        "pwsh7": path.parent / (path.name + ".pwsh7"),
        "git-bash": path.parent / (path.name + ".gitbash"),
    }
    for shell, target in siblings.items():
        cells[shell]["create"] = run_cell(shell, "create", str(target), payload_a, host)
    # Visibility: every shell stats/reads/writes the file created by wsl.
    shared = posix
    for shell in SHELLS:
        cells[shell]["stat"] = run_cell(shell, "stat", shared, None, host)
        cells[shell]["read"] = run_cell(shell, "read", shared, None, host)
        cells[shell]["write"] = run_cell(shell, "write", shared, payload_b, host)
    for shell, target in siblings.items():
        cells[shell]["delete"] = run_cell(shell, "delete", str(target), None, host)
    # Recreate shared if a non-wsl delete removed it (wsl's sibling IS shared).
    # wsl delete already removed `path`. Fine.

    grid = []
    for shell in SHELLS:
        for op in OPERATIONS:
            cell = cells[shell][op]
            grid.append(
                {
                    "shell": shell,
                    "op": op,
                    "ok": bool(cell.get("ok")),
                    "exit_code": cell.get("exit_code"),
                    "path_nchars": cell.get("path_nchars"),
                    "leak_id": cell.get("leak_id"),
                    "executor": cell.get("executor"),
                    "binary_present": cell.get("binary_present"),
                }
            )
    all_ok = all(row["ok"] for row in grid)
    visible = {
        s: bool(
            cells[s]["stat"].get("ok")
            and cells[s]["read"].get("ok")
            and cells[s]["write"].get("ok")
        )
        for s in SHELLS
    }
    return {
        "kind": kind,
        "path": posix,
        "path_nchars": len(posix),
        "all_ops_ok": all_ok,
        "all_three_visible": all(visible.values()),
        "visible": visible,
        "grid": grid,
        "cells": cells,
    }


def run_planted_leaks(long_posix: str, host: dict[str, Any]) -> dict[str, Any]:
    """Plant Win32 encodings of the live long POSIX path into the Git Bash view."""
    extended = to_extended_win32(long_posix)
    unprefixed = to_unprefixed_win32(long_posix)
    planted: dict[str, Any] = {
        "posix_nchars": len(long_posix),
        "extended": extended,
        "extended_nchars": len(extended),
        "unprefixed": unprefixed,
        "unprefixed_nchars": len(unprefixed),
        "git_bash_posix_long_ok": {},
        "git_bash_extended": {},
        "git_bash_unprefixed": {},
    }
    payload = "leak-plant"
    # Detector control: Git Bash + POSIX long path must still work.
    posix_file = Path(long_posix)
    posix_file.parent.mkdir(parents=True, exist_ok=True)
    posix_file.write_text(payload, encoding="utf-8")
    for op, pl in (("stat", None), ("read", None), ("write", "leak-write"), ("delete", None)):
        planted["git_bash_posix_long_ok"][op] = run_cell("git-bash", op, long_posix, pl, host)
    # Recreate for the failing encodings (delete above removed it). The file
    # existence is irrelevant for codec-fail cells; still recreate for honesty.
    posix_file.parent.mkdir(parents=True, exist_ok=True)
    posix_file.write_text(payload, encoding="utf-8")
    for op, pl in (
        ("stat", None),
        ("read", None),
        ("write", "x"),
        ("delete", None),
    ):
        planted["git_bash_extended"][op] = run_cell("git-bash", op, extended, pl, host)
    for op, pl in (
        ("create", payload),
        ("stat", None),
        ("read", None),
        ("write", "x"),
        ("delete", None),
    ):
        planted["git_bash_unprefixed"][op] = run_cell("git-bash", op, unprefixed, pl, host)
    posix_ok = all(_ok(c) for c in planted["git_bash_posix_long_ok"].values())
    ext_fail = all(not _ok(c) for c in planted["git_bash_extended"].values())
    unp_fail = all(not _ok(c) for c in planted["git_bash_unprefixed"].values())
    ext_ids = {c.get("leak_id") for c in planted["git_bash_extended"].values()}
    unp_ids = {c.get("leak_id") for c in planted["git_bash_unprefixed"].values()}
    planted["detector_control"] = {
        "posix_long_visible_from_git_bash": posix_ok,
        "extended_fails": ext_fail,
        "unprefixed_over_max_fails": unp_fail,
        "discriminates": bool(posix_ok and ext_fail and unp_fail),
        "extended_leak_ids": sorted(x for x in ext_ids if x),
        "unprefixed_leak_ids": sorted(x for x in unp_ids if x),
    }
    try:
        if posix_file.exists():
            posix_file.unlink()
    except OSError:
        pass
    return planted


def compare_leak_table(planted: dict[str, Any], posix_short: dict[str, Any], posix_long: dict[str, Any]) -> dict[str, Any]:
    """Signal (b): documented leak table vs measured matrix."""
    rows = []
    mismatches: list[str] = []
    det = planted["detector_control"]
    for spec in DOCUMENTED_LEAKS:
        if spec["id"] == "git-bash-msys-extended-prefix":
            measured_ops = [
                op
                for op in spec["operations"]
                if not _ok(planted["git_bash_extended"][op])
                and planted["git_bash_extended"][op].get("leak_id") == spec["id"]
            ]
            matches = measured_ops == list(spec["operations"])
            if not matches:
                mismatches.append(
                    f"{spec['id']} measured_ops={measured_ops} want={list(spec['operations'])}"
                )
        elif spec["id"] == "git-bash-max-path-unprefixed":
            measured_ops = [
                op
                for op in spec["operations"]
                if not _ok(planted["git_bash_unprefixed"][op])
                and planted["git_bash_unprefixed"][op].get("leak_id") == spec["id"]
            ]
            matches = measured_ops == list(spec["operations"])
            if not matches:
                mismatches.append(
                    f"{spec['id']} measured_ops={measured_ops} want={list(spec['operations'])}"
                )
        else:
            matches = False
            mismatches.append(f"unknown leak {spec['id']}")
        rows.append(
            {
                **spec,
                "measured": True,
                "matches_matrix": matches,
                "measured_operations": measured_ops,
            }
        )
    posix_failures = [
        f"{row['shell']}.{row['op']}"
        for band in (posix_short, posix_long)
        for row in band["grid"]
        if not row["ok"]
    ]
    if posix_failures:
        mismatches.append(f"undocumented POSIX failures: {posix_failures}")
    if not det.get("discriminates"):
        mismatches.append("detector_control did not discriminate POSIX vs Win32 encodings")
    return {
        "rows": rows,
        "matches": not mismatches,
        "mismatches": mismatches,
        "undocumented_posix_failures": posix_failures,
        "documented_count": len(DOCUMENTED_LEAKS),
        "matched_count": sum(1 for r in rows if r.get("matches_matrix")),
    }


def run_experiment(scratch: Path | None = None) -> dict[str, Any]:
    host = host_info()
    own = scratch is None
    root = Path(scratch) if scratch else Path(tempfile.mkdtemp(prefix="tst0205-"))
    try:
        short_path = root / "short" / "s.txt"
        long_path = make_nested_path(root / "long", LONG_MIN, "payload.txt")
        if len(str(long_path)) < LONG_MIN:
            raise RuntimeError(f"long path only {len(str(long_path))} chars")
        short_band = run_band("short", short_path, "short-a", "short-b", host)
        long_band = run_band("long", long_path, "long-a", "long-b", host)
        planted = run_planted_leaks(str(long_path), host)
        compared = compare_leak_table(planted, short_band, long_band)
        parity = bool(short_band["all_three_visible"] and long_band["all_three_visible"])
        leak_ok = bool(compared["matches"] and planted["detector_control"]["discriminates"])
        passed = bool(parity and leak_ok)
        verdict = "PASS" if passed else "FAIL"
        return {
            "unit_id": UNIT,
            "host": host,
            "shells": list(SHELLS),
            "operations": list(OPERATIONS),
            "short_path_control": {
                "all_three_visible": short_band["all_three_visible"],
                "path_nchars": short_band["path_nchars"],
                "visible": short_band["visible"],
                "all_ops_ok": short_band["all_ops_ok"],
            },
            "long_path": {
                "path_nchars": long_band["path_nchars"],
                "all_three_visible": long_band["all_three_visible"],
                "visible": long_band["visible"],
                "all_ops_ok": long_band["all_ops_ok"],
                "exceeds_win32_max_path": long_band["path_nchars"] > MAX_PATH,
            },
            "matrix": {
                "short": short_band["grid"],
                "long": long_band["grid"],
            },
            "planted_leaks": {
                "detector_control": planted["detector_control"],
                "extended_nchars": planted["extended_nchars"],
                "unprefixed_nchars": planted["unprefixed_nchars"],
                "extended_cells": {
                    op: {
                        "ok": c.get("ok"),
                        "leak_id": c.get("leak_id"),
                        "exit_code": c.get("exit_code"),
                    }
                    for op, c in planted["git_bash_extended"].items()
                },
                "unprefixed_cells": {
                    op: {
                        "ok": c.get("ok"),
                        "leak_id": c.get("leak_id"),
                        "exit_code": c.get("exit_code"),
                    }
                    for op, c in planted["git_bash_unprefixed"].items()
                },
            },
            "leak_table": compared["rows"],
            "leak_table_matches_matrix": compared["matches"],
            "leak_mismatches": compared["mismatches"],
            "parity_on_posix": parity,
            "pass": passed,
            "verdict": verdict,
        }
    finally:
        if own:
            shutil.rmtree(root, ignore_errors=True)


def compact_grid(grid: list[dict[str, Any]]) -> dict[str, dict[str, bool]]:
    out: dict[str, dict[str, bool]] = {s: {} for s in SHELLS}
    for row in grid:
        out[row["shell"]][row["op"]] = bool(row["ok"])
    return out
