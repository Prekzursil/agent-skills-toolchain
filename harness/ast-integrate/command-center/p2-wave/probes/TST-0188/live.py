#!/usr/bin/env python3
"""Live tag/commit dereference plus both-states caret-mangle control.

windows-shell.md:2: unquoted `tag^{commit}` / `HEAD^` is corrupted because `^`
is the cmd.exe escape and `{...}` is a PowerShell script block. The sanctioned
form is `git rev-list -n 1 <tag>` or a quoted peel.

This box has no pwsh7 binary. The control is still live git: we apply the
documented rewrites to argv and feed git, proving the mangled form is wrong
or errored and the sanctioned form matches `git rev-list -n 1`.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAG = "v-tst-0188"
PWSH_CANDIDATES = ("pwsh", "pwsh.exe", "powershell", "powershell.exe")


def which_pwsh() -> str | None:
    for name in PWSH_CANDIDATES:
        found = shutil.which(name)
        if found:
            return found
    return None


def cmd_caret_escape(token: str) -> str:
    """cmd.exe: `^` escapes the next character (or is dropped at EOL)."""
    out: list[str] = []
    i = 0
    while i < len(token):
        if token[i] == "^":
            i += 1
            if i < len(token):
                out.append(token[i])
                i += 1
            continue
        out.append(token[i])
        i += 1
    return "".join(out)


def pwsh_unquoted_native(token: str) -> str:
    """pwsh argument-mode: unquoted `{...}` is a script block, not argv text.

    `tag^{commit}` therefore loses the peel spec (and the caret that introduced
    it), so git sees the bare tag name — the annotated tag object, not the commit.
    """
    return re.sub(r"\^?\{[^{}]*\}", "", token)


def git(repo: Path, args: list[str], check: bool = False) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.setdefault("GIT_AUTHOR_NAME", "TST-0188")
    env.setdefault("GIT_AUTHOR_EMAIL", "tst-0188@test.invalid")
    env.setdefault("GIT_COMMITTER_NAME", "TST-0188")
    env.setdefault("GIT_COMMITTER_EMAIL", "tst-0188@test.invalid")
    env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
        env=env,
    )


def build_fixture(root: Path) -> dict:
    git(root, ["init", "-q"], check=True)
    git(root, ["config", "user.name", "TST-0188"], check=True)
    git(root, ["config", "user.email", "tst-0188@test.invalid"], check=True)
    git(root, ["config", "advice.detachedHead", "false"], check=True)
    (root / "file.txt").write_text("one\n", encoding="utf-8")
    git(root, ["add", "file.txt"], check=True)
    git(root, ["commit", "-q", "-m", "one"], check=True)
    parent = git(root, ["rev-parse", "HEAD"], check=True).stdout.strip()
    (root / "file.txt").write_text("one\ntwo\n", encoding="utf-8")
    git(root, ["add", "file.txt"], check=True)
    git(root, ["commit", "-q", "-m", "two"], check=True)
    head = git(root, ["rev-parse", "HEAD"], check=True).stdout.strip()
    git(root, ["tag", "-a", TAG, "-m", "annotated TST-0188"], check=True)
    tag_obj = git(root, ["rev-parse", TAG], check=True).stdout.strip()
    peeled = git(root, ["rev-parse", f"{TAG}^{{commit}}"], check=True).stdout.strip()
    via_list = git(root, ["rev-list", "-n", "1", TAG], check=True).stdout.strip()
    parent_via_caret = git(root, ["rev-parse", "HEAD^"], check=True).stdout.strip()
    return {
        "parent": parent,
        "head": head,
        "tag_obj": tag_obj,
        "peeled": peeled,
        "via_list": via_list,
        "parent_via_caret": parent_via_caret,
        "tag": TAG,
    }


def run_live() -> dict:
    pwsh = which_pwsh()
    tmp = tempfile.mkdtemp(prefix="tst0188-")
    repo = Path(tmp)
    try:
        ids = build_fixture(repo)
        cmd_head = cmd_caret_escape("HEAD^")
        cmd_peel = cmd_caret_escape(f"{TAG}^{{commit}}")
        pwsh_peel = pwsh_unquoted_native(f"{TAG}^{{commit}}")
        quoted_ok = ids["peeled"]
        listed = ids["via_list"]

        mangled_head = git(repo, ["rev-parse", cmd_head])
        mangled_peel_cmd = git(repo, ["rev-parse", cmd_peel])
        mangled_peel_pwsh = git(repo, ["rev-parse", pwsh_peel])
        quoted_peel = git(repo, ["rev-parse", f"{TAG}^{{commit}}"])
        listed_run = git(repo, ["rev-list", "-n", "1", TAG])

        head_wrong = (
            mangled_head.returncode == 0
            and mangled_head.stdout.strip() == ids["head"]
            and ids["head"] != ids["parent"]
        )
        peel_cmd_errored = mangled_peel_cmd.returncode != 0
        peel_pwsh_sha = (mangled_peel_pwsh.stdout or "").strip()
        peel_pwsh_wrong = mangled_peel_pwsh.returncode != 0 or peel_pwsh_sha != ids[
            "peeled"
        ]
        sanctioned_match = (
            quoted_ok == listed == ids["peeled"] == ids["head"]
            and quoted_peel.returncode == 0
            and listed_run.returncode == 0
            and quoted_peel.stdout.strip() == listed
        )
        pwsh_live = None
        if pwsh:
            script = repo / "_caret.ps1"
            script.write_text(
                f"Set-Location '{repo.as_posix()}'\n"
                f"git rev-parse {TAG}^{{commit}}\n",
                encoding="utf-8",
            )
            qscript = repo / "_quoted.ps1"
            qscript.write_text(
                f"Set-Location '{repo.as_posix()}'\n"
                f"git rev-list -n 1 {TAG}\n"
                f"git rev-parse '{TAG}^{{commit}}'\n",
                encoding="utf-8",
            )
            bad = subprocess.run(
                [pwsh, "-NoProfile", "-NonInteractive", "-File", str(script)],
                capture_output=True,
                text=True,
            )
            good = subprocess.run(
                [pwsh, "-NoProfile", "-NonInteractive", "-File", str(qscript)],
                capture_output=True,
                text=True,
            )
            pwsh_live = {
                "binary": pwsh,
                "unquoted_exit": bad.returncode,
                "unquoted_stdout": (bad.stdout or "").strip()[:200],
                "unquoted_stderr": (bad.stderr or "").strip()[:200],
                "quoted_exit": good.returncode,
                "quoted_stdout": (good.stdout or "").strip()[:200],
            }

        return {
            "repo": str(repo),
            "pwsh_binary": pwsh,
            "objects": ids,
            "mangle": {
                "cmd_HEAD^": cmd_head,
                f"cmd_{TAG}^{{commit}}": cmd_peel,
                f"pwsh_{TAG}^{{commit}}": pwsh_peel,
            },
            "results": {
                "cmd_HEAD^_sha": (mangled_head.stdout or "").strip(),
                "cmd_HEAD^_rc": mangled_head.returncode,
                "cmd_peel_rc": mangled_peel_cmd.returncode,
                "cmd_peel_err": (mangled_peel_cmd.stderr or "").strip()[:240],
                "pwsh_peel_sha": (mangled_peel_pwsh.stdout or "").strip(),
                "pwsh_peel_rc": mangled_peel_pwsh.returncode,
                "quoted_peel_sha": (quoted_peel.stdout or "").strip(),
                "rev_list_sha": (listed_run.stdout or "").strip(),
            },
            "head_caret_wrong_object": head_wrong,
            "cmd_peel_errored": peel_cmd_errored,
            "pwsh_peel_wrong_or_errored": peel_pwsh_wrong,
            "sanctioned_match": sanctioned_match,
            "annotated_tag_differs_from_commit": ids["tag_obj"] != ids["peeled"],
            "parent_differs_from_head": ids["parent"] != ids["head"],
            "pwsh_live": pwsh_live,
            "pass": bool(
                head_wrong
                and peel_cmd_errored
                and peel_pwsh_wrong
                and sanctioned_match
                and ids["tag_obj"] != ids["peeled"]
                and ids["parent"] != ids["head"]
            ),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
