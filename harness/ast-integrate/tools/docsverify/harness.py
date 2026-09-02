"""Git-archive vs cat-file authority harness (TST-0252)."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Recipe:
    """One fenced shell invocation lifted from a document.

    ``line`` is the 1-based line of the command inside ``path`` (the source
    document); ``name`` is the recipe family (``archive`` / ``cat-file`` /
    ``shell``) used by the name-only mutant.
    """

    kind: str
    command: str
    name: str = ""
    line: int = 0
    path: str = ""


class Proc:
    """Completed command: exit code, raw stdout/stderr bytes and the command text."""

    def __init__(
        self,
        returncode: int,
        stdout: bytes,
        stderr: bytes = b"",
        command: str = "",
    ) -> None:
        self.returncode = returncode
        self.exit_code = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.command = command


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
    """Execute one recipe inside ``repo`` and return its raw bytes.

    ``git archive <rev> <path> | tar -xO`` and ``git cat-file -p <rev>:<path>``
    are routed through git directly (so the byte judge sees exactly what the
    documented pipeline produces); anything else runs through the shell.
    """
    toks = command.split()
    if command.startswith("git archive"):
        rev, rel = "HEAD", ""
        rest = [t for t in toks[2:] if not t.startswith("-")]
        if rest:
            rev = rest[0]
        if len(rest) > 1 and rest[1] != "|":
            rel = rest[1]
        proc = subprocess.run(
            f"git -C {repo} archive {rev} {rel} | tar -xO",
            shell=True,
            capture_output=True,
        )
        return Proc(proc.returncode, proc.stdout or b"", proc.stderr or b"", command)
    if command.startswith("git cat-file"):
        spec = toks[-1]
        proc = git(repo, "cat-file", "-p", spec)
        proc.command = command
        return proc
    proc = subprocess.run(command, cwd=str(repo), shell=True, capture_output=True)
    return Proc(proc.returncode, proc.stdout or b"", proc.stderr or b"", command)


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


def judge_name_only(run: Proc, authority: bytes, name: str | None = None) -> dict[str, Any]:
    """Mutant: judges the recipe by its *name*, never by bytes.

    Any command whose text contains ``git archive`` FAILs; everything else
    PASSes -- so a non-git command that emits wrong (CRLF) bytes with exit 0
    is waved through. Kept as a negative control for the byte judge.
    """
    del authority
    text = name if name is not None else getattr(run, "command", "")
    verdict = "FAIL" if "git archive" in text else "PASS"
    return {
        "verdict": verdict,
        "reason": "name-only",
        "name": text,
        "exit_code": run.exit_code,
        "compare": {"got": measure(run.stdout or b""), "eol_only_difference": False},
    }


FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})\s*([A-Za-z0-9_+-]*)\s*$")
SHELL_INFO = {"", "sh", "bash", "shell", "zsh", "console", "text", "powershell", "pwsh"}


def extract_recipes(text: str, source: str = "") -> list[Recipe]:
    """Lift executable recipes from a document's fenced code blocks only.

    Every non-blank, non-comment line inside a shell fence is one recipe;
    ``$ `` prompts are stripped. Inline backtick mentions (prose) are never
    recipes. ``line`` is the 1-based line number of the command in ``text``.
    """
    recipes: list[Recipe] = []
    in_fence = False
    fence_marker = ""
    shell_fence = False
    for lineno, raw in enumerate(text.splitlines(), start=1):
        m = FENCE_RE.match(raw)
        if m and not in_fence:
            in_fence, fence_marker = True, m.group(1)[0]
            shell_fence = m.group(2).lower() in SHELL_INFO
            continue
        if in_fence and m and m.group(1)[0] == fence_marker and not m.group(2):
            in_fence, shell_fence = False, False
            continue
        if not in_fence or not shell_fence:
            continue
        cmd = raw.strip()
        if cmd.startswith("$ "):
            cmd = cmd[2:].strip()
        if not cmd or cmd.startswith("#"):
            continue
        if cmd.startswith("git archive"):
            kind = "archive"
        elif cmd.startswith("git cat-file"):
            kind = "cat-file"
        else:
            kind = "shell"
        recipes.append(Recipe(kind=kind, command=cmd, name=kind, line=lineno, path=source))
    return recipes
