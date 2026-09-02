"""Round-trip argv through real shells.

Catalog control: a deliberately apostrophe-bearing payload MUST fail when
naively wrapped in POSIX single quotes, and MUST succeed when the same
payload is passed as a filesystem path / argv element (no shell wrap).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from helpers import HERE

ECHO = HERE / "argv_echo.py"
PAYLOAD = "o'reilly"
CLEAN = "oreilly"
TIMEOUT = 20


def _which(name: str) -> str | None:
    return shutil.which(name)


def discover_shells() -> dict:
    git_bash_candidates = [
        "/mnt/c/Program Files/Git/bin/bash.exe",
        "/usr/bin/git-bash",
    ]
    git_bash = next((p for p in git_bash_candidates if Path(p).is_file()), None)
    return {
        "sh": _which("sh"),
        "bash": _which("bash"),
        "dash": _which("dash"),
        "pwsh": _which("pwsh") or _which("pwsh.exe"),
        "powershell": _which("powershell") or _which("powershell.exe"),
        "git_bash": git_bash,
    }


def _parse_argv(stdout: str) -> list | None:
    lines = [ln.strip() for ln in (stdout or "").splitlines() if ln.strip()]
    if not lines:
        return None
    try:
        data = json.loads(lines[-1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None


def _run(argv: list[str]) -> dict:
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "argv": argv,
            "rc": 124 if isinstance(exc, subprocess.TimeoutExpired) else 127,
            "stdout_tail": "",
            "stderr_tail": str(exc)[:400],
            "received": None,
        }
    received = _parse_argv(proc.stdout)
    return {
        "argv": argv,
        "rc": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-400:],
        "stderr_tail": (proc.stderr or "")[-400:],
        "received": received,
    }


def naive_single_quote_command(payload: str) -> str:
    """Intentionally naive: wrap payload in literal apostrophes."""
    py = sys.executable
    echo = str(ECHO)
    return f"{py} {echo} '{payload}'"


def argv_matches(run: dict, expected: list[str]) -> bool:
    if run.get("rc") != 0:
        return False
    return run.get("received") == expected


def roundtrip_apostrophe(shell_bin: str, label: str) -> dict:
    naive = naive_single_quote_command(PAYLOAD)
    clean = naive_single_quote_command(CLEAN)
    bad = _run([shell_bin, "-c", naive])
    good_literal = _run([shell_bin, "-c", clean])
    with tempfile.TemporaryDirectory(prefix="aud86-rt-") as tmp:
        path = Path(tmp) / PAYLOAD
        path.write_text("ok\n", encoding="utf-8")
        file_run = _run([sys.executable, str(ECHO), str(path)])
        file_ok = argv_matches(file_run, [str(path)])
    inline_failed = not argv_matches(bad, [PAYLOAD])
    clean_ok = argv_matches(good_literal, [CLEAN])
    return {
        "shell": label,
        "bin": shell_bin,
        "inline_apostrophe_failed": inline_failed,
        "inline_rc": bad["rc"],
        "inline_received": bad.get("received"),
        "clean_literal_ok": clean_ok,
        "file_path_ok": file_ok,
        "file_received": file_run.get("received"),
        "pass": bool(inline_failed and clean_ok and file_ok),
        "inline_stderr_tail": bad.get("stderr_tail") or "",
    }


def roundtrip_procsubst(bash: str | None, sh: str | None) -> dict:
    script = "cat <(printf '%s' hi)"
    bash_run = _run([bash, "-c", script]) if bash else None
    sh_run = _run([sh, "-c", script]) if sh else None
    bash_out = (bash_run.get("stdout_tail") or "") if bash_run else ""
    bash_ok = bool(bash_run and bash_run["rc"] == 0 and "hi" in bash_out)
    sh_failed = bool(sh_run and sh_run["rc"] != 0)
    return {
        "bash_supports_procsubst": bash_ok,
        "sh_rejects_procsubst": sh_failed,
        "sh_rc": None if not sh_run else sh_run["rc"],
        "bash_rc": None if not bash_run else bash_run["rc"],
        "pass": bool((not bash or bash_ok) and (not sh or sh_failed) and (bash or sh)),
    }


def run_roundtrips() -> dict:
    shells = discover_shells()
    posix: list[dict] = []
    for label in ("sh", "bash"):
        bin_path = shells.get(label)
        if bin_path:
            posix.append(roundtrip_apostrophe(bin_path, label))
    posix_pass = bool(posix) and all(r["pass"] for r in posix)
    proc = roundtrip_procsubst(shells.get("bash"), shells.get("sh"))
    pwsh_present = bool(shells.get("pwsh") or shells.get("powershell"))
    git_bash_present = bool(shells.get("git_bash"))
    return {
        "payload": PAYLOAD,
        "clean_payload": CLEAN,
        "shells": shells,
        "posix_apostrophe": posix,
        "posix_pass": posix_pass,
        "procsubst": proc,
        "pwsh_present": pwsh_present,
        "git_bash_present": git_bash_present,
        "control_pass": posix_pass,
        "control": {
            "inline_apostrophe_failed": all(r["inline_apostrophe_failed"] for r in posix)
            if posix
            else False,
            "file_path_succeeded": all(r["file_path_ok"] for r in posix) if posix else False,
            "clean_literal_succeeded": all(r["clean_literal_ok"] for r in posix)
            if posix
            else False,
        },
    }


def main() -> int:
    result = run_roundtrips()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if not result.get("control_pass"):
        print("FAILED:AUD-0086-roundtrip apostrophe-inline vs file-path control")
        return 1
    print("SUCCESS:AUD-0086-roundtrip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
