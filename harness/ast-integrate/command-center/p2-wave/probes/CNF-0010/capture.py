"""Pinned environment capture for one confirmation run."""

from __future__ import annotations

import locale
import os
import platform
import subprocess
import sys
from pathlib import Path

from contract import NAMED_TOOLS, WINDOWS_RECORDED_RUFF
from resolver import LIVE_PATHEXT, WINDOWS_PATHEXT, powershell_resolve, split_search_path

_VERSION_FLAGS = {
    "python3": ["--version"],
    "python": ["--version"],
    "node": ["--version"],
    "git": ["--version"],
    "ruff": ["--version"],
    "basedpyright": ["--version"],
    "pwsh": ["--version"],
    "bash": ["--version"],
}


def _run(argv: list[str], timeout: float = 8.0) -> str | None:
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if not text:
        return None
    return text.splitlines()[0][:240]


def _version_of(resolved: str | None, name: str) -> str | None:
    if not resolved:
        return None
    flags = _VERSION_FLAGS.get(name, ["--version"])
    return _run([resolved, *flags])


def _git_autocrlf() -> str:
    text = _run(["git", "config", "--get", "core.autocrlf"])
    if text is None or text == "":
        return "unset"
    return text


def _os_release() -> str:
    path = Path("/etc/os-release")
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    return platform.platform()


def _shell_version() -> tuple[str, str]:
    shell = os.environ.get("SHELL") or "/bin/sh"
    name = Path(shell).name
    ver = _run([shell, "--version"]) or "unknown"
    return name, ver


