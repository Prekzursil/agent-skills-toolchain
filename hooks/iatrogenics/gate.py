#!/usr/bin/env python3
r"""iatrogenics/gate.py — PreToolUse hook: watchful-waiting advisory.

"Primum non nocere" — does the fix's blast/irreversibility exceed the problem severity,
and is the symptom actually transient/self-resolving?

For each incoming tool call that is classified as IRREVERSIBLE (heuristic: rm -rf,
force-overwrites, device writes, MITM, CheatEngine memory writes, Frida code injection)
AND is at LOW RECURRENCE for this session (same action signature tried < K times), this
hook INJECTS (exit 0 + additionalContext) a watchful-waiting advisory.

First-occurrence behaviour:
  - Non-MCP-tool triggers (Bash commands, device path writes): the watchful-waiting
    premise requires RECURRENCE. First use is usually intentional, not a retry-loop.
    Advisory does NOT fire on occurrence #1; counter still increments.
  - MCP tool triggers (CheatEngine writes, Frida execute/spawn): fire from occurrence #1
    because these are model-initiated mutations that warrant immediate advisory.

Recurrence counter: per-session JSON file at IATROGENICS_COUNTER_DIR/<session_hash>.json.
Auto-clears after IATROGENICS_TTL_HOURS (default 4h). Counter increments on every
irreversible call regardless of whether the advisory was injected.

NEVER blocks. FAIL-OPEN: any exception -> exit 0. Pure stdlib.
Opt-out: IATROGENICS=off (or "0"/"false") OR a .disabled file in this directory.

Settings.json wire spec (PreToolUse):
  Matcher:       Edit|Write|Bash|mcp__cheatengine__.*|mcp__frida-mcp__.*
  Command:       python C:/Users/Prekzursil/.claude/hooks/iatrogenics/gate.py
  Timeout:       5000
  StatusMessage: Iatrogenics watchful-waiting gate
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"

# ---------------------------------------------------------------------------
# Calibrated-silence path setup (fail-open import)
# ---------------------------------------------------------------------------
_CAL_SIL_DIR = str(THIS.parent / "calibrated-silence")
if _CAL_SIL_DIR not in sys.path:
    sys.path.insert(0, _CAL_SIL_DIR)

# ---------------------------------------------------------------------------
# Configuration (all overridable via env vars)
# ---------------------------------------------------------------------------
# Number of irreversible attempts before the advisory stops firing.
_K = int(os.environ.get("IATROGENICS_K", "3"))
# Auto-clear TTL for the per-session counter files (hours).
_TTL_HOURS = float(os.environ.get("IATROGENICS_TTL_HOURS", "4"))
# Directory for per-session counter state files.
_COUNTER_DIR = Path(
    os.environ.get(
        "IATROGENICS_COUNTER_DIR",
        str(Path.home() / ".claude" / "iatrogenics"),
    )
)
# L4: maximum command length scanned by regex; skip beyond this to avoid O(n) on huge inputs.
_MAX_CMD_BYTES = 256 * 1024

# ---------------------------------------------------------------------------
# Irreversibility heuristics
# ---------------------------------------------------------------------------
# MCP tool names that directly mutate live process state (always irreversible).
_IRREVERSIBLE_TOOL_RE = re.compile(
    r"mcp__cheatengine__(write_memory|write_integer|write_string|auto_assemble|patch_bytes)"
    r"|mcp__frida-mcp__(execute_in_session|spawn_process)",
    re.IGNORECASE,
)

# Bash / PowerShell command patterns that are hard or impossible to undo.
_IRREVERSIBLE_CMD_RE = re.compile(
    r"\brm\b\s+(-[rf]+|-{1,2}(recursive|force)\b)"  # rm -rf, rm -f, rm --force
    r"|Remove-Item\b.*-Force\b"  # PowerShell destructive delete
    r"|\bdd\b.*\bof="  # dd disk write
    r"|git\s+(push\b.*--force\b|reset\b.*--hard\b|checkout\s+--\s)"  # destructive git
    r"|\bsed\s+-i\b"  # in-place sed (no backup)
    r"|\btruncate\b"  # truncate a file
    r"|\bmkfs\b|\bformat\s+[A-Za-z]:"  # format disk
    r"|>\s*/dev/(?!null\b|zero\b|random\b|urandom\b|stdin\b|stdout\b|stderr\b)"
    r"|--overwrite\b|--force-overwrite\b"
    r"|\bmitmproxy\b|\bmitmdump\b",  # MITM (irreversible re: BC HGT)
    re.IGNORECASE | re.VERBOSE,
)

# File paths that are considered irreversible targets (device / firmware writes).
_IRREVERSIBLE_PATH_RE = re.compile(r"^/dev/|^\\\\.\\", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _disabled() -> bool:
    return DISABLED.exists() or os.environ.get("IATROGENICS", "").lower() in (
        "off",
        "0",
        "false",
    )


def _emit(msg: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": msg,
                }
            }
        )
    )


def _cs_allow(itype: str, context: dict) -> bool:
    """Gate through calibrated-silence. Fail-open = True if module unavailable."""
    try:
        import calibrated_silence  # noqa: PLC0415

        ctx = dict(context)
        ledger = os.environ.get("CALSIL_LEDGER_PATH")
        if ledger:
            ctx["ledger_path"] = ledger
        allow, _ = calibrated_silence.should_interject(itype, ctx)
        return bool(allow)
    except Exception:
        return True  # fail-open: never suppress on error


def _is_irreversible(tool_name: str, tool_input: dict) -> bool:
    """Heuristic classifier: is this tool call likely irreversible?"""
    try:
        # 1. Specific MCP tools that mutate live process state.
        if tool_name and _IRREVERSIBLE_TOOL_RE.search(tool_name):
            return True
        # 2. Bash / PowerShell destructive command patterns (L4: size-capped).
        cmd = str(tool_input.get("command") or "")[:_MAX_CMD_BYTES]
        if cmd and _IRREVERSIBLE_CMD_RE.search(cmd):
            return True
        # 3. Write / Edit targeting a device path.
        fp = str(tool_input.get("file_path") or "")
        if fp and _IRREVERSIBLE_PATH_RE.search(fp):
            return True
    except Exception:
        pass
    return False


def _action_sig(tool_name: str, tool_input: dict) -> str:
    """Stable short key for (tool, target) used as the counter bucket key."""
    try:
        cmd = str(tool_input.get("command") or "")
        fp = str(tool_input.get("file_path") or "")
        target = (fp or cmd)[:120]
        raw = f"{tool_name}:{target}"
        # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1 -- non-cryptographic action fingerprint for dedup, not a security control
        return hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()[:16]
    except Exception:
        return "unknown"


def _counter_path(session_id: str) -> Path:
    try:
        # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1 -- non-cryptographic session-id slug for a state-file name, not a security control
        h = hashlib.sha1(session_id.encode("utf-8", "replace")).hexdigest()[:24]
        return _COUNTER_DIR / f"{h}.json"
    except Exception:
        return _COUNTER_DIR / "default.json"


def _load_counter(session_id: str) -> dict:
    """Load the session counter dict; returns {} if absent or expired."""
    p = _counter_path(session_id)
    try:
        if not p.exists():
            return {}
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        # Auto-clear: if the file is older than the TTL, start fresh.
        ts = float(data.get("_ts", 0))
        if time.time() - ts > _TTL_HOURS * 3600:
            return {}
        return data
    except Exception:
        return {}


def _save_counter(session_id: str, counter: dict) -> None:
    try:
        _COUNTER_DIR.mkdir(parents=True, exist_ok=True)
        counter["_ts"] = time.time()
        _counter_path(session_id).write_text(json.dumps(counter), encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    try:
        if _disabled():
            return 0

        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except Exception:
            return 0  # malformed stdin -> fail-open

        tool_name = str(payload.get("tool_name") or "")
        tool_input = payload.get("tool_input") or {}
        session_id = str(payload.get("session_id") or payload.get("cwd") or "default")

        if not _is_irreversible(tool_name, tool_input):
            return 0  # reversible action — no advisory needed

        sig = _action_sig(tool_name, tool_input)
        counter = _load_counter(session_id)
        count = int(counter.get(sig, 0))

        # High-severity = a model-initiated live-state mutation (CheatEngine memory
        # write, Frida code injection). Its DISTINCT first occurrence is a new safety
        # alert and must NEVER be gagged just because the session is long/noisy, so it
        # BYPASSES calibrated-silence. A REPEAT (count>0) is still CS-gated (dedup).
        is_high_sev = bool(tool_name and _IRREVERSIBLE_TOOL_RE.search(tool_name))
        cs_bypass = is_high_sev and count == 0

        # Calibrated-silence gate: suppress if the operating point says no (fail-open).
        if not cs_bypass and not _cs_allow(
            "suggestion",
            {"prompt": str(payload.get("prompt", "")), "session_id": session_id},
        ):
            # Still increment the counter so recurrence tracking is accurate.
            counter[sig] = count + 1
            _save_counter(session_id, counter)
            return 0

        # First-occurrence skip for non-MCP-tool triggers (Bash commands, path writes).
        # Watchful-waiting premise: the advisory is useful for RECURRING symptoms.
        # First use of a destructive command is usually intentional, not a retry-loop.
        # MCP tool triggers (CheatEngine/Frida) bypass this — model-initiated mutations
        # are dangerous from the very first call.
        cmd_triggered = not is_high_sev
        if cmd_triggered and count == 0:
            counter[sig] = count + 1
            _save_counter(session_id, counter)
            return 0

        if count < _K:
            observe_n = _K - count - 1
            observe_str = (
                f"{observe_n} more occurrence(s)"
                if observe_n > 0
                else "before taking irreversible action"
            )
            _emit(
                f"IATROGENICS GATE — watchful-waiting recommended:\n"
                f"This is occurrence {count + 1}/{_K} of an IRREVERSIBLE action on this "
                f"target in the current session.\n"
                f"First occurrences of the same symptom are often transient (race condition, "
                f"flaky test, temporary lock, stale cache). The intervention's own blast "
                f"radius may exceed the problem severity if the root cause is self-resolving.\n"
                f"Recommendation: observe {observe_str}; confirm the symptom is "
                f"non-transient before proceeding."
            )

        # Always increment — track every irreversible attempt regardless of inject.
        counter[sig] = count + 1
        _save_counter(session_id, counter)

    except Exception:
        pass  # fail-open

    return 0


if __name__ == "__main__":
    sys.exit(main())
