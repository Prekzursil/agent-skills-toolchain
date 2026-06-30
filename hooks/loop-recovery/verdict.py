#!/usr/bin/env python
"""loop-recovery/verdict.py — loop-recovery verdict engine.

Computes PROGRESSING | STALLED | LOOPING from:
  1. Anti-degen fingerprint state  (~/.claude/anti-degen/<session_id>.json)
     Written by hooks/anti-degen/fingerprint.py (PostToolUse).
     Format: list of {tool, ah, oh, ts} — same (tool, args_hash) pair appearing
     ≥REPEAT_THRESHOLD times with identical output_hash → LOOPING.
  2. Event ledger (last K events from ~/.claude/event-ledger/<slug>/events.jsonl)
     Written by hooks/event-ledger/stop-hook.py.
     * Recurring failure preconditions ≥FAILURE_REPEAT → LOOPING.
     * ≥MIN_ACTIVITY_TURNS turns with zero milestones/decisions → STALLED.

Importable with no side-effects. All I/O paths are parameterisable so tests
can inject tmp_path roots without touching real data.

Fail-open contract: any unhandled exception in compute_verdict → (PROGRESSING, reason, None).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Optional, Tuple

# ── public constants (overridable via kwargs in tests) ─────────────────────────
K = 8  # how many ledger events to inspect
REPEAT_THRESHOLD = 3  # fingerprint (tool+args) repeats → LOOPING  (mirrors anti-degen)
FAILURE_REPEAT = 2  # same failure precondition text recurs → LOOPING
MIN_ACTIVITY_TURNS = 4  # need at least this many 'turn' events before stall fires

PROGRESSING = "PROGRESSING"
STALLED = "STALLED"
LOOPING = "LOOPING"

_DEFAULT_DEGEN_ROOT = Path.home() / ".claude" / "anti-degen"
_DEFAULT_LEDGER_ROOT = Path.home() / ".claude" / "event-ledger"


# ── internal helpers ───────────────────────────────────────────────────────────


def _sha(text: str) -> str:
    """SHA-256 hex (non-crypto; sha256 per CWE-327 guidance)."""
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def _legacy_slug(p: str) -> str:
    """Identical to ledger._legacy_slug — cwd-hash path formula.

    Produces the same directory name that event-ledger/ledger.py uses for
    paths that have no pre-existing projid-based shard, covering the common
    case. If a projid-based shard exists the verdict may not find events there,
    but that is safe — it simply returns PROGRESSING (fail-open).
    """
    base = Path(p).name or "root"
    h = _sha(p)[:8]
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in base)[:40]
    return f"{safe}-{h}"


# ── fingerprint state ──────────────────────────────────────────────────────────


def _load_fingerprint(session_id: str, anti_degen_root: Path) -> list:
    """Load the anti-degen sliding-window list. Returns [] on any error."""
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in str(session_id))[
        :80
    ]
    f = anti_degen_root / f"{safe or 'unknown'}.json"
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _detect_fp_loop(
    window: list, threshold: int
) -> Tuple[Optional[str], Optional[str], int]:
    """Return (loop_id, tool_name, count) if a fingerprint loop is detected.

    A fingerprint loop = same (tool, args_hash) pair appeared ≥threshold times
    AND every occurrence produced the same output_hash (no change → no progress).
    """
    groups: dict[tuple, list] = {}
    for e in window:
        try:
            key = (str(e.get("tool", "")), str(e.get("ah", "")))
            groups.setdefault(key, []).append(e)
        except Exception:
            continue

    for (tool, ah), entries in groups.items():
        if len(entries) < threshold:
            continue
        output_hashes = {str(e.get("oh", "")) for e in entries}
        if len(output_hashes) == 1:  # all same output → stuck
            out_h = next(iter(output_hashes))
            loop_id = _sha(f"fp:{tool}:{ah}:{out_h}")[:16]
            return loop_id, tool, len(entries)

    return None, None, 0


# ── ledger events ──────────────────────────────────────────────────────────────


def _load_events(project_path: str, k: int, ledger_root: Path) -> list:
    """Read the last k events from the event-ledger JSONL. Returns [] on any error."""
    slug = _legacy_slug(str(project_path))
    events_file = ledger_root / slug / "events.jsonl"
    if not events_file.exists():
        return []
    try:
        lines = events_file.read_text(encoding="utf-8", errors="replace").splitlines()
        out = []
        for ln in lines[-k:]:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out
    except Exception:
        return []


# ── loop / stall detectors ─────────────────────────────────────────────────────


def _detect_failure_loop(
    events: list, failure_repeat: int
) -> Tuple[Optional[str], Optional[str], int]:
    """Return (loop_id, precondition_text, count) for the most-repeated failure precondition."""
    counts: dict[str, int] = {}
    for e in events:
        if e.get("kind") != "failure":
            continue
        prec = str(e.get("preconditions", "") or "").strip()
        if not prec:
            continue
        counts[prec] = counts.get(prec, 0) + 1

    # highest-count first
    for prec, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        if cnt >= failure_repeat:
            loop_id = _sha(f"fail:{prec}")[:16]
            return loop_id, prec, cnt

    return None, None, 0


def _detect_stall(events: list, min_activity_turns: int) -> bool:
    """Return True when the window shows churn-without-progress.

    Stall requires ALL of the following to hold simultaneously:
    - At least min_activity_turns 'turn' events in the window
    - Zero 'milestone' events (= nothing was completed)
    - Zero 'decision' events (= no direction was chosen)
    - Git HEAD did not change across turns (= no commits landed)
    - No non-empty dirty_files seen in any turn (= no files being worked on)

    The last two conditions guard against false-positives for sessions that
    commit code every turn but never call note.py — git HEAD changes and
    dirty-file deltas are objective progress signals that the Stop hook writes
    into every turn event, so the stall detector must honour them.
    """
    turns = [e for e in events if e.get("kind") == "turn"]
    if len(turns) < min_activity_turns:
        return False

    # Named progress signals (written via note.py by the agent)
    milestones = [e for e in events if e.get("kind") == "milestone"]
    decisions = [e for e in events if e.get("kind") == "decision"]
    if milestones or decisions:
        return False

    # Objective progress signals embedded in turn events by the Stop hook:
    # (1) git HEAD moved → commits were made this window
    non_empty_heads = [str(t.get("head", "")) for t in turns if t.get("head")]
    if len(set(non_empty_heads)) > 1:
        return False

    # (2) dirty_files non-empty → files are actively being modified
    if any(t.get("dirty_files") for t in turns):
        return False

    return True


# ── public API ─────────────────────────────────────────────────────────────────


def compute_verdict(
    session_id: str,
    project_path: str,
    *,
    anti_degen_root: Optional[Path] = None,
    ledger_root: Optional[Path] = None,
    k: int = K,
    repeat_threshold: int = REPEAT_THRESHOLD,
    failure_repeat: int = FAILURE_REPEAT,
    min_activity_turns: int = MIN_ACTIVITY_TURNS,
) -> Tuple[str, str, Optional[str]]:
    """Compute a progress verdict.

    Args:
        session_id:        Claude Code session identifier
        project_path:      cwd / project root (for ledger shard lookup)
        anti_degen_root:   override for anti-degen state root (tests)
        ledger_root:       override for event-ledger root (tests)
        k:                 number of ledger events to inspect
        repeat_threshold:  fingerprint repeat count → LOOPING
        failure_repeat:    failure precondition repeat count → LOOPING
        min_activity_turns: min turns before STALLED can fire

    Returns:
        (verdict, reason, loop_id)
        verdict:  PROGRESSING | STALLED | LOOPING
        reason:   human-readable explanation string
        loop_id:  16-char stable identifier for escalation back-off
                  (None when verdict is PROGRESSING or no distinct loop identified)

    Never raises. Any unhandled exception → (PROGRESSING, "fail-open: ...", None).
    """
    try:
        degen_root = anti_degen_root or Path(
            os.environ.get("ANTI_DEGEN_ROOT", str(_DEFAULT_DEGEN_ROOT))
        )
        lroot = ledger_root or Path(
            os.environ.get("EVENT_LEDGER_ROOT", str(_DEFAULT_LEDGER_ROOT))
        )

        # 1. Anti-degen fingerprint loop (fastest check, no ledger I/O)
        window = _load_fingerprint(str(session_id), degen_root)
        loop_id, tool, fp_count = _detect_fp_loop(window, repeat_threshold)
        if loop_id:
            return (
                LOOPING,
                f"tool '{tool}' repeated {fp_count}× with identical input+output",
                loop_id,
            )

        # 2. Ledger-based checks
        events = _load_events(str(project_path), k, lroot)

        # 2a. Recurring failure precondition
        fail_loop_id, precond, f_count = _detect_failure_loop(events, failure_repeat)
        if fail_loop_id:
            prec_short = (precond or "")[:60]
            return (
                LOOPING,
                f"failure precondition '{prec_short}' recurred {f_count}× in last {k} events",
                fail_loop_id,
            )

        # 2b. Stall (churn without progress)
        if _detect_stall(events, min_activity_turns):
            stall_id = _sha(f"stall:{session_id}")[:16]
            turn_count = sum(1 for e in events if e.get("kind") == "turn")
            return (
                STALLED,
                f"{turn_count} turns, zero milestones/decisions in last {k} events",
                stall_id,
            )

        return PROGRESSING, "progress signals found or window too short to stall", None

    except Exception as exc:
        return PROGRESSING, f"fail-open: {type(exc).__name__}: {exc}", None
