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
- Mode gate: CLAIM_GUARD_MODE env var: "warn" (default) | "off" | "block".
  In "block" mode an UNSUPPORTED `functional` ("it works now") claim exits 2
  (blocks the Stop); every other category, and warn/off mode, stay exit-0 warnings
  so nothing that worked before starts blocking.

Stop hook stdin JSON keys used:
  session_id       str   - to locate the correct ledger file
  stop_hook_active bool  - if true, we are in a hook continuation → skip (anti-loop)
  transcript_path  str   - path to the session JSONL transcript; final assistant message
                           is the last entry with role=="assistant"
  cwd              str   - fallback for session identification

Stdout (when warning fires):
  JSON {"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": "<msg>"}}
Stdout (silent case): nothing
Exit: 0 (warn/off, and unsupported non-functional claims even in block mode); 2 only
  for an unsupported `functional` claim under CLAIM_GUARD_MODE=block.
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
# Turn-boundary marker. Mirrors TURN_BOUNDARY_KEY in ledger-write.py -- the pair
# cannot share a module (hyphenated filenames are not importable), which is why
# `_ledger_file` is already duplicated across the two hooks.
TURN_BOUNDARY_KEY = "turn_end"

_LEDGER_ROOT = Path(
    os.environ.get(
        "CLAIM_GUARD_LEDGER_ROOT",
        str(Path(tempfile.gettempdir()) / "claude-claim-ledger"),
    )
)


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
        r"tests?\s+(?:are\s+)?pass(?:ing|ed)?"  # tests pass / tests passing / test passed
        r"|all\s+tests?\s+(?:are\s+)?pass(?:ing|ed)?"  # all tests pass / all tests passing
        r"|(?:the\s+)?test\s+suite\s+pass(?:es|ed)?"  # the test suite passes / passed
        r")",
        re.IGNORECASE,
    ),
    "build": re.compile(
        r"\b(?:"
        r"build\s+(?:succeeds?|passes?|is\s+green|is\s+clean|compiles?)"  # build succeeds/passes/is green
        r"|builds?\s+successfully"  # builds successfully
        r"|compilation\s+succeeds?"  # compilation succeeds
        r"|(?:the\s+)?build\s+(?:is\s+)?(?:passing|green|clean)"  # build is passing/green
        r")",
        re.IGNORECASE,
    ),
    "lint": re.compile(
        r"\b(?:"
        r"lint(?:ing)?\s+(?:passes?|is\s+clean|succeeds?)"  # linting passes / lint is clean
        r"|no\s+lint(?:ing)?\s+(?:errors?|warnings?)"  # no linting errors
        r"|lint(?:er)?\s+(?:checks?\s+)?(?:pass(?:es|ed)?|clean)"
        r")",
        re.IGNORECASE,
    ),
    "coverage": re.compile(
        r"\b(?:"
        r"coverage\s+(?:(?:threshold(?:s)?\s+)?(?:met|pass(?:es|ed)?|satisfied))"  # coverage met/passes
        r"|(?:meets?|satisfies?)\s+(?:the\s+)?coverage"  # meets the coverage
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
        r"|everything(?:'s|\s+is)?\s+(?:green|passing|clean)"  # everything's green
        r"|all\s+green\b"  # all green
        r")",
        re.IGNORECASE,
    ),
    "no_errors": re.compile(
        r"\b(?:"
        r"no\s+errors?\s+(?:found|remaining|detected)"  # no errors found
        r"|(?:zero|0)\s+errors?"  # zero errors
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
        r"|gates?\s+(?:are\s+)?green"  # gates are green
        r"|all\s+(?:ci\s+)?checks?\s+(?:are\s+)?(?:green|passing|pass(?:ed|es)?)"  # all checks passed
        r"|(?:ready|safe)\s+to\s+merge|mergeable"  # ready/safe to merge
        r"|(?:pr|pull\s+request)\s+is\s+(?:green|passing|mergeable)"  # PR is green
        r")",
        re.IGNORECASE,
    ),
    # G1 — FUNCTIONAL-ACCEPTANCE: assertive PRODUCT "it works now" claims. Unlike the
    # categories above, a generic unit-test pass does NOT satisfy this — see
    # _E2E_SIGNATURES / _has_support: a `functional` claim needs a real end-to-end /
    # held-out golden-journey / acceptance run this turn. Same hedge-suppression +
    # word-boundary discipline as every other category.
    "functional": re.compile(
        r"\b(?:"
        # <subject> [now] works / is working / renders / generates / produces / ships
        r"(?:the\s+)?(?:app|application|feature|button|flow|pipeline|export|"
        r"render(?:er)?|video|clip|shorts?|reels?|ui|page|screen|integration|"
        r"product|workflow|command|script|tool)\s+"
        r"(?:now\s+)?(?:works?|is\s+working|are\s+working|renders?|generates?|"
        r"produces?|functions?|is\s+functional|is\s+done|is\s+ready|ships?|shipped)\b"
        # it / this / everything [now] works / renders / generates / produces
        r"|(?:it|this|everything)\s+(?:now\s+)?(?:works?|is\s+working|renders?|"
        r"generates?|produces?)\b"
        # end-to-end works / e2e works / works end to end / works as expected
        r"|(?:end[-\s]?to[-\s]?end|e2e)\s+(?:works?|passes?|is\s+working)\b"
        r"|works?\s+(?:end[-\s]?to[-\s]?end|as\s+expected)\b"
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
    "tests": [
        "pytest",
        "jest",
        "go test",
        "npm test",
        "npm run test",
        "yarn test",
        "cargo test",
        "mvn test",
        "gradle test",
        "python -m pytest",
        "dotnet test",
        "rspec",
        "mocha",
        "vitest",
    ],
    "build": [
        "npm run build",
        "yarn build",
        "cargo build",
        "make ",
        "gradlew",
        "gradle build",
        "tsc",
        "webpack",
        "vite build",
        "mvn package",
        "dotnet build",
        "go build",
        "cmake",
    ],
    "lint": [
        "eslint",
        "ruff",
        "flake8",
        "pylint",
        "semgrep",
        "mypy",
        "pyright",
        "black --check",
        "prettier --check",
        "golangci-lint",
        "clippy",
        "rubocop",
    ],
    "coverage": [
        "pytest",
        "jest --coverage",
        "npm run test",
        "coverage run",
        "lcov",
        "nyc",
        "cargo tarpaulin",
    ],
    "fixed": [],  # "fixed" is generic; any successful command is supporting evidence
    "all_green": [],  # same — any successful command supports "all green"
    "no_errors": [],  # same — any successful command supports "no errors"
    # STRICT (non-empty): only a real remote-CI/gate query supports a "gates green"
    # claim — a green local build is NOT evidence. This is the core of the #2 tuning.
    "ci_gates": [
        "gh pr checks",
        "gh run view",
        "gh run list",
        "gh checks",
        "gh pr view",
        "gh workflow view",
        "gh api",
    ],
}


