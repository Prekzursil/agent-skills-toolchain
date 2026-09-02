"""Extract fenced shell commands from Markdown documentation.

A fence is a command only when its language is a shell/console family, or
when the fence is unlabeled and the body looks like a shell invocation.
Python/JSON/etc. fences are mention, not use.

Exclusion from execution requires an explicit NOT-EXECUTABLE (or noexec)
marker in the info string, the preceding source line, or the first body
line. The runner may not invent a skip.
"""
from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any

COMMAND_LANGS = frozenset(
    {
        "bash",
        "sh",
        "shell",
        "zsh",
        "fish",
        "ksh",
        "console",
        "terminal",
        "shell-session",
        "console-session",
        "powershell",
        "pwsh",
        "ps1",
        "cmd",
        "bat",
        "batch",
    }
)
MARKER_RE = re.compile(r"\bNOT-EXECUTABLE\b|\bnot-executable\b|\bnoexec\b", re.I)
OPEN_RE = re.compile(r"^([ \t]{0,3})(`{3,}|~{3,})(.*)$")
PROMPT_RE = re.compile(r"^\$\s+")
ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# Unlabeled fences are commands only when every extracted line is a real
# shell invocation. Status tables and YAML blobs must not inflate the census.
SHELL_VERBS = frozenset(
    {
        "[",
        "ansible",
        "apt",
        "apt-get",
        "awk",
        "basedpyright",
        "basename",
        "bash",
        "brew",
        "bundle",
        "bun",
        "cargo",
        "cat",
        "cd",
        "chmod",
        "choco",
        "chown",
        "claude",
        "cmake",
        "cmd",
        "codex",
        "conda",
        "cp",
        "curl",
        "date",
        "deno",
        "dirname",
        "docker",
        "docker-compose",
        "dotnet",
        "echo",
        "env",
        "exec",
        "export",
        "false",
        "fd",
        "find",
        "fish",
        "gem",
        "gh",
        "git",
        "git-crypt",
        "go",
        "gpg",
        "grep",
        "gzip",
        "head",
        "http",
        "install",
        "java",
        "javac",
        "jq",
        "kill",
        "ksh",
        "kubectl",
        "ln",
        "ls",
        "make",
        "mamba",
        "mkdir",
        "mv",
        "mvn",
        "mypy",
        "ninja",
        "node",
        "npm",
        "npx",
        "openssl",
        "pacman",
        "pip",
        "pip3",
        "pipx",
        "pnpm",
        "podman",
        "poetry",
        "powershell",
        "printf",
        "pwsh",
        "pwd",
        "py",
        "pytest",
        "python",
        "python3",
        "rg",
        "rm",
        "rmdir",
        "ruby",
        "ruff",
        "scp",
        "sed",
        "set",
        "sh",
        "source",
        "ssh",
        "sudo",
        "systemctl",
        "tail",
        "tar",
        "terraform",
        "test",
        "touch",
        "tox",
        "true",
        "uname",
        "unset",
        "unzip",
        "uv",
        "uvx",
        "wc",
        "wget",
        "whoami",
        "winget",
        "xargs",
        "yarn",
        "zip",
        "zsh",
    }
)


def _is_closer(line: str, tick: str, n: int) -> bool:
    stripped = line.strip()
    if not stripped or set(stripped) != {tick}:
        return False
    return len(stripped) >= n


def _lang_of(info: str) -> str:
    token = (info or "").strip().split()
    if not token:
        return ""
    return token[0].lower().lstrip(".")


def _has_marker(info: str, prev_line: str, body: str) -> bool:
    first = ""
    for line in body.splitlines():
        if line.strip():
            first = line
            break
    return bool(
        MARKER_RE.search(info or "")
        or MARKER_RE.search(prev_line or "")
        or MARKER_RE.search(first)
    )


