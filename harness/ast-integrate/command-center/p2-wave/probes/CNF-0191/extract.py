"""Extract documented shell commands from markdown (fenced blocks).

Use-vs-mention: fences under 'what not to do' / 'removed in v2' headings, or
marked NOT-EXECUTABLE / noexec, are skipped. Prompted `$ ` / `PS>` lines are
commands; following non-prompt lines in the same fence are documented output.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

SKIP_LANGS = {
    "json",
    "jsonc",
    "yaml",
    "yml",
    "python",
    "py",
    "javascript",
    "js",
    "typescript",
    "ts",
    "html",
    "xml",
    "mermaid",
    "diff",
    "toml",
    "ini",
    "css",
    "go",
    "rust",
    "java",
}
# Prompted `$ `/`PS>` lines are accepted in these fences (incl. empty/`text`).
SHELL_LANGS = {
    "",
    "bash",
    "sh",
    "shell",
    "console",
    "terminal",
    "powershell",
    "pwsh",
    "cmd",
    "bat",
    "zsh",
    "fish",
    "text",
}
# Unprompted fences with empty/`text` lang are usually directory trees, not
# commands. Only explicit shell langs are executed as recipes.
EXPLICIT_SHELL_LANGS = {
    "bash",
    "sh",
    "shell",
    "console",
    "terminal",
    "powershell",
    "pwsh",
    "cmd",
    "bat",
    "zsh",
    "fish",
}
MENTION_HEADING = re.compile(
    r"what not to do|removed in v2|do not run|do not execute|"
    r"not[- ]executable|example of what not",
    re.I,
)
NOEXEC_MARK = re.compile(r"not[- ]executable|noexec", re.I)
PROMPT = re.compile(r"^(?:PS>|\$)\s+(.*)$")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass
class Extracted:
    path: str
    line: int
    command: str
    documented_output: str
    fence_lang: str
    skipped: bool = False
    skip_reason: str | None = None


def _info_lang(info: str) -> str:
    token = (info or "").strip().split()[0] if (info or "").strip() else ""
    return token.lower().lstrip(".")


def _should_skip_fence(info: str, heading: str, prelude: str) -> str | None:
    lang = _info_lang(info)
    if lang in SKIP_LANGS:
        return f"non-shell-fence:{lang or 'empty'}"
    if lang not in SHELL_LANGS:
        return f"non-shell-fence:{lang}"
    if NOEXEC_MARK.search(info or ""):
        return "fence-marked-noexec"
    if MENTION_HEADING.search(heading or ""):
        return f"mention-heading:{heading.strip()[:80]}"
    if NOEXEC_MARK.search(prelude or ""):
        return "prelude-noexec"
    return None


def extract_markdown(text: str, rel_path: str) -> list[Extracted]:
    """Return live commands and skipped mentions, in document order."""
    lines = text.splitlines()
    out: list[Extracted] = []
    heading = ""
    i = 0
    n = len(lines)
    while i < n:
        raw = lines[i]
        hm = HEADING.match(raw.strip())
        if hm:
            heading = hm.group(2)
            i += 1
            continue
        stripped = raw.lstrip()
        if stripped.startswith("```"):
            info = stripped[3:].strip()
            fence_line = i + 1
            prelude = "\n".join(lines[max(0, i - 3) : i])
            body: list[tuple[int, str]] = []
            i += 1
            while i < n and not lines[i].lstrip().startswith("```"):
                body.append((i + 1, lines[i]))
                i += 1
            skip = _should_skip_fence(info, heading, prelude)
            lang = _info_lang(info)
            prompted = [(ln, PROMPT.match(s.rstrip())) for ln, s in body]
            has_prompt = any(m for _, m in prompted)
            if skip:
                if has_prompt:
                    for ln, m in prompted:
                        if m:
                            out.append(
                                Extracted(
                                    path=rel_path,
                                    line=ln,
                                    command=m.group(1).strip(),
                                    documented_output="",
                                    fence_lang=lang,
                                    skipped=True,
                                    skip_reason=skip,
                                )
                            )
                i += 1
                continue
            if has_prompt:
                current: Extracted | None = None
                output_lines: list[str] = []
                for ln, src in body:
                    m = PROMPT.match(src.rstrip())
                    if m:
                        if current is not None:
                            current.documented_output = "\n".join(output_lines).rstrip(
                                "\n"
                            )
                            out.append(current)
                        current = Extracted(
                            path=rel_path,
                            line=ln,
                            command=m.group(1).strip(),
                            documented_output="",
                            fence_lang=lang,
                        )
                        output_lines = []
                    elif current is not None:
                        if src.strip().startswith("#"):
                            continue
                        output_lines.append(src)
                if current is not None:
                    current.documented_output = "\n".join(output_lines).rstrip("\n")
                    out.append(current)
            elif lang not in EXPLICIT_SHELL_LANGS:
                # Empty/`text` unprompted fence: directory listing, not a recipe.
                if i < n and lines[i].lstrip().startswith("```"):
                    i += 1
                continue
            else:
                # Unprompted shell fence: join backslash continuations as one command.
                buf: list[str] = []
                start_ln = fence_line + 1
                for ln, src in body:
                    s = src.rstrip()
                    if not s or s.lstrip().startswith("#"):
                        continue
                    if not buf:
                        start_ln = ln
                    if s.endswith("\\"):
                        buf.append(s[:-1].rstrip())
                    else:
                        buf.append(s)
                        cmd = " ".join(buf).strip()
                        if cmd:
                            out.append(
                                Extracted(
                                    path=rel_path,
                                    line=start_ln,
                                    command=cmd,
                                    documented_output="",
                                    fence_lang=lang,
                                )
                            )
                        buf = []
                if buf:
                    cmd = " ".join(buf).strip()
                    if cmd:
                        out.append(
                            Extracted(
                                path=rel_path,
                                line=start_ln,
                                command=cmd,
                                documented_output="",
                                fence_lang=lang,
                            )
                        )
            if i < n and lines[i].lstrip().startswith("```"):
                i += 1
            continue
        i += 1
    return out


def extract_file(path: Path, rel_path: str) -> list[Extracted]:
    text = path.read_text(encoding="utf-8")
    return extract_markdown(text, rel_path)


def live_only(rows: list[Extracted]) -> list[Extracted]:
    return [r for r in rows if not r.skipped]


def skipped_only(rows: list[Extracted]) -> list[Extracted]:
    return [r for r in rows if r.skipped]