# G1 — external evidence bar for a `functional` ("it works now") claim.
# These are the ONLY commands that count as evidence that the product actually
# runs end to end this turn. A plain unit-test pass (pytest/jest/…) deliberately
# does NOT qualify — that higher, EXTERNAL bar is the whole point of the category.
# Substring match (case-insensitive) against the ledger command. Small + curated so
# it is trivial to extend: add app-specific produced-artifact signatures here, or
# per-project via the CLAIM_GUARD_E2E_EXTRA env var (comma-separated substrings,
# e.g. "media_studio,render_shorts").
_E2E_SIGNATURES: list[str] = [
    "playwright",  # npx playwright test / playwright test
    "cypress",  # cypress run / cypress open
    "e2e",  # npm run e2e / yarn e2e / *e2e* spec paths / --grep e2e
    "golden",  # golden-journey / golden-path acceptance runs
    "acceptance",  # *acceptance* suites
    "nightwatch",  # browser e2e runner
    "webdriver",  # selenium / webdriverio
    "testcafe",  # browser e2e runner
]


def _e2e_signatures() -> list[str]:
    """The e2e/acceptance signatures plus any CLAIM_GUARD_E2E_EXTRA additions."""
    extra = os.environ.get("CLAIM_GUARD_E2E_EXTRA", "")
    extras = [s.strip().lower() for s in extra.split(",") if s.strip()]
    return _E2E_SIGNATURES + extras


def _ledger_file(session_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in str(session_id))[
        :80
    ]
    return _LEDGER_ROOT / f"{safe or 'unknown'}.ndjson"


def _load_ledger(session_id: str) -> list[dict]:
    """Return THIS TURN's ledger records for this session. [] on any error.

    The ledger file spans the whole session, but the contract in README.md is
    evidence "this turn". Records written before the most recent turn-boundary
    marker belong to an earlier turn and must NOT vouch for the current final
    response -- otherwise turn 1's successful `pytest -q` silently supports a
    turn-2 "Tests pass." that ran no tests at all.
    """
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
                    rec = json.loads(line)
                except Exception:
                    continue
                if not isinstance(rec, dict):
                    continue
                if rec.get(TURN_BOUNDARY_KEY) is True:
                    # A turn closed here; everything before it is stale evidence.
                    records.clear()
                    continue
                records.append(rec)
    except Exception:
        pass
    return records


