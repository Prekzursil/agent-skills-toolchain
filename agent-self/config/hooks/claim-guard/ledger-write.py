#!/usr/bin/env python3
"""claim-guard/ledger-write.py — PostToolUse hook (matcher: Bash).

Records every Bash command and its exit status to an on-disk NDJSON ledger so
claim-check.py (Stop hook) can verify that success-claims in the final response
are backed by actual tool evidence this turn.

DESIGN CONSTRAINTS:
- FAIL-OPEN: all logic is wrapped in try/except; any error → exit 0, no output.
- NON-NAGGING: this hook is record-only. It NEVER injects text or warnings.
- EXTERNAL-ANCHORED: writes raw exit codes; claim-check does the inference.
- Windows/Python 3: uses encoding="utf-8", errors="replace" on all file I/O.
- Mode gate: if env CLAIM_GUARD_MODE == "off", exits silently.

Ledger location: %TEMP%\\claude-claim-ledger\\<session_id>.ndjson
(gitignore-safe: lives in the system temp directory, not in any repo)

PostToolUse stdin JSON keys used:
  session_id    str   - identifies the current session / turn group
  tool_name     str   - must be "Bash" for this hook (enforced by matcher)
  tool_input    dict  - {"command": "...", ...}
  tool_response str|dict - stdout/stderr/exit code payload from Bash
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODE = os.environ.get("CLAIM_GUARD_MODE", "warn").lower()
_LEDGER_ROOT = Path(
    os.environ.get(
        "CLAIM_GUARD_LEDGER_ROOT",
        str(Path(tempfile.gettempdir()) / "claude-claim-ledger"),
    )
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ledger_file(session_id: str) -> Path:
    """Return the per-session NDJSON ledger path, creating parent dir if needed."""
    _LEDGER_ROOT.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in str(session_id))[
        :80
    ]
    return _LEDGER_ROOT / f"{safe or 'unknown'}.ndjson"


def _extract_command(tool_input) -> str:
    """Extract the command string from the Bash tool_input."""
    if isinstance(tool_input, dict):
        return str(tool_input.get("command") or tool_input.get("cmd") or "")
    return str(tool_input or "")


def _parse_exit_and_ok(tool_response) -> tuple[int | None, bool]:
    """
    Extract (exit_code, ok) from the Bash tool_response.

    tool_response shapes we handle:
      - dict with "exit_code" key (preferred)
      - dict with "returncode" key
      - dict with "interrupted" or "error" key → ok=False
      - str: scan for common error markers conservatively
      - unknown: default ok=True (conservative — avoid false "unverified" warnings)

    ok=True when exit_code == 0 (or we can't tell and no error markers found).
    When uncertain, we default ok=True to avoid false positives.
    """
    exit_code: int | None = None
    ok: bool = True

    if isinstance(tool_response, dict):
        # Try numeric exit code fields
        for key in ("exit_code", "exitCode", "returncode", "return_code"):
            val = tool_response.get(key)
            if val is not None:
                try:
                    exit_code = int(val)
                    ok = exit_code == 0
                    return exit_code, ok
                except (TypeError, ValueError):
                    pass

        # Check for explicit error/interrupted signals
        if tool_response.get("interrupted") or tool_response.get("error"):
            return None, False

        # Check for nested metadata (some Claude Code versions wrap in "output")
        nested = tool_response.get("output") or tool_response.get("result")
        if isinstance(nested, dict):
            return _parse_exit_and_ok(nested)

        # If we get a dict with stdout/stderr but no exit code, check stderr for errors
        stderr = str(tool_response.get("stderr") or "").strip()
        stdout = str(tool_response.get("stdout") or "").strip()
        if stderr and not stdout:
            # stderr-only, no stdout at all — lean towards failure, but not certain
            # Keep ok=True to stay conservative (avoid false "unverified" warnings)
            pass

        return exit_code, ok

    elif isinstance(tool_response, str):
        text = tool_response
        # Only mark ok=False for strongly assertive error signals in raw string output
        # (avoid false positives on tool_response that merely MENTIONS errors in output)
        lowered = text.lower()
        # Common "tool itself failed" markers (not just error output from a program)
        strong_failure_markers = [
            "command not found",
            "permission denied",
            "no such file or directory",
            "syntax error",
            "bash: ",
            "error: command failed with exit code",
            "exited with code ",
            "exit code: ",
            "returncode: ",
        ]
        for marker in strong_failure_markers:
            if marker in lowered:
                # Try to extract exit code from text
                import re

                m = re.search(r"exit(?:ed)?\s+(?:code|with)?\s*[:\s]\s*(\d+)", lowered)
                if m:
                    exit_code = int(m.group(1))
                    ok = exit_code == 0
                    return exit_code, ok
                # Marker present but no code extracted → mark as failed (conservative)
                # BUT only for the most unambiguous markers
                if marker in (
                    "command not found",
                    "permission denied",
                    "syntax error",
                    "bash: ",
                ):
                    return None, False
        return exit_code, ok

    # Fallback: unknown type → ok=True (conservative)
    return exit_code, True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    # Mode gate — must be before try/except so it can exit cleanly
    if MODE == "off":
        return 0

    try:
        raw = sys.stdin.read() or "{}"
        data = json.loads(raw)
    except Exception:
        return 0  # fail-open: malformed stdin

    try:
        tool_name = str(data.get("tool_name") or "")
        # Guard: only record Bash tool calls (settings.json matcher already does this,
        # but be defensive)
        if tool_name != "Bash":
            return 0

        session_id = str(data.get("session_id") or "unknown")
        tool_input = data.get("tool_input") or {}
        tool_response = data.get("tool_response") or data.get("tool_output") or ""

        command = _extract_command(tool_input)
        exit_code, ok = _parse_exit_and_ok(tool_response)

        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "cmd": command,
            "exit": exit_code,
            "ok": ok,
        }

        ledger_path = _ledger_file(session_id)
        with ledger_path.open("a", encoding="utf-8", errors="replace") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    except Exception:
        pass  # fail-open: any logic error → silent exit 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
