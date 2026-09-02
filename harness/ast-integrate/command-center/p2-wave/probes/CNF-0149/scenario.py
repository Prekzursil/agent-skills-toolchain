#!/usr/bin/env python3
"""Isolated git fixture for CNF-0149 line-ending route measurements.

Does not touch the parent worktree's git state. All `git add` / `git commit`
run only inside a TemporaryDirectory repo.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

UNIT = "CNF-0149"
CLASSIC_BLOB = 3737
CLASSIC_NEWLINES = 100
CONTROL = "control-lf.txt"
REVIEWER = "reviewer-second.txt"
KNOWN_CRLF = "known-crlf.txt"
GOOD_PY = "good.py"
BAD_PY = "bad.py"
REGISTER = "register.md"
GATTR = ".gitattributes"

GIT_ENV = {
    "GIT_AUTHOR_NAME": "CNF-0149",
    "GIT_AUTHOR_EMAIL": "cnf-0149@invalid.local",
    "GIT_COMMITTER_NAME": "CNF-0149",
    "GIT_COMMITTER_EMAIL": "cnf-0149@invalid.local",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_OPTIONAL_LOCKS": "0",
}


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.update(GIT_ENV)
    cmd = [
        "git",
        "-c",
        "user.name=CNF-0149",
        "-c",
        "user.email=cnf-0149@invalid.local",
        "-c",
        "core.autocrlf=false",
        "-c",
        "core.safecrlf=false",
        "-C",
        str(repo),
        *args,
    ]
    proc = subprocess.run(cmd, capture_output=True, env=env)
    if check and proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace")
        out = (proc.stdout or b"").decode("utf-8", "replace")
        raise RuntimeError(f"git {args} failed rc={proc.returncode}\n{err}\n{out}")
    return proc


def classic_control_bytes() -> bytes:
    nlines = CLASSIC_NEWLINES
    budget = CLASSIC_BLOB - nlines
    base, extra = divmod(budget, nlines)
    parts: list[bytes] = []
    for i in range(nlines):
        n = base + (1 if i < extra else 0)
        prefix = f"{i:03d}.".encode("ascii")
        rest = n - len(prefix)
        if rest < 0:
            parts.append(b"x" * n + b"\n")
        else:
            parts.append(prefix + (b"x" * rest) + b"\n")
    data = b"".join(parts)
    if len(data) != CLASSIC_BLOB or data.count(b"\n") != nlines or b"\r" in data:
        n_nl = data.count(b"\n")
        n_cr = data.count(b"\r")
        raise AssertionError(
            f"classic control bytes={len(data)} nl={n_nl} cr={n_cr}"
        )
    return data


def reviewer_bytes() -> bytes:
    lines = [f"reviewer-line-{i:02d} three-route second file\n" for i in range(40)]
    data = "".join(lines).encode("utf-8")
    if b"\r" in data:
        raise AssertionError("reviewer file must be LF")
    return data


def known_crlf_bytes() -> bytes:
    return b"committed-crlf-one\r\ncommitted-crlf-two\r\ncommitted-crlf-three\r\n"


def good_py_bytes() -> bytes:
    return (
        "def greet(name: str) -> str:\n"
        "    return f'hello {name}'\n"
        "\n"
        "\n"
        "def main() -> None:\n"
        "    print(greet('world'))\n"
    ).encode("utf-8")


def bad_py_bytes() -> bytes:
    # Deliberate style breaks: space after '(', double space after return.
    return (
        "def greet( name:str )->str:\n"
        "  return  f'hello {name}'\n"
        "\n"
        "def main()->None:\n"
        "    print( greet('world') )\n"
    ).encode("utf-8")


def register_bytes() -> bytes:
    return (
        "# register snapshot\n"
        "R-A01 OPEN next-action=measure\n"
        "R-B06 OPEN next-action=hash-blob\n"
        "recorded provenance is the LF blob of this file\n"
    ).encode("utf-8")


def gitattributes_text() -> str:
    # eol=crlf makes `git archive` run convert_to_working_tree -> CRLF.
    # register.md is `text` with no eol= so core.autocrlf actually changes checkout.
    # known-crlf.txt is -text so CRLF survives in the blob.
    return (
        f"{CONTROL} text eol=crlf\n"
        f"{REVIEWER} text eol=crlf\n"
        f"{KNOWN_CRLF} -text\n"
        f"{GOOD_PY} text eol=lf\n"
        f"{BAD_PY} text eol=lf\n"
        f"{REGISTER} text\n"
    )


def build_repo(root: Path) -> dict:
    repo = root / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-b", "main")
    (repo / CONTROL).write_bytes(classic_control_bytes())
    (repo / REVIEWER).write_bytes(reviewer_bytes())
    (repo / KNOWN_CRLF).write_bytes(known_crlf_bytes())
    (repo / GOOD_PY).write_bytes(good_py_bytes())
    (repo / BAD_PY).write_bytes(bad_py_bytes())
    (repo / REGISTER).write_bytes(register_bytes())
    (repo / GATTR).write_text(gitattributes_text(), encoding="utf-8", newline="\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "CNF-0149 fixture: LF control, CRLF blob, format pair")
    rev = git(repo, "rev-parse", "HEAD").stdout.decode().strip()
    return {"repo": repo, "rev": rev}


def clone_checkout(repo: Path, dest: Path, autocrlf: str) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(GIT_ENV)
    # `git clone -c` writes core.autocrlf into the new repo before checkout.
    proc = subprocess.run(
        [
            "git",
            "clone",
            "-c",
            f"core.autocrlf={autocrlf}",
            "--quiet",
            str(repo),
            str(dest),
        ],
        capture_output=True,
        env=env,
    )
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace")
        raise RuntimeError(f"git clone autocrlf={autocrlf} failed: {err}")
    # Persist the mode. Do not use git() here for checkout: that helper pins
    # core.autocrlf=false so blobs stay LF when the fixture is built.
    subprocess.run(
        [
            "git",
            "-C",
            str(dest),
            "config",
            "core.autocrlf",
            autocrlf,
        ],
        capture_output=True,
        env=env,
        check=True,
    )
    if autocrlf == "true":
        subprocess.run(
            ["git", "-C", str(dest), "config", "core.eol", "crlf"],
            capture_output=True,
            env=env,
            check=True,
        )
        sample = dest / REGISTER
        if sample.is_file() and b"\r" not in sample.read_bytes():
            for args in (
                ["rm", "-r", "--cached", "-q", "."],
                ["checkout", "-f", "HEAD"],
            ):
                proc = subprocess.run(
                    [
                        "git",
                        "-c",
                        "core.autocrlf=true",
                        "-c",
                        "core.eol=crlf",
                        "-C",
                        str(dest),
                        *args,
                    ],
                    capture_output=True,
                    env=env,
                )
                if proc.returncode != 0:
                    err = (proc.stderr or b"").decode("utf-8", "replace")
                    raise RuntimeError(f"git {args} renormalize failed: {err}")
    return dest