def _close_turn(session_id: str) -> None:
    """Append the turn-boundary marker. Best-effort; never raises.

    Stop IS the turn boundary, so this runs on every non-continuation Stop --
    including the silent paths (no claims fired, no transcript) and the
    CLAIM_GUARD_MODE=block escalation that returns 2. If it only ran when a
    warning was emitted, a quiet turn would leave its receipts live for the
    next turn to consume, which is the exact defect being fixed.
    """
    try:
        path = _ledger_file(session_id)
        if not path.exists():
            return  # nothing was recorded this turn; no boundary to close
        with path.open("a", encoding="utf-8", errors="replace") as fh:
            fh.write(json.dumps({TURN_BOUNDARY_KEY: True}) + "\n")
    except Exception:
        pass


def _has_support(category: str, ledger: list[dict]) -> bool:
    """
    Return True if the ledger contains a successful command that supports the claim.

    For generic categories (fixed, all_green, no_errors), ANY ok=true command counts.
    For specific categories, the command must match one of the category's command patterns.
    """
    ok_records = [r for r in ledger if r.get("ok") is True]
    if not ok_records:
        return False

    # G1 — `functional` has a HIGHER, EXTERNAL bar: satisfied ONLY by an ok=true
    # command matching an e2e / acceptance signature, never by the generic
    # "any ok=true command" path (a unit-test pass is not acceptance evidence).
    if category == "functional":
        sigs = _e2e_signatures()
        for record in ok_records:
            cmd = (record.get("cmd") or "").lower()
            if any(s in cmd for s in sigs):
                return True
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
                                if (
                                    isinstance(block, dict)
                                    and block.get("type") == "text"
                                ):
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
        "tests": "tests pass",
        "build": "build succeeds",
        "lint": "lint passes",
        "coverage": "coverage met",
        "fixed": "issue fixed",
        "all_green": "all green",
        "no_errors": "no errors",
        "ci_gates": "CI gates green / ready to merge",
        "functional": "app works / functional",
    }
    claim_list = ", ".join(f'"{labels.get(c, c)}"' for c in unsupported)
    msg = (
        f"[Claim-Guard] Unverified success claim(s) detected: {claim_list}. "
        f"No successful supporting command was found in the Bash ledger this turn. "
        f"Please run the relevant commands (tests, build, lint, etc.) and verify "
        f"before asserting these outcomes."
    )
    if "functional" in unsupported:
        # Name the gap explicitly: a functional/'works' claim needs external
        # end-to-end evidence, not just a unit-test pass.
        msg += (
            " A functional/'works' claim needs a held-out golden-journey / e2e / "
            "acceptance run this turn (an ok=true e2e command) — a plain unit-test "
            "pass does NOT satisfy it."
        )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "Stop",
                    "additionalContext": msg,
                }
            }
        )
    )


def _block_message() -> str:
    """Stderr message for CLAIM_GUARD_MODE=block on an unsupported functional claim."""
    return (
        "[Claim-Guard] BLOCKED (CLAIM_GUARD_MODE=block): a functional / 'it works' "
        "claim was made with no held-out golden-journey / e2e / acceptance run in "
        "the Bash ledger this turn. Run a real end-to-end acceptance check "
        "(e.g. playwright / an *e2e* / *golden-journey* command) that exits 0, or "
        "remove the 'it works' claim, before finishing.\n"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    # Mode gate
    if MODE == "off":
        return 0

    # BLOCK mode is handled narrowly at the tail of the evidence check (only an
    # unsupported `functional` claim exits 2). warn/off never block.

    try:
        raw = sys.stdin.read() or "{}"
        data = json.loads(raw)
    except Exception:
        return 0  # fail-open: malformed stdin

    if not isinstance(data, dict):
        return 0  # fail-open: stdin parsed to a non-object (e.g. a bare list)

    # Read BEFORE the anti-loop guard: the `finally` below needs the real session
    # id on every exit path, including the early returns inside the try.
    session_id = str(data.get("session_id") or "unknown")
    in_continuation = bool(data.get("stop_hook_active"))

    try:
        # Anti-loop guard: if we're already inside a stop-hook continuation, do
        # nothing. No boundary is written here either: the continuation is still
        # the SAME turn, and closing it would strand the turn's own receipts.
        if in_continuation:
            return 0
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

        # BLOCK is narrow: only an UNSUPPORTED functional claim, only under
        # CLAIM_GUARD_MODE=block. Every other category — and warn/off mode — stays a
        # non-blocking warning, so nothing that worked before starts blocking now.
        if MODE == "block" and "functional" in unsupported:
            sys.stderr.write(_block_message())
            return 2

        # Emit one combined warning (exit 0)
        _inject_warning(unsupported)

    except Exception:
        pass  # fail-open: any logic error → silent exit 0
    finally:
        # Stop IS the turn boundary. Close it on EVERY path past the
        # stop_hook_active guard -- including the early returns and the block
        # escalation -- because a turn that made no claim still consumed its
        # receipts.
        if not in_continuation:
            _close_turn(session_id)

    return 0


if __name__ == "__main__":
    sys.exit(main())
