#!/usr/bin/env python
"""cmd-rewrite/compress-output.py — PostToolUse hook: compress known-noisy Bash output.

WHY
===
Some Bash commands produce enormous output that floods Claude's context window
without adding proportional signal:
  • `git status` in a large repo can list hundreds of untracked files.
  • Build/CI output, test runners, and compiler logs often contain megabytes of
    ANSI-coloured noise.

This hook fires AFTER the Bash tool executes (PostToolUse) and compresses the
tool response when it matches a known-noisy pattern AND exceeds a size threshold.
All other output passes through unchanged.

NARROW SCOPE — ONLY SAFE COMPRESSIONS
=======================================
We apply exactly two transformations, each gated by explicit pattern + size:

  1. git-status-summary  (command matches /\\bgit\\s+status\\b/)
     If output length > SIZE_THRESHOLD, keep:
       - The branch/tracking lines (top)
       - Staged/modified/untracked COUNTS + first MAX_SHOW_PATHS paths each
       - A clear "[truncated — N more paths not shown]" footer
     Output format is unchanged for the shown paths (no porcelain injection).

  2. ansi-strip  (any long output with ANSI sequences)
     If output length > SIZE_THRESHOLD AND contains ANSI escape codes,
     strip escape sequences.  This reduces token count without losing content.
     Applied AFTER git-status processing (so git-status summary is also clean).

HONEST CAVEATS
==============
  • This fires AFTER the tool completes (PostToolUse).  It is a context-budget
    optimiser, NOT a gate — it cannot prevent the command from running.
  • It does NOT redact secrets: the original output is captured in the OTel
    trace / transcript.  Do not rely on this hook for security purposes.
  • We only act when output exceeds SIZE_THRESHOLD (default 4000 chars).
    Short outputs are never modified.

FAIL-OPEN CONTRACT
==================
Any error exits 0 with no output.  The original tool response is then used
unchanged by Claude Code.

Stdin (PostToolUse JSON):
    session_id    str
    tool_name     str        — always "Bash" (enforced by matcher)
    tool_input    dict       — {"command": "<shell command string>"}
    tool_response str | dict — {"type":"text","text":"..."} or raw str

Stdout (on compression):
    JSON: {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                   "updatedToolOutput": "<compressed text>"}}

Stdout (no change): nothing — exit 0.
"""
from __future__ import annotations

import json
import re
import sys

# ── Configuration ─────────────────────────────────────────────────────────────

# Only compress if output exceeds this many characters.
SIZE_THRESHOLD: int = int(__import__("os").environ.get("COMPRESS_SIZE_THRESHOLD", "4000"))

# Show at most this many file paths per category in git-status summary.
MAX_SHOW_PATHS: int = 10

