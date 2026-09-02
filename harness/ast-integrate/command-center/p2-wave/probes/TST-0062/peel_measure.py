#!/usr/bin/env python3
"""Live tag-peel vs rev-list, plus the PowerShell-mangled argv measured on this box."""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

TAG = "v1.4.1"
PEEL = f"{TAG}^{{commit}}"  # v1.4.1^{commit}
LEFTOVER = f"{TAG}^"  # argv pwsh 7.4.6 actually delivered for the unquoted peel


def find_pwsh() -> str | None:
    env_keys = ("TST0062_PWSH", "PWSH", "POWERSHELL")
    candidates: list[str] = []
    for k in env_keys:
        v = os.environ.get(k)
        if v:
            candidates.append(v)
    which = shutil.which("pwsh") or shutil.which("pwsh.exe")
    if which:
        candidates.append(which)
    here = Path(__file__).resolve().parent
    repo = here.parents[3]
    candidates.extend(
        [
            "/tmp/tst0062-pwsh/pwsh",
            "/tmp/tst-0062-pwsh/pwsh",
            str(here.parent / "CNF-0021/tools/pwsh/pwsh"),
            str(repo / "command-center/p2-wave/probes/CNF-0021/tools/pwsh/pwsh"),
        ]
    )
    seen: set[str] = set()
    for raw in candidates:
        p = Path(raw)
        if str(p) in seen:
            continue
        seen.add(str(p))
        if not p.is_file():
            continue
        mode = p.stat().st_mode
        if not (mode & stat.S_IXUSR):
            try:
                p.chmod(mode | stat.S_IXUSR)
            except OSError:
                continue
        if os.access(p, os.X_OK):
            return str(p)
    return None


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def build_annotated_tag_repo(root: Path) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "tst-0062@invalid")
    _git(root, "config", "user.name", "TST-0062")
    (root / "tracked.txt").write_text("one\n", encoding="utf-8")
    _git(root, "add", "tracked.txt")
    _git(root, "commit", "-m", "c1")
    (root / "tracked.txt").write_text("two\n", encoding="utf-8")
    _git(root, "add", "tracked.txt")
    _git(root, "commit", "-m", "c2")
    _git(root, "tag", "-a", TAG, "-m", "annotated v1.4.1")


def _sha(proc: subprocess.CompletedProcess[str]) -> str:
    return (proc.stdout or "").strip().splitlines()[0] if proc.returncode == 0 and proc.stdout else ""


def run_bash(cwd: Path, script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "--norc", "--noprofile", "-c", script],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def run_pwsh(pwsh: str, cwd: Path, command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [pwsh, "-NoProfile", "-Command", command],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def row(kind: str, proc: subprocess.CompletedProcess[str], **extra) -> dict:
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    sha = _sha(proc)
    rec = {
        "kind": kind,
        "returncode": proc.returncode,
        "sha": sha,
        "stdout_tail": out[-400:],
        "stderr_tail": err[-400:],
        "ok": proc.returncode == 0 and bool(sha) and " " not in sha,
    }
    rec.update(extra)
    return rec


def measure(repo: Path, pwsh: str | None) -> dict:
    tag_obj = row("git-argv-tag-object", _git(repo, "rev-parse", TAG), argv=[TAG])
    peel_argv = row("git-argv-quoted-peel-equivalent", _git(repo, "rev-parse", PEEL), argv=[PEEL])
    rev_list = row("git-argv-rev-list", _git(repo, "rev-list", "-n", "1", TAG), argv=["-n", "1", TAG])
    leftover = row("git-argv-pwsh-leftover", _git(repo, "rev-parse", LEFTOVER), argv=[LEFTOVER])
    cmd_mangled = f"{TAG}{{commit}}"  # cmd.exe: ^ escapes {
    cmd_row = row("git-argv-cmd-caret-unescape", _git(repo, "rev-parse", cmd_mangled), argv=[cmd_mangled])

    bash_quoted = row(
        "bash-quoted-peel",
        run_bash(repo, "git rev-parse 'v1.4.1^{commit}'"),
        shell="bash",
        command="git rev-parse 'v1.4.1^{commit}'",
    )
    bash_rev_list = row(
        "bash-rev-list",
        run_bash(repo, "git rev-list -n 1 v1.4.1"),
        shell="bash",
        command="git rev-list -n 1 v1.4.1",
    )

    pwsh_rows: dict[str, dict] = {}
    pwsh_version = None
    if pwsh:
        ver = subprocess.run(
            [pwsh, "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"],
            capture_output=True,
            text=True,
            check=False,
        )
        pwsh_version = (ver.stdout or "").strip()
        pwsh_rows["unquoted_peel"] = row(
            "pwsh-unquoted-peel",
            run_pwsh(pwsh, repo, "git rev-parse v1.4.1^{commit}"),
            shell="pwsh",
            command="git rev-parse v1.4.1^{commit}",
        )
        pwsh_rows["single_quoted_peel"] = row(
            "pwsh-single-quoted-peel",
            run_pwsh(pwsh, repo, "git rev-parse 'v1.4.1^{commit}'"),
            shell="pwsh",
            command="git rev-parse 'v1.4.1^{commit}'",
        )
        pwsh_rows["double_quoted_peel"] = row(
            "pwsh-double-quoted-peel",
            run_pwsh(pwsh, repo, 'git rev-parse "v1.4.1^{commit}"'),
            shell="pwsh",
            command='git rev-parse "v1.4.1^{commit}"',
        )
        pwsh_rows["pwsh_rev_list"] = row(
            "pwsh-rev-list",
            run_pwsh(pwsh, repo, "git rev-list -n 1 v1.4.1"),
            shell="pwsh",
            command="git rev-list -n 1 v1.4.1",
        )

    commit_sha = peel_argv["sha"]
    return {
        "tag": TAG,
        "peel_form": PEEL,
        "pwsh_path": pwsh,
        "pwsh_version": pwsh_version,
        "commit_sha": commit_sha,
        "tag_object_sha": tag_obj["sha"],
        "tag_object_differs_from_commit": bool(tag_obj["sha"]) and tag_obj["sha"] != commit_sha,
        "rows": {
            "tag_object": tag_obj,
            "peel_argv": peel_argv,
            "rev_list": rev_list,
            "pwsh_leftover_argv": leftover,
            "cmd_caret_unescape": cmd_row,
            "bash_quoted": bash_quoted,
            "bash_rev_list": bash_rev_list,
            **pwsh_rows,
        },
    }


def live_measure() -> dict:
    pwsh = find_pwsh()
    tmp = tempfile.mkdtemp(prefix="tst0062-peel-")
    repo = Path(tmp)
    try:
        build_annotated_tag_repo(repo)
        return measure(repo, pwsh)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def equivalent(a: str, b: str) -> bool:
    return bool(a) and a == b and len(a) == 40 and all(c in "0123456789abcdef" for c in a)
