#!/usr/bin/env python3
r"""background-digest/reader.py - SessionStart SURFACE for the ANTICIPATORY layer.

Folded into _dispatch/manifest.json (NOT a separate settings.json hook, so it does
not add a 2nd raw SessionStart surface and does not touch the ~6-hook ceiling). This
is the SURFACE half of the "background dreaming" layer: the scheduled-task PRODUCERS
(resource-guard.ps1, world-watch.ps1, ...) append dated lines to a digest file; at
SessionStart this reader surfaces the oldest K pending entries ONCE as
"while you were away I noticed / prepared X", then TRUNCATES the consumed entries
(archiving them first, so a consumed line is never lost).

DIGEST FILE   ~/.claude/BACKGROUND-DIGEST.md            (override: BG_DIGEST_FILE)
  An append-only queue. An ENTRY is any line beginning with a date bracket
  '[YYYY-MM-DD'. Everything else (a markdown header, blank lines, '#'/'<!--' notes)
  is PRESERVED untouched and is never surfaced or consumed. Producers append:
     [2026-06-29 14:03:11] [resource-guard] <what changed>  | PROPOSE: <command>
  LOG + SURFACE ONLY - each entry carries a PROPOSED command; the agent/user runs it
  (mirrors the mcp-drift-audit doctrine: never auto-act destructively).

ARCHIVE FILE  ~/.claude/BACKGROUND-DIGEST.archive.log   (override: BG_DIGEST_ARCHIVE)
  Consumed entries are appended here BEFORE the live file is truncated (audit trail +
  loss-proof), rotated to the last BG_DIGEST_ARCHIVE_MAX lines.

Dispatcher interface: main(argv) reads the SessionStart payload on stdin and prints ONE
hookSpecificOutput JSON (or nothing). FAIL-OPEN at every level. Opt-out: BG_DIGEST=off
(or 0/false) or a .disabled file in this dir.

SUBAGENT GUARD: a Task subagent's SessionStart ALSO runs this dispatcher; surfacing +
consuming there injects the digest into the subagent's context and truncates it from the
live file, STEALING the "while you were away" notice from the user's MAIN session. So we
skip when the payload's transcript_path is a subagent transcript
(.../subagents/agent-<id>.jsonl). (open-loops/resurface never hit this because it does not
CONSUME; any consume-on-SessionStart check MUST guard against subagents.)

LOSS-PROOF / surface-once: consumed entries are archived BEFORE truncation, and the live
file is truncated ONLY if the archive write succeeded (else the entries stay put and
re-surface next session - a harmless duplicate, never a silent loss). Truncation removes
the consumed lines from a FRESH re-read (matched by exact text, first occurrence each), so
a producer append landing between the initial read and the rewrite is preserved. The
residual race - an append in the sub-ms window between the fresh re-read and the atomic
os.replace - can drop that one not-yet-surfaced line (which is NOT in the archive, as it
was never surfaced); accepted because producers fire hourly/daily so the window is
effectively never hit.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"
HOME = Path.home()

DIGEST_FILE = Path(
    os.environ.get("BG_DIGEST_FILE", str(HOME / ".claude" / "BACKGROUND-DIGEST.md"))
)
ARCHIVE_FILE = Path(
    os.environ.get(
        "BG_DIGEST_ARCHIVE", str(HOME / ".claude" / "BACKGROUND-DIGEST.archive.log")
    )
)
MAX_SURFACE = int(os.environ.get("BG_DIGEST_MAX", "12"))
ARCHIVE_MAX = int(os.environ.get("BG_DIGEST_ARCHIVE_MAX", "500"))

# An ENTRY line begins with a date bracket: [YYYY-MM-DD ...]. Anything else is a
# header / blank / note and is preserved (never surfaced or truncated).
_ENTRY_RE = re.compile(r"^\[\d{4}-\d{2}-\d{2}")


def _disabled() -> bool:
    try:
        if DISABLED.exists():
            return True
    except Exception:
        pass
    return os.environ.get("BG_DIGEST", "").lower() in ("off", "0", "false")


def emit(event_name: str, msg: str) -> None:
    """Inject additionalContext (the shared hookSpecificOutput shape)."""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": msg,
                }
            }
        )
    )


def _read_lines(path: Path) -> list[str]:
    try:
        if not path.exists():
            return []
        # utf-8-sig: strip an optional BOM (Windows PowerShell 5.1 Add-Content -Encoding utf8
        # writes one when CREATING a file) so a BOM-prefixed first entry still matches _ENTRY_RE.
        return path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except Exception:
        return []


def _is_subagent(payload: dict) -> bool:
    """True when this SessionStart is for a Task subagent (transcript under .../subagents/
    agent-<id>.jsonl). We must NOT surface/consume there or the user's main session loses
    the notice. Unknown/empty transcript -> treat as main (safe default: surface)."""
    try:
        tp = (
            str((payload or {}).get("transcript_path") or "").replace("\\", "/").lower()
        )
        if not tp:
            return False
        return "/subagents/" in tp or Path(tp).name.startswith("agent-")
    except Exception:
        return False


def _is_entry(line: str) -> bool:
    return bool(_ENTRY_RE.match(line.strip()))


def _atomic_write(path: Path, lines: list[str]) -> None:
    """Rewrite the whole file atomically (temp + os.replace) so an abandoned thread
    or a crash can never leave a half-written digest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    text = ("\n".join(lines) + "\n") if lines else ""
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def build_message(lines: list[str]) -> tuple[str | None, list[str]]:
    """PURE: given the digest's current lines, return (message_or_None, surfaced_entries).

    Surfaces the oldest MAX_SURFACE entries (FIFO so nothing starves); any overflow is
    noted and left for the next session."""
    entries = [ln for ln in lines if _is_entry(ln)]
    if not entries:
        return None, []
    surfaced = entries[:MAX_SURFACE]
    overflow = len(entries) - len(surfaced)
    header = "## While you were away (background digest - surfaced once)"
    body = list(surfaced)
    if overflow > 0:
        body.append(
            f"...(+{overflow} more pending in {DIGEST_FILE.name}; will surface next session)"
        )
    footer = (
        "Each line is LOG + PROPOSE only - run the proposed command yourself if it "
        f"still applies. Consumed history: {ARCHIVE_FILE.name}"
    )
    return "\n".join([header, *body, footer]), surfaced


