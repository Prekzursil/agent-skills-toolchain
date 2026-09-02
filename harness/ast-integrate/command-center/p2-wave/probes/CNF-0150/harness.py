"""Live engines for the four CNF-0150 shell traps.

Windows PowerShell 7 and Git Bash are absent on this Linux worktree.
GNU bash 5.2 here is the same interpreter WSL bash would run. PATHEXT
Get-Command, MSYS path conversion, Git-Bash igncr, and cmd caret-unescape
are executable models of those shells' documented argv/PATH behaviour,
labeled as models in every cell that uses them.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

MSYS_PREFIX = r"C:\Program Files\Git"
PATHEXT = (".COM", ".EXE", ".BAT", ".CMD", ".VBS", ".JS", ".MSC")
BASH = "/usr/bin/bash"


def cmd_caret_unescape(text: str) -> str:
    """cmd.exe caret: '^' escapes the next character; a trailing '^' is dropped."""
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == "^":
            if i + 1 < len(text):
                out.append(text[i + 1])
                i += 2
            else:
                i += 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def msys_convert_arg(arg: str, env: dict[str, str] | None = None) -> str:
    """Git-for-Windows / MSYS POSIX-path rewrite (documented trap)."""
    env = env or {}
    if str(env.get("MSYS_NO_PATHCONV") or "").strip():
        return arg
    if not arg.startswith("/") or arg.startswith("//"):
        return arg
    if len(arg) >= 2 and arg[1].isalpha() and (len(arg) == 2 or arg[2] == "/"):
        drive = arg[1].upper()
        rest = arg[3:] if len(arg) > 2 else ""
        return drive + ":\\" + rest.replace("/", "\\")
    return MSYS_PREFIX + arg.replace("/", "\\")


def msys_convert_argv(argv: list[str], env: dict[str, str] | None = None) -> list[str]:
    return [msys_convert_arg(a, env) for a in argv]


def get_command(name: str, path_dirs: list[Path]) -> Path | None:
    """PowerShell Get-Command: PATHEXT search, including non-executable .cmd shims.

    Windows filesystems compare names case-insensitively; this Linux worktree
    does not, so the match is done on the uppercased filename.
    """
    upper = name.upper()
    want = {upper} | {upper + ext for ext in PATHEXT}
    for directory in path_dirs:
        if not directory.is_dir():
            continue
        for child in directory.iterdir():
            if child.is_file() and child.name.upper() in want:
                return child
    return None


def posix_which(name: str, path_dirs: list[Path]) -> Path | None:
    """Git Bash `which` / POSIX which: exact name, must be executable. Misses .cmd."""
    for directory in path_dirs:
        candidate = directory / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def strip_cr(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def bash_syntax_check(script: Path, igncr: bool) -> tuple[int, str]:
    """Return (exit, combined output). igncr=True is the Git-Bash default."""
    if igncr:
        cleaned = Path(str(script) + ".lf")
        cleaned.write_bytes(strip_cr(script.read_text(encoding="utf-8")).encode("utf-8"))
        target = cleaned
    else:
        target = script
    proc = subprocess.run(
        [BASH, "-n", str(target)],
        capture_output=True,
        text=True,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def shebang_exec(script: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [str(script)],
        capture_output=True,
        text=True,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def real_git() -> str:
    found = shutil.which("git")
    if not found:
        raise RuntimeError("git binary missing")
    return found


def make_two_commit_repo(root: Path) -> Path:
    repo = root / "caret-repo"
    repo.mkdir()
    git = real_git()
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "CNF-0150"
    env["GIT_AUTHOR_EMAIL"] = "cnf0150@example.invalid"
    env["GIT_COMMITTER_NAME"] = "CNF-0150"
    env["GIT_COMMITTER_EMAIL"] = "cnf0150@example.invalid"
    subprocess.run([git, "init", "-q", str(repo)], check=True, capture_output=True)
    subprocess.run(
        [git, "-C", str(repo), "config", "user.email", "cnf0150@example.invalid"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [git, "-C", str(repo), "config", "user.name", "CNF-0150"],
        check=True,
        capture_output=True,
    )
    (repo / "f.txt").write_text("one\n", encoding="utf-8")
    subprocess.run([git, "-C", str(repo), "add", "f.txt"], check=True, capture_output=True)
    subprocess.run(
        [git, "-C", str(repo), "commit", "-q", "-m", "one"],
        check=True,
        capture_output=True,
        env=env,
    )
    (repo / "f.txt").write_text("two\n", encoding="utf-8")
    subprocess.run([git, "-C", str(repo), "add", "f.txt"], check=True, capture_output=True)
    subprocess.run(
        [git, "-C", str(repo), "commit", "-q", "-m", "two"],
        check=True,
        capture_output=True,
        env=env,
    )
    return repo


def git_rev_parse(repo: Path, ref: str, via_cmd_shim: bool) -> tuple[int, str, str]:
    """Return (exit, stdout, argv_seen). via_cmd_shim applies caret unescape."""
    git = real_git()
    seen = cmd_caret_unescape(ref) if via_cmd_shim else ref
    proc = subprocess.run(
        [git, "-C", str(repo), "rev-parse", "--verify", seen],
        capture_output=True,
        text=True,
    )
    return proc.returncode, (proc.stdout or "").strip(), seen


def write_cmd_shim(directory: Path, name: str = "onlyshim") -> Path:
    path = directory / f"{name}.cmd"
    path.write_text("@echo off\r\necho shim-ok\r\n", encoding="utf-8")
    path.chmod(path.stat().st_mode & ~stat.S_IXUSR & ~stat.S_IXGRP & ~stat.S_IXOTH)
    return path


def write_crlf_agent_sh(path: Path) -> Path:
    # Agent-written .sh with CRLF on compound commands: GNU bash -n fails;
    # Git Bash igncr (CR stripped first) passes.
    body = "#!/usr/bin/env bash\r\nif true; then\r\n  printf 'ok\\n'\r\nfi\r\n"
    path.write_bytes(body.encode("ascii"))
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def write_portable_sh(path: Path) -> Path:
    path.write_text("#!/usr/bin/env bash\nprintf 'portable-ok\\n'\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def run_portable(script: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [BASH, str(script)],
        capture_output=True,
        text=True,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def run_python_argv() -> tuple[int, str]:
    proc = subprocess.run(
        ["python3", "-c", "print('argv-ok')"],
        capture_output=True,
        text=True,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text