def capture_live(repo: Path) -> dict:
    path_dirs = split_search_path(os.environ.get("PATH") or "")
    tools = []
    resolved: dict[str, str | None] = {}
    versions: dict[str, str | None] = {}
    for name in NAMED_TOOLS:
        hit = powershell_resolve(name, path_dirs, pathext=LIVE_PATHEXT)
        ver = _version_of(hit, name)
        if name in {"python3", "python"} and hit is None:
            hit = sys.executable
            ver = "Python " + sys.version.split()[0]
        resolved[name] = hit
        versions[name] = ver
        tools.append(
            {
                "name": name,
                "resolved_by": "powershell-resolver",
                "resolved_path": hit,
                "version": ver,
            }
        )
    sh_name, sh_ver = _shell_version()
    loc = locale.getlocale()
    lang = os.environ.get("LANG") or (loc[0] or "unset")
    code_page = locale.getpreferredencoding(False) or "unknown"
    node_ver = versions.get("node")
    if node_ver and node_ver.startswith("v"):
        node_ver = node_ver
    manifest = {
        "run_id": "linux-live-" + platform.node(),
        "capture_kind": "live",
        "os": {
            "family": "linux",
            "system": platform.system(),
            "build": platform.version() or platform.release(),
            "release": platform.release(),
            "pretty": _os_release(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "shell": {"name": sh_name, "version": sh_ver},
        "python": {
            "version": sys.version.split()[0],
            "resolved_path": sys.executable,
            "implementation": platform.python_implementation(),
            "full": sys.version,
        },
        "node": {
            "version": node_ver,
            "resolved_path": resolved.get("node"),
        },
        "git": {
            "version": versions.get("git"),
            "autocrlf": _git_autocrlf(),
            "resolved_path": resolved.get("git"),
        },
        "locale": {
            "lang": lang,
            "lc_all": os.environ.get("LC_ALL") or "unset",
            "code_page": code_page,
            "locale_tuple": [loc[0], loc[1]],
        },
        "tools": tools,
        "verbatim": {
            "platform.platform": platform.platform(),
            "platform.version": platform.version(),
            "sys.version": sys.version,
            "git.core.autocrlf": _git_autocrlf(),
            "PATH": os.environ.get("PATH") or "",
            "LANG": os.environ.get("LANG") or "",
            "repo": str(repo),
        },
    }
    return manifest


def capture_windows_fixture(shim_dir: Path) -> dict:
    """Windows-family manifest: PATHEXT resolver + recorded clone fields.

    This host is Linux. The Windows run is a PATHEXT fixture plus the
    verbatim Windows-clone measurements recorded in
    tools/command-center/seed.py (core.autocrlf=true, CRLF REGISTER.md)
    and the catalog's ruff 0.15.22 vs 0.15.17 precedent. capture_kind
    is windows-pathext-fixture, not a live Win32 host.
    """
    shim_dir.mkdir(parents=True, exist_ok=True)
    shim = shim_dir / "ruff.cmd"
    shim.write_text("@echo off\necho ruff 0.15.22\n", encoding="utf-8", newline="\r\n")
    dirs = [str(shim_dir)]
    ruff_path = powershell_resolve("ruff", dirs, pathext=WINDOWS_PATHEXT)
    tools = [
        {
            "name": "ruff",
            "resolved_by": "powershell-resolver",
            "resolved_path": ruff_path,
            "version": WINDOWS_RECORDED_RUFF,
        },
        {
            "name": "python",
            "resolved_by": "powershell-resolver",
            "resolved_path": None,
            "version": "not-captured-on-fixture",
        },
    ]
    verbatim = {
        "source": "tools/command-center/seed.py:140-151",
        "validate_py": "tools/command-center/validate.py:217-222",
        "autocrlf_true_clone": {
            "REGISTER.md_bytes": 61110,
            "CRLF_count": 339,
            "REACH-6": "sha256 721c4e577ca5 != 60a4d35f822d",
        },
        "validate_worktree_vs_blob": {
            "worktree": "1a404a91d819",
            "recorded_blob": "8b3e44cc3813",
        },
        "catalog_ruff_precedent": "CI 0.15.17 vs local 0.15.22 (CNF-0021)",
        "ruff_cmd_shim": str(shim),
        "PATHEXT": ";".join(WINDOWS_PATHEXT),
    }
    return {
        "run_id": "windows-pathext-fixture-recorded-clone",
        "capture_kind": "windows-pathext-fixture",
        "os": {
            "family": "windows",
            "system": "Windows",
            "build": "recorded-windows-clone+PATHEXT-fixture",
            "release": "recorded",
            "pretty": "Windows checkout with core.autocrlf=true (seed.py measurement)",
            "platform": "Windows",
            "machine": "recorded",
        },
        "shell": {"name": "pwsh", "version": "PowerShell Get-Command analogue (this module)"},
        "python": {
            "version": "not-captured-on-fixture",
            "resolved_path": None,
        },
        "node": {"version": None, "resolved_path": None},
        "git": {
            "version": "recorded-windows-clone",
            "autocrlf": "true",
            "resolved_path": None,
        },
        "locale": {
            "lang": "recorded",
            "lc_all": "recorded",
            "code_page": "CRLF-working-tree",
        },
        "tools": tools,
        "verbatim": verbatim,
    }


def tool_version_token(version: str | None) -> str | None:
    """Normalise 'ruff 0.15.17' / 'Python 3.12.3' / 'v24.5.0' to a pin-like token."""
    if not version:
        return None
    text = version.strip()
    if text.lower().startswith("python "):
        text = text.split()[1]
    if text.lower().startswith("ruff "):
        text = text.split()[1]
    if text.startswith("v") and text[1:2].isdigit():
        text = text[1:]
    return text.split()[0]


def pin_parity_rows(live: dict, ci_pins: dict) -> list[dict]:
    by_name = {
        row["name"]: tool_version_token(row.get("version"))
        for row in live.get("tools") or []
    }
    # python lives on the dedicated field as well
    by_name["python"] = live.get("python", {}).get("version")
    rows = []
    for pin in ci_pins.get("formatters_and_linters") or []:
        name = pin["name"]
        local = by_name.get(name)
        ci = pin["pinned_version"]
        rows.append(
            {
                "name": name,
                "ci_pinned": ci,
                "local_resolved": local,
                "equal": local == ci,
                "role": pin.get("role"),
            }
        )
    return rows