def _commands_from_body(lang: str, body: str) -> list[str]:
    lines = body.splitlines()
    prompted = [ln for ln in lines if PROMPT_RE.match(ln.lstrip())]
    if prompted or lang in {"console", "terminal", "shell-session", "console-session"}:
        out: list[str] = []
        for ln in lines:
            raw = ln.lstrip()
            if PROMPT_RE.match(raw):
                cmd = PROMPT_RE.sub("", raw, count=1).strip()
                if cmd and not cmd.startswith("#"):
                    out.append(cmd)
        return out
    joined: list[str] = []
    buf = ""
    for ln in lines:
        s = ln.rstrip()
        if not s.strip() or s.strip().startswith("#"):
            if buf.endswith("\\"):
                buf = buf[:-1] + " "
            continue
        if buf.endswith("\\"):
            buf = buf[:-1] + " " + s.lstrip()
            continue
        if buf:
            joined.append(buf.strip())
        buf = s
    if buf.strip():
        joined.append(buf.strip())
    return [c for c in joined if c]


def _first_token(command: str) -> str:
    try:
        parts = shlex.split(command, posix=True)
    except ValueError:
        parts = command.split()
    for part in parts:
        if ENV_ASSIGN_RE.match(part):
            continue
        name = Path(part).name.lower()
        if name.endswith(".exe"):
            name = name[:-4]
        if not name or name.startswith("-"):
            continue
        return name
    return ""


def _is_shell_command(command: str) -> bool:
    raw = (command or "").strip()
    if not raw or raw.startswith("#"):
        return False
    if PROMPT_RE.match(raw):
        return True
    return _first_token(raw) in SHELL_VERBS


def _looks_like_shell(commands: list[str]) -> bool:
    if not commands:
        return False
    return all(_is_shell_command(c) for c in commands)


def extract_text(text: str, rel_path: str) -> list[dict[str, Any]]:
    """Return command rows for one document (LF-normalized)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.splitlines()
    rows: list[dict[str, Any]] = []
    i = 0
    prev_nonempty = ""
    seq = 0
    while i < len(lines):
        m = OPEN_RE.match(lines[i])
        if not m:
            if lines[i].strip():
                prev_nonempty = lines[i]
            i += 1
            continue
        tick = m.group(2)[0]
        n = len(m.group(2))
        info = m.group(3).strip()
        start_line = i + 1  # 1-indexed fence opener
        j = i + 1
        body_lines: list[str] = []
        found = False
        while j < len(lines):
            if _is_closer(lines[j], tick, n):
                found = True
                break
            body_lines.append(lines[j])
            j += 1
        if not found:
            i += 1
            continue
        body = "\n".join(body_lines)
        lang = _lang_of(info)
        cmds = _commands_from_body(lang, body)
        is_command_fence = lang in COMMAND_LANGS or (
            lang == "" and _looks_like_shell(cmds)
        )
        if is_command_fence:
            marked = _has_marker(info, prev_nonempty, body)
            if not cmds:
                seq += 1
                rows.append(
                    {
                        "id": f"{rel_path}:{start_line}:{seq}",
                        "path": rel_path,
                        "line": start_line,
                        "lang": lang or "unlabeled",
                        "info": info,
                        "command": "",
                        "marked_not_executable": marked,
                        "empty_fence": True,
                    }
                )
            else:
                for cmd in cmds:
                    seq += 1
                    rows.append(
                        {
                            "id": f"{rel_path}:{start_line}:{seq}",
                            "path": rel_path,
                            "line": start_line,
                            "lang": lang or "unlabeled",
                            "info": info,
                            "command": cmd,
                            "marked_not_executable": marked,
                            "empty_fence": False,
                        }
                    )
        if lines[j].strip():
            prev_nonempty = lines[j]
        i = j + 1
    return rows


def extract_file(path: Path, rel_path: str) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    return extract_text(text, rel_path)


def naive_unlabeled_only(text: str, rel_path: str) -> list[dict[str, Any]]:
    """Broken extractor: ignores language-tagged fences. Detector control."""
    rows = extract_text(text, rel_path)
    return [r for r in rows if r.get("lang") == "unlabeled"]
