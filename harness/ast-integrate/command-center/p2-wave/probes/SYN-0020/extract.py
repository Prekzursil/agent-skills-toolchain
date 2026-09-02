"""Extract fenced shell commands from markdown; skip noexec/illustrative blocks."""

from __future__ import annotations

import re
from pathlib import Path

from contract import NOEXEC_TOKENS

FENCE_OPEN = re.compile(r"^(\s*)(`{3,}|~{3,})([^\n]*)$")
HTML_NOEXEC = re.compile(
    r"<!--\s*(noexec|not-executable|illustrative)\s*-->", re.I
)
SHELLISH = frozenset(
    {
        "",
        "bash",
        "sh",
        "shell",
        "zsh",
        "console",
        "terminal",
        "text",
        "powershell",
        "pwsh",
        "cmd",
        "bat",
    }
)
PROMPT_RE = re.compile(r"^\s*(?:\$|>{1,3}|PS>)\s+")


def _info_tokens(info: str) -> list[str]:
    raw = (info or "").strip().lower()
    if not raw:
        return []
    return [t for t in re.split(r"[\s,{}\[\]]+", raw) if t]


def is_noexec_info(info: str) -> bool:
    tokens = set(_info_tokens(info))
    return bool(tokens & NOEXEC_TOKENS)


def language_of(info: str) -> str:
    tokens = _info_tokens(info)
    if not tokens:
        return ""
    for t in tokens:
        if t not in NOEXEC_TOKENS:
            return t
    return ""


def iter_fences(text: str) -> list[dict]:
    lines = text.splitlines()
    out: list[dict] = []
    i = 0
    prev_nonblank = ""
    while i < len(lines):
        line = lines[i]
        m = FENCE_OPEN.match(line)
        if not m:
            if line.strip():
                prev_nonblank = line
            i += 1
            continue
        marker = m.group(2)
        info = m.group(3).strip()
        start = i + 1
        i += 1
        body_lines: list[str] = []
        close = re.compile(r"^\s*" + re.escape(marker) + r"\s*$")
        while i < len(lines) and not close.match(lines[i]):
            body_lines.append(lines[i])
            i += 1
        if i < len(lines):
            i += 1
        skipped = is_noexec_info(info) or bool(HTML_NOEXEC.search(prev_nonblank))
        reason = None
        if is_noexec_info(info):
            reason = "fence-info-noexec"
        elif HTML_NOEXEC.search(prev_nonblank):
            reason = "html-comment-noexec"
        out.append(
            {
                "start_line": start,
                "info": info,
                "language": language_of(info),
                "body": "\n".join(body_lines),
                "skipped": skipped,
                "skip_reason": reason,
            }
        )
        prev_nonblank = ""
    return out


def _command_lines(body: str, language: str) -> list[tuple[int, str]]:
    """Return (offset_in_fence, invocation) pairs."""
    rows: list[tuple[int, str]] = []
    pending = ""
    pending_off = 0
    for off, raw in enumerate(body.splitlines(), start=0):
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if language in {"console", "terminal"} or stripped.startswith("$ "):
            if not PROMPT_RE.match(line) and not stripped.startswith("$"):
                continue
        cmd = PROMPT_RE.sub("", line).strip()
        if not cmd or cmd.startswith("#"):
            continue
        if cmd == "..." or cmd.startswith("..."):
            continue
        if pending:
            cmd = pending + cmd
            off_use = pending_off
            pending = ""
        else:
            off_use = off
        if cmd.endswith("\\"):
            pending = cmd[:-1]
            pending_off = off_use
            continue
        rows.append((off_use, cmd))
    return rows


def extract_path(path: Path, repo: Path) -> dict:
    rel = path.relative_to(repo).as_posix() if path.is_relative_to(repo) else str(path)
    text = path.read_text(encoding="utf-8")
    commands: list[dict] = []
    skipped: list[dict] = []
    for fence in iter_fences(text):
        lang = fence["language"]
        if lang not in SHELLISH:
            continue
        for off, inv in _command_lines(fence["body"], lang):
            rec = {
                "path": rel,
                "line": fence["start_line"] + off,
                "invocation": inv,
                "fence_info": fence["info"],
                "executable": not fence["skipped"],
                "skip_reason": fence["skip_reason"],
            }
            if fence["skipped"]:
                skipped.append(rec)
            else:
                commands.append(rec)
    return {"path": rel, "commands": commands, "skipped": skipped}


def extract_many(paths: list[Path], repo: Path) -> dict:
    commands: list[dict] = []
    skipped: list[dict] = []
    seen: list[str] = []
    for path in paths:
        if not path.is_file():
            continue
        rel = path.relative_to(repo).as_posix() if path.is_relative_to(repo) else str(path)
        seen.append(rel)
        got = extract_path(path, repo)
        commands.extend(got["commands"])
        skipped.extend(got["skipped"])
    return {
        "docs": seen,
        "commands": commands,
        "skipped": skipped,
        "command_count": len(commands),
        "skipped_count": len(skipped),
    }
