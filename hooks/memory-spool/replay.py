#!/usr/bin/env python3
r"""memory-spool/replay.py -- AUTO-REPLAY spooled basic-memory writes via the CLI.

spool.py persists each write_note/edit_note payload BEFORE the MCP call. flush_check.py
clears the ones the MCP call confirmed and REPORTS the rest -- but a reported entry was
never actually re-attempted, so failed writes rotted on disk (exactly the silent
memory-loss this system exists to prevent, one layer up). This closes that gap.

It re-applies each pending WRITE by shelling to `basic-memory tool write-note`, which
writes the vault DIRECTLY -- no dependency on the flappy MCP HTTP server (the whole point:
the server can be stalling and the note still lands). write-note is idempotent here
(`--overwrite`), so re-applying an already-saved note is harmless. On success the spool
entry is cleared; on failure it is kept for the next attempt.

edit_note is deliberately NOT auto-applied: append/prepend are non-idempotent, so a rare
mis-cleared success could double-apply. Those are left for flush_check.py to REPORT and a
human/agent to re-attempt. Content-less garbage spools are GC'd.

Wired as a SessionStart slot that runs BEFORE flush_check's report, so the report only
fires for entries that truly could not be auto-replayed.

FAIL-OPEN: any error -> exit 0 (never blocks a session). Opt-out: MEMORY_SPOOL=off or a
.disabled file. Preview with --dry-run.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import _common as C  # noqa: E402

DISABLED = THIS / ".disabled"
# The basic-memory CLI writes the vault directly (independent of the MCP server).
BM_EXE = os.environ.get(
    "BASIC_MEMORY_EXE", str(Path.home() / ".local" / "bin" / "basic-memory.exe"))
TIMEOUT = float(os.environ.get("MEMORY_SPOOL_REPLAY_TIMEOUT", "45"))


def _disabled() -> bool:
    return DISABLED.exists() or os.environ.get(
        "MEMORY_SPOOL", "").lower() in ("off", "0", "false")


def build_write_argv(payload: dict) -> list[str] | None:
    """Argv for `basic-memory tool write-note` from a write_note payload.

    Returns None for a content-less/titleless spool (garbage the caller GCs).
    Content is passed on stdin (safe for long/special text), so it is NOT in the argv.
    """
    title = str(payload.get("title") or "").strip()
    content = payload.get("content")
    content = "" if content is None else str(content)
    if not title or (not content.strip() and len(title) <= 2):
        return None
    folder = str(payload.get("directory") or payload.get("folder") or "").strip() or "/"
    argv = [BM_EXE, "tool", "write-note", "--title", title,
            "--folder", folder, "--overwrite", "--local"]
    tags = payload.get("tags")
    if tags:
        argv += ["--tags", tags if isinstance(tags, str) else ",".join(map(str, tags))]
    ntype = payload.get("note_type") or payload.get("type")
    if ntype:
        argv += ["--type", str(ntype)]
    proj = payload.get("project")
    if proj:
        argv += ["--project", str(proj)]
    return argv


def _spawn_detached() -> None:
    """Relaunch self DETACHED and return instantly.

    The basic-memory CLI is ~6s/write (cold start), so a synchronous replay would eat
    the shared SessionStart dispatch budget and starve sibling checks. The SessionStart
    slot calls `replay.py --spawn`, which fires a background copy that does the slow work
    off the critical path. The vault write is what matters; nothing is emitted to the
    session (flush_check.py still reports anything that could not be replayed).
    """
    try:
        flags = 0
        if os.name == "nt":
            flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0)
                     | getattr(subprocess, "DETACHED_PROCESS", 0))
        subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--quiet"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, close_fds=True, creationflags=flags)
    except Exception:  # noqa: BLE001
        pass


def _run(argv: list[str], stdin_text: str) -> bool:
    # Force UTF-8 for the child pipe + interpreter: Windows defaults to cp1252, which
    # raises UnicodeEncodeError on note content containing arrows/em-dashes/emoji and
    # then hangs the stdin-writer thread. encoding+env make the round-trip lossless.
    try:
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        r = subprocess.run(argv, input=stdin_text, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=TIMEOUT, env=env)
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def replay_one(path: Path, dry: bool) -> str:
    """Attempt one spool entry. Returns: replayed | garbage | keep | skip."""
    rec = C.load_json(path)
    tool = str(rec.get("tool") or rec.get("tool_name") or "")
    payload = rec.get("payload") or {}
    if not tool.endswith("write_note"):
        return "skip"  # edit_note (non-idempotent) + unknown -> leave for the report
    argv = build_write_argv(payload)
    if argv is None:
        if not dry:
            try:
                path.unlink()
            except OSError:
                pass
        return "garbage"
    if dry:
        return "replayed"
    content = str(payload.get("content") or "")
    if _run(argv, content):
        try:
            path.unlink()
        except OSError:
            pass
        return "replayed"
    return "keep"


def main(argv) -> int:
    try:
        if _disabled():
            return 0
        if "--spawn" in argv:
            if C.list_spools():   # only pay the process cost when there is work
                _spawn_detached()
            return 0
        dry = "--dry-run" in argv
        spools = C.list_spools()
        if not spools:
            return 0
        counts = {"replayed": 0, "garbage": 0, "keep": 0, "skip": 0}
        for p in spools:
            counts[replay_one(p, dry)] += 1
        done = counts["replayed"] + counts["garbage"]
        if dry:
            print(counts)
        elif done and "--quiet" not in argv:
            C.emit("SessionStart",
                   f"[memory-spool] auto-replayed {counts['replayed']} + GC'd "
                   f"{counts['garbage']} stale memory write(s) direct to the basic-memory "
                   f"vault; {counts['keep']} write(s) + {counts['skip']} edit(s) still "
                   f"pending.")
        return 0
    except Exception:
        return 0  # fail-open


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
