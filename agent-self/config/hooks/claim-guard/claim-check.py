#!/usr/bin/env python3
"""claim-guard/claim-check.py — Stop hook (no matcher required).

Scans the final assistant response for assertive success-claims (e.g. "tests pass",
"fixed", "all green", "build succeeds"). For each matched CATEGORY, checks the
per-session Bash ledger written by ledger-write.py. If a claim category has NO
supporting successful command in the ledger this turn → injects ONE concise warning
listing the unsupported claim(s).

DESIGN CONSTRAINTS:
- FAIL-OPEN: all logic is wrapped in try/except; any error → exit 0, no output.
- NON-NAGGING: only emits when (a) a success-claim phrase is present AND
  (b) no supporting ok=true command exists. Otherwise completely silent.
- EXTERNAL-ANCHORED: judges against real exit codes in the ledger, never prose.
- False-positive controls:
    * Requires assertive past/present-tense claims (not "should pass" / "would pass")
    * Only warns once per Stop event (one combined message)
    * When uncertain, stays silent (conservative)
- Windows/Python 3: encoding="utf-8", errors="replace" on all I/O.
- Mode gate: CLAIM_GUARD_MODE env var: "warn" (default) | "off" | "block" (stub).

Stop hook stdin JSON keys used:
  session_id       str   - to locate the correct ledger file
  stop_hook_active bool  - if true, we are in a hook continuation → skip (anti-loop)
  transcript_path  str   - path to the session JSONL transcript; final assistant message
                           is the last entry with role=="assistant"
  cwd              str   - fallback for session identification

Stdout (when warning fires):
  JSON {"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": "<msg>"}}
Stdout (silent case): nothing
Exit: always 0 (WARN mode only; block stub is here but not enabled by default)
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODE = os.environ.get("CLAIM_GUARD_MODE", "warn").lower()
_LEDGER_ROOT = Path(os.environ.get(
    "CLAIM_GUARD_LEDGER_ROOT",
    str(Path(tempfile.gettempdir()) / "claude-claim-ledger")
))


# ---------------------------------------------------------------------------
# Claim detection — assertive only, no hypotheticals
# ---------------------------------------------------------------------------

# We require word-boundary anchors to avoid false matches (e.g. "fixed" in "as-fixed").
# The patterns must match ASSERTIVE past/present-tense claims.
# Hypothetical / conditional forms are excluded via a NOT-following pattern check.

# Map of claim_category → compiled regex
_CLAIM_PATTERNS: dict[str, re.Pattern] = {
    "tests": re.compile(
        r"\b(?:"
        r"tests?\s+(?:are\s+)?pass(?:ing|ed)?"        # tests pass / tests passing / test passed
        r"|all\s+tests?\s+(?:are\s+)?pass(?:ing|ed)?"  # all tests pass / all tests passing
        r"|(?:the\s+)?test\s+suite\s+pass(?:es|ed)?"   # the test suite passes / passed
        r")",
        re.IGNORECASE,
    ),
    "build": re.compile(
        r"\b(?:"
        r"build\s+(?:succeeds?|passes?|is\s+green|is\s+clean|compiles?)"  # build succeeds/passes/is green
        r"|builds?\s+successfully"                       # builds successfully
        r"|compilation\s+succeeds?"                      # compilation succeeds
        r"|(?:the\s+)?build\s+(?:is\s+)?(?:passing|green|clean)"  # build is passing/green
        r")",
        re.IGNORECASE,
    ),
    "lint": re.compile(
        r"\b(?:"
        r"lint(?:ing)?\s+(?:passes?|is\s+clean|succeeds?)"  # linting passes / lint is clean
        r"|no\s+lint(?:ing)?\s+(?:errors?|warnings?)"       # no linting errors
        r"|lint(?:er)?\s+(?:checks?\s+)?(?:pass(?:es|ed)?|clean)"
        r")",
        re.IGNORECASE,
    ),
    "coverage": re.compile(
        r"\b(?:"
        r"coverage\s+(?:(?:threshold(?:s)?\s+)?(?:met|pass(?:es|ed)?|satisfied))"  # coverage met/passes
        r"|(?:meets?|satisfies?)\s+(?:the\s+)?coverage"    # meets the coverage
        r")",
        re.IGNORECASE,
    ),
    "fixed": re.compile(
        r"\b(?:"
        r"(?:(?:is|are|has\s+been|have\s+been)\s+)?fixed\b"  # is fixed / has been fixed / fixed
        r"|(?:the\s+)?(?:bug|issue|error|problem)\s+(?:is\s+)?(?:now\s+)?fixed"
        r")",
        re.IGNORECASE,
    ),
    "all_green": re.compile(
        r"\b(?:"
        r"all\s+(?:checks?\s+)?(?:are\s+)?(?:green|pass(?:ing|ed)?)"  # all checks are green
        r"|everything(?:'s|\s+is)?\s+(?:green|passing|clean)"          # everything's green
        r"|all\s+green\b"                                               # all green
        r")",
        re.IGNORECASE,
    ),
    "no_errors": re.compile(
        r"\b(?:"
        r"no\s+errors?\s+(?:found|remaining|detected)"    # no errors found
        r"|(?:zero|0)\s+errors?"                          # zero errors
        r")",
        re.IGNORECASE,
    ),
    # CI / remote-gate / merge-readiness claims. Strict: only an actual CI-check
    # command (gh pr checks / gh run view / MCP gate read run via gh) counts as
    # evidence — a green LOCAL build does NOT support "the gates are green".
    # (HEAD-SHA freshness + no-op detection are enforced by the ci-silent-pass-lint
    # skill, the mechanizable home for those checks.)
    "ci_gates": re.compile(
        r"\b(?:"
        r"(?:ci|gates?|pipeline)\s+(?:are\s+|is\s+)?(?:green|passing|pass(?:ed|es)?)"  # ci/gates green/passing
        r"|gates?\s+(?:are\s+)?green"                                                   # gates are green
        r"|all\s+(?:ci\s+)?checks?\s+(?:are\s+)?(?:green|passing|pass(?:ed|es)?)"       # all checks passed
        r"|(?:ready|safe)\s+to\s+merge|mergeable"                                       # ready/safe to merge
        r"|(?:pr|pull\s+request)\s+is\s+(?:green|passing|mergeable)"                    # PR is green
        r")",
        re.IGNORECASE,
    ),
}

# Hypothetical / conditional hedge phrases — if found near a claim, suppress the warning.
# We check within a 120-char window around the match.
_HEDGE_PATTERNS = re.compile(
    r"\b(?:"
    r"should\s+(?:now\s+)?(?:pass|work|be|run)"
    r"|would\s+(?:pass|work|be)"
    r"|will\s+(?:likely|probably)\s+"
    r"|expected\s+to\s+"
    r"|(?:once|after|when|if)\s+you\s+"
    r"|might\s+(?:pass|work)"
    r"|appears?\s+to\s+"
    r"|looks?\s+like\s+(?:it\s+)?(?:pass|work)"
    r")",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Ledger-query helpers
# ---------------------------------------------------------------------------

# Map claim_category → set of command substrings that count as supporting evidence
_SUPPORT_CMDS: dict[str, list[str]] = {
    "tests":    ["pytest", "jest", "go test", "npm test", "npm run test",
                 "yarn test", "cargo test", "mvn test", "gradle test",
                 "python -m pytest", "dotnet test", "rspec", "mocha", "vitest"],
    "build":    ["npm run build", "yarn build", "cargo build", "make ",
                 "gradlew", "gradle build", "tsc", "webpack", "vite build",
                 "mvn package", "dotnet build", "go build", "cmake"],
    "lint":     ["eslint", "ruff", "flake8", "pylint", "semgrep",
                 "mypy", "pyright", "black --check", "prettier --check",
                 "golangci-lint", "clippy", "rubocop"],
    "coverage": ["pytest", "jest --coverage", "npm run test", "coverage run",
                 "lcov", "nyc", "cargo tarpaulin"],
    "fixed":    [],  # "fixed" is generic; any successful command is supporting evidence
    "all_green": [], # same — any successful command supports "all green"
    "no_errors": [], # same — any successful command supports "no errors"
    # STRICT (non-empty): only a real remote-CI/gate query supports a "gates green"
    # claim — a green local build is NOT evidence. This is the core of the #2 tuning.
    "ci_gates": ["gh pr checks", "gh run view", "gh run list", "gh checks",
                 "gh pr view", "gh workflow view", "gh api"],
}


def _ledger_file(session_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in str(session_id))[:80]
    return _LEDGER_ROOT / f"{safe or 'unknown'}.ndjson"


def _load_ledger(session_id: str) -> list[dict]:
    """Return all ledger records for this session. Returns [] on any error."""
    path = _ledger_file(session_id)
    if not path.exists():
        return []
    records: list[dict] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        pass
    return records


def _has_support(category: str, ledger: list[dict]) -> bool:
    """
    Return True if the ledger contains a successful command that supports the claim.

    For generic categories (fixed, all_green, no_errors), ANY ok=true command counts.
    For specific categories, the command must match one of the category's command patterns.
    """
    ok_records = [r for r in ledger if r.get("ok") is True]
    if not ok_records:
        return False

    support_cmds = _SUPPORT_CMDS.get(category, [])
    if not support_cmds:
        # Generic category — any ok=true command is sufficient
        return True

    for record in ok_records:
        cmd = (record.get("cmd") or "").lower()
        if any(pat in cmd for pat in support_cmds):
            return True

    return False


# ---------------------------------------------------------------------------
# Transcript parsing
# ---------------------------------------------------------------------------

def _get_final_assistant_text(transcript_path: str) -> str | None:
    """
    Parse the session JSONL transcript and return the text of the final assistant message.

    The transcript is a JSONL file where each line is an event. Assistant messages have
    type="assistant" with message.role="assistant" and message.content[].text.

    Returns None if the transcript cannot be parsed or no assistant text is found.
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
# Claim scanning
# ---------------------------------------------------------------------------

