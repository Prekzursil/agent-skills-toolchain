"""Git-archive vs cat-file authority harness (TST-0252)."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Recipe:
    kind: str
    command: str
    name: str = ""


class Proc:
    def __init__(self, returncode: int, stdout: bytes, stderr: bytes = b"") -> None:
        self.returncode = returncode
        self.exit_code = returncode
        self.stdout = stdout
        self.stderr = stderr


def git(repo: Path, *args: str) -> Proc:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=False,
    )
    return Proc(proc.returncode, proc.stdout or b"", proc.stderr or b"")


def measure(data: bytes) -> dict[str, Any]:
    raw = data or b""
    return {
        "bytes": len(raw),
        "sha256": __import__("hashlib").sha256(raw).hexdigest(),
        "crlf": raw.count(b"\r\n"),
        "lf": raw.count(b"\n"),
        "eol_crlf": b"\r\n" in raw,
    }


def authority_bytes(repo: Path, rel: str, rev: str = "HEAD") -> bytes:
    proc = git(repo, "cat-file", "-p", f"{rev}:{rel}")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace"))
    return proc.stdout.replace(b"\r\n", b"\n")


def run_recipe(repo: Path, command: str) -> Proc:
    if command.startswith("git archive"):
        # git archive HEAD rel | tar -xO
        rel = command.split()[-1] if "tar" not in command.split()[-1] else command.split()[3]
        parts = command.replace("|", " ").split()
        # command: git archive HEAD {rel} | tar -xO
        rel = ""
        toks = command.split()
        if "HEAD" in toks:
            i = toks.index("HEAD")
            if i + 1 < len(toks):
                rel = toks[i + 1]
        proc = subprocess.run(
            f"git -C {repo} archive HEAD {rel} | tar -xO",
            shell=True,
            capture_output=True,
        )
        return Proc(proc.returncode, proc.stdout or b"", proc.stderr or b"")
    if command.startswith("git cat-file"):
        rel = command.split("HEAD:", 1)[-1]
        return git(repo, "cat-file", "-p", f"HEAD:{rel}")
    proc = subprocess.run(command, cwd=str(repo), shell=True, capture_output=True)
    return Proc(proc.returncode, proc.stdout or b"", proc.stderr or b"")


def three_route_table(repo: Path, rel: str, rev: str) -> dict[str, Any]:
    blob = git(repo, "cat-file", "-p", f"{rev}:{rel}").stdout
    show = git(repo, "show", f"{rev}:{rel}").stdout
    arch = subprocess.run(
        f"git -C {repo} archive {rev} {rel} | tar -xO",
        shell=True,
        capture_output=True,
    ).stdout
    blob_n = blob.replace(b"\r\n", b"\n")
    arch_n = arch.replace(b"\r\n", b"\n")
    return {
        "catfile_equals_show": blob == show or blob.replace(b"\r\n", b"\n") == show.replace(b"\r\n", b"\n"),
        "archive_differs_from_blob": arch != blob,
        "archive_eol_only": arch != blob and arch_n == blob_n,
        "blob_bytes": len(blob),
        "archive_bytes": len(arch),
    }


def _compare(got: bytes, authority: bytes) -> dict[str, Any]:
    got_n = got.replace(b"\r\n", b"\n")
    auth_n = authority.replace(b"\r\n", b"\n")
    return {
        "equal": got == authority,
        "eol_only_difference": got != authority and got_n == auth_n,
        "got": measure(got),
        "authority": measure(authority),
    }


def judge(run: Proc, authority: bytes) -> dict[str, Any]:
    cmp_ = _compare(run.stdout or b"", authority)
    if cmp_["equal"]:
        verdict, reason = "PASS", "bytes-match"
    elif cmp_["eol_only_difference"]:
        verdict, reason = "FAIL", "wrong-bytes-eol-only"
    else:
        verdict, reason = "FAIL", "wrong-bytes"
    return {
        "verdict": verdict,
        "reason": reason,
        "exit_code": run.exit_code,
        "compare": cmp_,
    }


def judge_exit_code_only(run: Proc, authority: bytes) -> dict[str, Any]:
    del authority
    return {
        "verdict": "PASS" if run.exit_code == 0 else "FAIL",
        "reason": "exit-code-only",
        "exit_code": run.exit_code,
        "compare": {"got": measure(run.stdout or b""), "eol_only_difference": False},
    }


def judge_name_only(run: Proc, authority: bytes, name: str) -> dict[str, Any]:
    del run, authority
    return {"verdict": "PASS" if name else "FAIL", "reason": "name-only", "name": name}


def extract_recipes(text: str, source: str = "") -> list[Recipe]:
    recipes = []
    for m in re.finditer(r"`(git (?:archive|cat-file)[^`]+)`", text):
        cmd = m.group(1)
        kind = "archive" if "archive" in cmd else "cat-file"
        recipes.append(Recipe(kind=kind, command=cmd, name=kind))
    if not recipes:
        recipes = [
            Recipe(kind="archive", command="git archive HEAD RELEASE-CHECKLIST.md | tar -xO", name="archive"),
            Recipe(kind="cat-file", command="git cat-file -p HEAD:RELEASE-CHECKLIST.md", name="cat-file"),
        ]
    return recipes