def _archive(consumed: list[str]) -> bool:
    """Append consumed entries to the archive (loss-proof), rotate to ARCHIVE_MAX.

    Returns True only if the entries were durably written; the caller must NOT truncate the
    live file on False (the entries then re-surface next session - a harmless duplicate,
    never a silent loss)."""
    if not consumed:
        return True
    try:
        ARCHIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with ARCHIVE_FILE.open("a", encoding="utf-8", errors="replace") as fh:
            for ln in consumed:
                fh.write(ln + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        existing = _read_lines(ARCHIVE_FILE)
        if len(existing) > ARCHIVE_MAX:
            _atomic_write(ARCHIVE_FILE, existing[-ARCHIVE_MAX:])
        return True
    except Exception:
        return False


def _truncate_consumed(consumed: list[str]) -> None:
    """Remove exactly the consumed entry lines (first occurrence each) from a FRESH
    read of the digest, preserving everything else (headers + concurrent appends)."""
    if not consumed:
        return
    try:
        fresh = _read_lines(DIGEST_FILE)
        if not fresh:
            return
        remaining = Counter(consumed)
        keep: list[str] = []
        for ln in fresh:
            if remaining.get(ln, 0) > 0:
                remaining[ln] -= 1
                continue
            keep.append(ln)
        _atomic_write(DIGEST_FILE, keep)
    except Exception:
        pass


def main(argv=None) -> int:
    try:
        if _disabled():
            return 0
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except Exception:
            payload = {}
        # Reserve the digest for the user's MAIN session - never consume it in a subagent.
        if _is_subagent(payload):
            return 0
        msg, surfaced = build_message(_read_lines(DIGEST_FILE))
        if msg:
            emit("SessionStart", msg)  # surface FIRST (write to the buffer)
            if _archive(surfaced):  # preserve; truncate ONLY if archived
                _truncate_consumed(surfaced)
            # archive failed -> leave entries in the live file (re-surface next session)
    except Exception:
        pass  # fail-open: never crash a session
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
