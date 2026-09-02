"""Git Bash igncr vs real POSIX/WSL bash CRLF discrimination.

Git Bash (MSYS) historically enables `igncr`. Linux bash (and WSL bash, which
is real Linux bash) do not: `exit 0\\r` is a numeric-argument error.

This box has no Git Bash binary and `bash -o igncr` is not a valid option.
The Git-Bash PASS state is therefore the documented igncr semantics: strip CR
then invoke the same bash. That is labelled an emulator, never a live Git Bash
run.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "crlf_gitbash_probe.sh"


def write_crlf_fixture(path: Path | None = None) -> Path:
    target = path or FIXTURE
    target.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "#!/usr/bin/env bash\n"
        "# ASSERTION: under Git Bash (igncr) this CRLF script exits 0; "
        "under real WSL/Linux bash `exit 0\\r` is a numeric argument error.\n"
        "echo SUCCESS:git-bash-crlf-cell\n"
        "exit 0\n"
    )
    target.write_bytes(body.replace("\n", "\r\n").encode("ascii"))
    target.chmod(0o755)
    return target


def _run_bash(script: Path, *, strip_cr: bool) -> dict:
    bash = Path("/usr/bin/bash")
    if not bash.is_file():
        bash = Path("bash")
    data = script.read_bytes()
    if b"\r\n" not in data and not strip_cr:
        return {
            "rc": 99,
            "stdout": "",
            "stderr": "fixture is not CRLF; discrimination would be silent",
            "mode": "host-bash-crlf",
        }
    run_path = script
    tmp = None
    if strip_cr:
        fd, name = tempfile.mkstemp(prefix="bld0007-igncr-", suffix=".sh")
        os.close(fd)
        tmp = Path(name)
        tmp.write_bytes(data.replace(b"\r\n", b"\n").replace(b"\r", b""))
        tmp.chmod(0o755)
        run_path = tmp
    try:
        p = subprocess.run(
            [str(bash), str(run_path)],
            capture_output=True,
            timeout=15,
        )
        return {
            "rc": p.returncode,
            "stdout": (p.stdout or b"").decode("utf-8", "replace"),
            "stderr": (p.stderr or b"").decode("utf-8", "replace"),
            "mode": "git-bash-igncr-emulator" if strip_cr else "host-bash-crlf",
            "interpreter": str(bash),
            "script": str(script),
        }
    finally:
        if tmp is not None:
            try:
                tmp.unlink()
            except OSError:
                pass


def discriminate(script: Path | None = None) -> dict:
    path = write_crlf_fixture(script)
    wsl_like = _run_bash(path, strip_cr=False)
    gitbash_like = _run_bash(path, strip_cr=True)
    wsl_fail = wsl_like["rc"] != 0
    git_pass = gitbash_like["rc"] == 0
    both_same = wsl_like["rc"] == gitbash_like["rc"]
    return {
        "ok": bool(wsl_fail and git_pass and not both_same),
        "wsl_or_linux_bash": wsl_like,
        "git_bash_igncr_emulator": gitbash_like,
        "both_states_identical": both_same,
        "probe_path": str(path),
        "note": (
            "host bash is the WSL-bash CRLF rejector (same real-bash semantics). "
            "Git Bash is not installed; PASS state is igncr emulation (CR strip)."
        ),
    }