def _is_hedged(text: str, match_start: int, match_end: int) -> bool:
    """Return True if a hedge phrase appears within ±120 chars of this match."""
    window_start = max(0, match_start - 120)
    window_end = min(len(text), match_end + 120)
    window = text[window_start:window_end]
    return bool(_HEDGE_PATTERNS.search(window))


def _find_fired_categories(text: str) -> list[str]:
    """
    Return list of claim categories that have an assertive (non-hedged) match in text.
    """
    fired: list[str] = []
    for category, pattern in _CLAIM_PATTERNS.items():
        for m in pattern.finditer(text):
            if not _is_hedged(text, m.start(), m.end()):
                fired.append(category)
                break  # one match per category is enough
    return fired


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _inject_warning(unsupported: list[str]) -> None:
    """Emit the additionalContext JSON for the Stop event."""
    # Human-readable category labels
    labels = {
        "tests":     "tests pass",
        "build":     "build succeeds",
        "lint":      "lint passes",
        "coverage":  "coverage met",
        "fixed":     "issue fixed",
        "all_green": "all green",
        "no_errors": "no errors",
        "ci_gates":  "CI gates green / ready to merge",
    }
    claim_list = ", ".join(f'"{labels.get(c, c)}"' for c in unsupported)
    msg = (
        f"[Claim-Guard] Unverified success claim(s) detected: {claim_list}. "
        f"No successful supporting command was found in the Bash ledger this turn. "
        f"Please run the relevant commands (tests, build, lint, etc.) and verify "
        f"before asserting these outcomes."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": msg,
        }
    }))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    # Mode gate
    if MODE == "off":
        return 0

    # BLOCK stub — not enabled by default, reserved for future escalation
    # if MODE == "block":
    #     ... (would output decision:block + reason, then sys.exit(2))
    #     pass  # for now, fall through to warn

    try:
        raw = sys.stdin.read() or "{}"
        data = json.loads(raw)
    except Exception:
        return 0  # fail-open: malformed stdin

    try:
        # Anti-loop guard: if we're already inside a stop-hook continuation, do nothing
        if data.get("stop_hook_active"):
            return 0

        session_id = str(data.get("session_id") or "unknown")
        transcript_path = str(data.get("transcript_path") or "")

        # Get the final assistant response text
        if not transcript_path:
            return 0  # can't check without a transcript

        final_text = _get_final_assistant_text(transcript_path)
        if not final_text:
            return 0  # no assistant text found → silent

        # Find assertive claim categories
        fired = _find_fired_categories(final_text)
        if not fired:
            return 0  # no claims → silent

        # Load the ledger
        ledger = _load_ledger(session_id)

        # Check each fired category for supporting evidence
        unsupported = [c for c in fired if not _has_support(c, ledger)]
        if not unsupported:
            return 0  # all claims are supported → silent

        # Emit one combined warning
        _inject_warning(unsupported)

    except Exception:
        pass  # fail-open: any logic error → silent exit 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
