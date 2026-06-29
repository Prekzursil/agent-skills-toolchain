#!/usr/bin/env python
"""SubagentStop hook — anti-degen + guardrail contract on subagent output.

WHY: today anti-degen (PostToolUse) and honest-signal (Stop) only see the MAIN
thread.  Subagent outputs — especially in large fan-outs — can be empty, hollow,
or fail the orchestrator's expectations without any check firing.  This hook
closes that gap at the SubagentStop boundary.

WHAT IT DOES (two-phase):

  (a) Degenerate-output check (always runs):
      Reads the FINAL ASSISTANT MESSAGE from transcript_path (the real field
      in SubagentStop events — 'output'/'result' are NOT sent by Claude Code).
      — empty / whitespace-only text  → inject "produced no meaningful output"
      — suspiciously brief (<20 chars) → inject "output suspiciously brief"
      Exception: AGENTS.md §4 terminal-marker shapes (SUCCESS:<id> /
      FAILED:<id>) are LEGITIMATE terse outputs and are NEVER flagged.
      If transcript_path is absent / unreadable / has no assistant message →
      stay completely SILENT (exit 0, no flag — fail-open).
      Never blocks; just injects additionalContext.

  (b) Guardrail-contract validation (only if orchestrator registered a contract):
      The orchestrator can write a sidecar JSON file keyed by session+agent_type
      before spawning the subagent.  Schema:
          required_keywords : list[str]   — must appear in output
          forbidden_keywords: list[str]   — must NOT appear
          min_length        : int         — minimum chars (stripped)
          max_retries       : int         — max blocking rounds (default 3)
      On failure AND retry budget > 0: emit TOP-LEVEL decision:'block' + reason
        so the subagent keeps working.  (CrewAI / Goose guardrail-retry pattern.)
      On failure AND budget exhausted: emit a warning additionalContext but allow
        the subagent to finish (never infinite-loops).
      On pass: silent (reset retry counter).

  Retry budget is keyed per-spawn (session+agent_type+transcript_path hash)
  so distinct subagents of the same type never share a retry budget (M1 fix).

  Contract sidecar path:
      STATE_ROOT/contracts/<session_id>-<agent_type>.json   (sanitised)
  Retry counter path:
      STATE_ROOT/retries/<session_id>-<agent_type>-<spawn_id>.json

FAIL-OPEN: any exception → exit 0, no output, no block.
OPT-OUT  : .disabled file next to this script OR SUBAGENT_LIFECYCLE=off.

Stdin (SubagentStop event JSON):
    session_id      : str
    cwd             : str
    agent_type      : str
    transcript_path : str   (path to the session JSONL transcript — the real
                             SubagentStop field; 'output'/'result' are absent)
    ...
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    emit_context,
    is_opted_out,
    load_contract,
    load_retries,
    save_retries,
)

# ---------------------------------------------------------------------------
# Transcript parsing (identical pattern to claim-guard/claim-check.py)
# ---------------------------------------------------------------------------

def _get_final_assistant_text(transcript_path: str) -> str | None:
    """Parse the session JSONL transcript and return the text of the final
    assistant message.

    Handles two JSONL shapes emitted by different Claude Code versions:
      Shape 1: {"type": "assistant", "message": {"role": "assistant", "content": [...]}}
      Shape 2: {"role": "assistant", "content": [...]}

    Returns None if the transcript cannot be parsed or has no assistant text.
    """
    path = Path(transcript_path)
    if not path.exists():
        return None

    last_assistant_text: str | None = None

    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except Exception:
                    continue

                # Shape 1: {"type": "assistant", "message": {"role": "assistant", "content": [...]}}
                if event.get("type") == "assistant":
                    msg = event.get("message") or {}
                    if msg.get("role") == "assistant":
                        content = msg.get("content") or []
                        text_parts = []
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    text_parts.append(str(block.get("text") or ""))
                        elif isinstance(content, str):
                            text_parts.append(content)
                        if text_parts:
                            last_assistant_text = " ".join(text_parts)

                # Shape 2 (some older Claude Code versions):
                # {"role": "assistant", "content": [...]}
                elif event.get("role") == "assistant":
                    content = event.get("content") or []
                    text_parts = []
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text_parts.append(str(block.get("text") or ""))
                            elif isinstance(block, str):
                                text_parts.append(block)
                    elif isinstance(content, str):
                        text_parts.append(content)
                    if text_parts:
                        last_assistant_text = " ".join(text_parts)

    except Exception:
        return None

    return last_assistant_text


# ---------------------------------------------------------------------------
# (a) Degenerate-output detection
# ---------------------------------------------------------------------------

_MIN_SUBSTANTIVE: int = 20  # chars after strip — below this → "too brief"

# AGENTS.md §4 terminal-marker shapes: SUCCESS:<id> / FAILED:<id> [reason]
# These are LEGITIMATE terse outputs per the cross-tool behavior contract
# and must NEVER be flagged as degenerate (L3 fix).
_TERMINAL_MARKER = re.compile(
    r"^\s*(?:SUCCESS|FAILED):[^\s]",
    re.IGNORECASE,
)

# Single-token bare-assertion patterns that pass the length check (e.g. long
# number strings, "done." with lots of padding stripped to exactly "done").
_BARE_ASSERTION = re.compile(
    r"^\s*(?:done|complete[d]?|success(?:ful(?:ly)?)?|ok(?:ay)?"
    r"|yes|no|true|false|null|none|\d+|\.+)\s*$",
    re.IGNORECASE,
)


def check_degenerate(output: str) -> str | None:
    """Return a flag message if *output* looks degenerate, else None.

    Four tiers (checked in order):
      1. Empty / whitespace-only         → "no meaningful output"
      2. AGENTS.md §4 terminal marker    → EXEMPT — return None immediately
      3. Length < _MIN_SUBSTANTIVE       → "suspiciously brief"
      4. Bare single-token assertion     → "bare assertion, no detail"
    """
    stripped = (output or "").strip()

    if not stripped:
        return (
            "[subagent-lifecycle] Subagent produced no meaningful output (empty). "
            "The result cannot be verified. Please complete the task and provide "
            "a substantive report."
        )

    # AGENTS.md §4 terminal markers are intentionally terse — never flag them.
    if _TERMINAL_MARKER.match(stripped):
        return None

    if len(stripped) < _MIN_SUBSTANTIVE:
        return (
            f"[subagent-lifecycle] Subagent output is suspiciously brief "
            f"({len(stripped)} chars after stripping). A substantive completion "
            f"report is expected."
        )

    if _BARE_ASSERTION.match(stripped):
        return (
            "[subagent-lifecycle] Subagent output is a bare assertion with no "
            "supporting evidence or detail. Provide a specific completion report."
        )

    return None


# ---------------------------------------------------------------------------
# (b) Result-contract validation
# ---------------------------------------------------------------------------

def validate_contract(output: str, contract: dict) -> tuple[bool, str]:
    """Validate *output* against a result-contract dict.

    Supported contract keys (all optional):
        required_keywords : list[str]  — strings that MUST appear in output
        forbidden_keywords: list[str]  — strings that MUST NOT appear
        min_length        : int        — minimum chars (stripped)
        max_retries       : int        — blocking-round cap (consumed elsewhere)

    Returns (passed: bool, reason: str).  reason is "" on pass.
    """
    stripped = (output or "").strip()
    reasons: list[str] = []

    min_len = int(contract.get("min_length") or 0)
    if min_len and len(stripped) < min_len:
        reasons.append(f"output too short ({len(stripped)} < {min_len} chars)")

    for kw in list(contract.get("required_keywords") or []):
        if kw and kw not in output:
            reasons.append(f"missing required keyword '{kw}'")

    for kw in list(contract.get("forbidden_keywords") or []):
        if kw and kw in output:
            reasons.append(f"forbidden keyword '{kw}' present")

    if reasons:
        return False, "; ".join(reasons)
    return True, ""


# ---------------------------------------------------------------------------
# Per-spawn identifier
# ---------------------------------------------------------------------------

def _spawn_id(transcript_path: str) -> str:
    """Return a short stable hash of transcript_path for per-spawn retry keying.

    Using md5 purely as a non-cryptographic hash for a file-path string.
    """
    if not transcript_path:
        return ""
    return hashlib.md5(
        transcript_path.encode("utf-8"), usedforsecurity=False
    ).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    try:
        if is_opted_out():
            return 0

        try:
            data = json.loads(sys.stdin.read() or "{}")
        except Exception:
            return 0  # malformed stdin — fail-open

        session_id = str(data.get("session_id") or "unknown")
        agent_type = str(data.get("agent_type") or "unknown")
        # SubagentStop carries transcript_path, NOT an 'output' field (C1 fix).
        transcript_path = str(data.get("transcript_path") or "")

        # Derive a per-spawn id so distinct subagents of the same agent_type
        # never share a retry budget (M1 fix).
        sid = _spawn_id(transcript_path)

        # ── Read the final assistant message from the transcript ──────────────
        # If transcript_path is absent or the file is unreadable / has no
        # assistant message → stay completely silent (fail-open).
        if not transcript_path:
            return 0

        output = _get_final_assistant_text(transcript_path)
        if output is None:
            return 0  # unreadable / no assistant text → silent

        # ── (a) degenerate-output check ──────────────────────────────────────
        degen_msg = check_degenerate(output)
        if degen_msg:
            emit_context("SubagentStop", degen_msg)
            return 0

        # ── (b) result-contract guardrail ────────────────────────────────────
        contract = load_contract(session_id, agent_type)
        if not contract:
            return 0  # no contract registered → silent approval

        passed, reason = validate_contract(output, contract)
        if passed:
            # Reset retry counter on success (clean slate for next subagent run).
            save_retries(session_id, agent_type, {"attempts": 0}, spawn_id=sid)
            return 0

        # Contract failed — check the retry budget.
        retry_state = load_retries(session_id, agent_type, spawn_id=sid)
        attempts = int(retry_state.get("attempts") or 0)
        max_retries = int(contract.get("max_retries") or 3)

        if attempts >= max_retries:
            # Budget exhausted — give up gracefully; NEVER loop forever.
            emit_context(
                "SubagentStop",
                f"[subagent-lifecycle] Contract validation failed ({reason}) "
                f"and max retries ({max_retries}) exhausted. Proceeding anyway.",
            )
            save_retries(session_id, agent_type, {"attempts": 0}, spawn_id=sid)
            return 0

        # Block the subagent with targeted feedback for the retry.
        # decision + reason are emitted TOP-LEVEL per SubagentStop spec (M1 fix).
        save_retries(session_id, agent_type, {"attempts": attempts + 1}, spawn_id=sid)
        feedback = (
            f"[subagent-lifecycle] Result failed contract: {reason} — "
            f"retry with this feedback "
            f"(attempt {attempts + 1}/{max_retries})."
        )
        emit_context(
            "SubagentStop",
            feedback,
            decision="block",
            reason=feedback,
        )

    except Exception:
        pass  # fail-open: any unexpected error → silent exit 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
