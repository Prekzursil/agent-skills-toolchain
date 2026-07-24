#!/usr/bin/env python
"""cmd-rewrite/compress-output.py — PostToolUse hook: compress known-noisy Bash output.

WHY
===
Some Bash commands produce enormous output that floods Claude's context window
without adding proportional signal:
  • `git status` in a large repo can list hundreds of untracked files.
  • Build/CI output, test runners, and compiler logs often contain megabytes of
    ANSI-coloured noise.
  • Browser tools (Playwright / claude-in-chrome / chrome-devtools) return
    multi-MB base64 screenshots — the #2 lifetime context consumer after Bash.

This hook fires AFTER the Bash tool OR a browser tool executes (PostToolUse) and
compresses the tool response when it matches a known-noisy pattern (and, for the
Bash rail, exceeds a size threshold). All other output passes through unchanged.

NARROW SCOPE — ONLY SAFE COMPRESSIONS
=======================================
We apply the following transformations, each gated by explicit pattern + size:

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

  3. screenshot-drop  (browser tools: mcp__playwright__*, mcp__claude-in-chrome__*,
     mcp__chrome-devtools__*)
     Base64 image blobs (data:image/…;base64,… URIs AND MCP "data":"…" image
     content) whose DECODED size ≥ IMG_MIN_BYTES are written to
     %TEMP%/screenshot_<sha1>.png and replaced with a
     "[screenshot dropped: N KB, saved to <path>]" placeholder.  Small,
     element-scoped images pass through untouched.  Runs regardless of total
     output size (a small JSON envelope can still wrap a big image).  Fail-open
     per blob: any decode/write error leaves that blob unchanged.

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
    tool_name     str        — "Bash" OR a browser tool (mcp__playwright__*,
                               mcp__claude-in-chrome__*, mcp__chrome-devtools__*),
                               scoped by the settings.json matcher.
    tool_input    dict       — {"command": "<shell command string>"} (Bash rail)
    tool_response str | dict — {"type":"text","text":"..."} or raw str

Stdout (on compression):
    JSON: {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                   "updatedToolOutput": "<compressed text>"}}

Stdout (no change): nothing — exit 0.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sys
import tempfile

# ── Configuration ─────────────────────────────────────────────────────────────

# Only compress if output exceeds this many characters (Bash rail).
SIZE_THRESHOLD: int = int(os.environ.get("COMPRESS_SIZE_THRESHOLD", "4000"))

# Show at most this many file paths per category in git-status summary.
MAX_SHOW_PATHS: int = 10

# Browser-rail tools whose results can wrap multi-MB base64 screenshots — the #2
# lifetime context consumer after Bash. The settings.json matcher routes them here
# so oversized images can be dropped to a temp file instead of flooding context.
_BROWSER_PREFIXES: tuple[str, ...] = (
    "mcp__playwright__",
    "mcp__claude-in-chrome__",
    "mcp__chrome-devtools__",
)

# Drop a base64 image blob only if its DECODED size is at least this many bytes;
# small, element-scoped screenshots pass through untouched.
IMG_MIN_BYTES: int = int(os.environ.get("COMPRESS_IMG_MIN_BYTES", "40000"))

# Regex to detect ANSI escape sequences (CSI + OSC variants).
_ANSI_RE = re.compile(
    r"\x1b(?:"
    r"\[[0-9;?]*[ -/]*[@-~]"  # CSI sequences (colour, cursor, etc.)
    r"|"
    r"\][^\x1b\x07]*(?:\x07|\x1b\\)"  # OSC sequences
    r"|"
    r"[()][AB012]"  # character-set designations
    r"|"
    r"[A-Z\\^_@]"  # other Fe sequences
    r")"
)

# Base64 image blobs, two shapes:
#   (A) data-URI:  data:image/png;base64,<b64>   (HTML / markdown embeds)
#   (B) MCP image content field:  "data": "<b64>"  (raw base64, no data: prefix)
# The MCP form requires a long value so ordinary short "data" fields are ignored;
# every candidate is still decoded and size-checked before it is dropped.
_DATA_URI_RE = re.compile(r"data:image/[A-Za-z0-9.+-]+;base64,([A-Za-z0-9+/=]+)")
_MCP_DATA_RE = re.compile(r'"data"\s*:\s*"([A-Za-z0-9+/=]{100,})"')


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


# ── Screenshot dropper (browser rail) ─────────────────────────────────────────


def _screenshot_dir() -> str:
    """Directory for dropped screenshots: %TEMP% on Windows, else the OS temp dir."""
    return os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir()


def _drop_large_images(text: str) -> tuple[str, int]:
    """Replace oversized base64 image blobs with a saved-to-disk placeholder.

    Scans *text* for the two base64 image shapes (data-URI and MCP "data" field).
    For each blob whose DECODED size is >= IMG_MIN_BYTES, the bytes are written to
    %TEMP%/screenshot_<sha1[:12]>.png and the blob is replaced with
    "[screenshot dropped: <KB> KB, saved to <path>]".  Small (element-scoped)
    images pass through untouched.  Fail-open per blob: any decode/write error
    keeps that blob exactly as it was.

    Returns (new_text, dropped_count).
    """
    dropped = 0

    def _sub(match: re.Match, wrap) -> str:
        nonlocal dropped
        b64 = match.group(1)
        try:
            raw = base64.b64decode(b64, validate=False)
        except Exception:
            return match.group(0)  # not decodable -> keep original
        if len(raw) < IMG_MIN_BYTES:
            return match.group(0)  # small / element-scoped -> untouched
        try:
            digest = hashlib.sha1(raw).hexdigest()[:12]
            path = os.path.join(_screenshot_dir(), f"screenshot_{digest}.png")
            with open(path, "wb") as fh:
                fh.write(raw)
        except Exception:
            return match.group(0)  # cannot persist -> keep original
        dropped += 1
        return wrap(f"[screenshot dropped: {len(raw) // 1024} KB, saved to {path}]")

    # (A) data-URI blobs — replace the whole URI with the placeholder.
    text = _DATA_URI_RE.sub(lambda m: _sub(m, lambda p: p), text)
    # (B) MCP "data" fields — keep the JSON key so surrounding structure survives.
    text = _MCP_DATA_RE.sub(lambda m: _sub(m, lambda p: f'"data":"{p}"'), text)
    return text, dropped


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
_BRANCH_LINE_RE = re.compile(
    r"^(?:On branch|HEAD detached|rebase in progress).*", re.MULTILINE
)
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
        if re.match(r"Changes to be committed", stripped):
            current_section = "staged"
            continue
        if re.match(r"Changes not staged for commit", stripped):
            current_section = "modified"
            continue
        if re.match(r"Untracked files:", stripped):
            current_section = "untracked"
            continue
        if re.match(
            r"^(\t| {2,})(new file:|modified:|deleted:|renamed:|copied:)\s+", stripped
        ):
            if current_section:
                # extract path part after the label
                m = re.match(
                    r"^(?:\t| {2,})(?:new file:|modified:|deleted:|renamed:|copied:)\s+(.*)",
                    stripped,
                )
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

    for label, key in [
        ("Staged", "staged"),
        ("Modified", "modified"),
        ("Untracked", "untracked"),
    ]:
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


def _emit(text: str) -> None:
    """Write the PostToolUse updatedToolOutput envelope to stdout."""
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "updatedToolOutput": text,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    sys.stdout.flush()


def main() -> int:
    try:
        raw = sys.stdin.read() or "{}"
        data = json.loads(raw)
    except Exception:
        return 0  # fail-open: malformed JSON → passthrough

    try:
        tool_name = data.get("tool_name") or ""
        is_browser = tool_name.startswith(_BROWSER_PREFIXES)
        if tool_name != "Bash" and not is_browser:
            return 0

        tool_input = data.get("tool_input") or {}
        command = tool_input.get("command", "")
        if not isinstance(command, str):
            command = ""

        tool_response = data.get("tool_response") or data.get("tool_output") or ""
        text = _extract_response_text(tool_response)
        if text is None:
            return 0

        # ── Browser rail: drop oversized base64 screenshots. Runs even on short
        #    text — a small JSON envelope can still wrap a multi-MB image. ──
        if is_browser:
            new_text, dropped = _drop_large_images(text)
            if dropped:
                _emit(new_text)
            return 0

        # ── Bash rail: git-status summary + ANSI strip, size-gated. ──
        if len(text) <= SIZE_THRESHOLD:
            return 0  # output is short — passthrough

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
        if (
            not did_compress
            and _ANSI_RE.search(compressed)
            and len(compressed) > SIZE_THRESHOLD
        ):
            stripped = _strip_ansi(compressed)
            if len(stripped) < len(compressed):
                compressed = stripped
                did_compress = True

        if not did_compress:
            return 0  # nothing changed — silent exit

        _emit(compressed)

    except Exception:
        pass  # fail-open: any logic error → exit 0, do nothing

    return 0


if __name__ == "__main__":
    sys.exit(main())