# Regex to detect ANSI escape sequences (CSI + OSC variants).
_ANSI_RE = re.compile(
    r"\x1b(?:"
    r"\[[0-9;?]*[ -/]*[@-~]"   # CSI sequences (colour, cursor, etc.)
    r"|"
    r"\][^\x1b\x07]*(?:\x07|\x1b\\)"  # OSC sequences
    r"|"
    r"[()][AB012]"             # character-set designations
    r"|"
    r"[A-Z\\^_@]"              # other Fe sequences
    r")"
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _extract_response_text(tool_response) -> str | None:
    """Extract the text content from tool_response (str or dict)."""
    if isinstance(tool_response, str):
        return tool_response
    if isinstance(tool_response, dict):
        # Common shapes: {"type":"text","text":"..."} or {"output":"..."}
        for key in ("text", "output", "content", "result"):
            val = tool_response.get(key)
            if isinstance(val, str):
                return val
        # Last resort: JSON-encode the whole dict
        try:
            return json.dumps(tool_response, ensure_ascii=False)
        except Exception:
            return None
    return None


# ── Git-status summariser ─────────────────────────────────────────────────────

# Patterns for git-status porcelain v1 / human output
_STATUS_STAGED_RE = re.compile(
    r"^(?:Changes to be committed|new file:|modified:|deleted:|renamed:|copied:)",
    re.MULTILINE,
)
_STATUS_MODIFIED_RE = re.compile(
    r"^(?:Changes not staged for commit|modified:|deleted:)",
    re.MULTILINE,
)
_STATUS_UNTRACKED_RE = re.compile(r"^\tUntracked files:", re.MULTILINE)

# Matches a single path line under a git-status section (indented by \t or spaces)
_PATH_LINE_RE = re.compile(r"^(\t| {4,})(\S.*)", re.MULTILINE)

# The branch/HEAD line at the top of git status output
_BRANCH_LINE_RE = re.compile(r"^(?:On branch|HEAD detached|rebase in progress).*", re.MULTILINE)
_TRACKING_LINE_RE = re.compile(
    r"^(?:Your branch is|nothing to commit|nothing added|no changes added).*",
    re.MULTILINE,
)


def _summarise_git_status(text: str) -> str:
    """Produce a compact summary of `git status` output."""
    lines = text.splitlines(keepends=True)
    total_lines = len(lines)

    # ── Collect header (branch + tracking) ──
    header_lines: list[str] = []
    for line in lines:
        stripped = line.rstrip()
        if _BRANCH_LINE_RE.match(stripped) or _TRACKING_LINE_RE.match(stripped):
            header_lines.append(stripped)
        elif stripped.startswith("#"):
            # Porcelain v2 / older git
            header_lines.append(stripped)

    # ── Parse sections ──
    sections: dict[str, list[str]] = {
        "staged": [],
        "modified": [],
        "untracked": [],
    }
    # We scan the text looking for the well-known section headers and collect
    # indented file paths after each.
    current_section: str | None = None
    for line in lines:
        stripped = line.rstrip()
        sl = stripped.lstrip()
        if re.match(r"Changes to be committed", stripped):
            current_section = "staged"
            continue
        if re.match(r"Changes not staged for commit", stripped):
            current_section = "modified"
            continue
        if re.match(r"Untracked files:", stripped):
            current_section = "untracked"
            continue
        if re.match(r"^(\t| {2,})(new file:|modified:|deleted:|renamed:|copied:)\s+", stripped):
            if current_section:
                # extract path part after the label
                m = re.match(r"^(?:\t| {2,})(?:new file:|modified:|deleted:|renamed:|copied:)\s+(.*)", stripped)
                if m:
                    sections[current_section].append(m.group(1).strip())
            continue
        if current_section == "untracked" and re.match(r"^(\t| {2,})\S", stripped):
            path = stripped.strip()
            if path and not path.startswith("(use "):
                sections["untracked"].append(path)
            continue
        # A blank line may end a section
        if not stripped:
            if current_section == "untracked":
                current_section = None  # untracked ends at blank line

    # ── Build summary ──
    summary_parts: list[str] = []

    if header_lines:
        summary_parts.append("\n".join(header_lines))

    def _format_section(label: str, paths: list[str]) -> str:
        count = len(paths)
        if count == 0:
            return ""
        shown = paths[:MAX_SHOW_PATHS]
        out = f"\n{label}: {count} file(s)\n"
        for p in shown:
            out += f"  {p}\n"
        if count > MAX_SHOW_PATHS:
            out += f"  ... [{count - MAX_SHOW_PATHS} more not shown]\n"
        return out

    for label, key in [("Staged", "staged"), ("Modified", "modified"), ("Untracked", "untracked")]:
        part = _format_section(label, sections[key])
        if part:
            summary_parts.append(part)

    if not any(sections.values()) and not header_lines:
        # Couldn't parse anything useful — return a char-count note instead
        return (
            f"[git status output: {len(text)} chars / {total_lines} lines — "
            f"could not parse sections; showing first 40 lines]\n"
            + "\n".join(lines[:40])
        )

    total_files = sum(len(v) for v in sections.values())
    summary_parts.append(
        f"\n[Summary: {sections['staged']} staged, "
        f"{len(sections['modified'])} modified, "
        f"{len(sections['untracked'])} untracked "
        f"({total_lines} lines compressed to summary)]"
    )

    return "\n".join(summary_parts)


# ── Main ──────────────────────────────────────────────────────────────────────

def _is_git_status_command(command: str) -> bool:
    """True if *command* is primarily a `git status` invocation."""
    # Match: git [flags] status [flags], possibly in a compound command
    # We only compress if git status is the FIRST (or only) command segment.
    first_seg = re.split(r"&&|;|\|", command)[0].strip()
    return bool(re.search(r"\bgit\b.*\bstatus\b", first_seg))


def main() -> int:
    try:
        raw = sys.stdin.read() or "{}"
        data = json.loads(raw)
    except Exception:
        return 0  # fail-open: malformed JSON → passthrough

    try:
        tool_name = data.get("tool_name", "")
        if tool_name != "Bash":
            return 0

        tool_input = data.get("tool_input") or {}
        command = tool_input.get("command", "")
        if not isinstance(command, str):
            command = ""

        tool_response = data.get("tool_response") or data.get("tool_output") or ""
        text = _extract_response_text(tool_response)
        if text is None:
            return 0

        if len(text) <= SIZE_THRESHOLD:
            return 0  # output is short — passthrough

        # ── Apply transformations ──
        compressed = text
        did_compress = False

        # 1. git-status summarisation
        if _is_git_status_command(command):
            try:
                compressed = _summarise_git_status(_strip_ansi(compressed))
                did_compress = True
            except Exception:
                pass  # fail-open: leave compressed as-is

        # 2. ANSI stripping (applied to whatever we have now, if still large)
        if not did_compress and _ANSI_RE.search(compressed) and len(compressed) > SIZE_THRESHOLD:
            stripped = _strip_ansi(compressed)
            if len(stripped) < len(compressed):
                compressed = stripped
                did_compress = True

        if not did_compress:
            return 0  # nothing changed — silent exit

        out = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "updatedToolOutput": compressed,
            }
        }
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        sys.stdout.flush()

    except Exception:
        pass  # fail-open: any logic error → exit 0, do nothing

    return 0


if __name__ == "__main__":
    sys.exit(main())
