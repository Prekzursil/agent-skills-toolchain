#!/usr/bin/env python
"""Shared prompt-injection grammar for the harness (gems D2 + B1).

ONE canonical list of injection-grammar regexes so two consumers agree on what
"injection" looks like instead of maintaining divergent copies:

  * D2 - the untrusted-tool-result injection tripwire (runtime, modules.py):
    scans content-ingesting tool RESULTS (WebFetch / search-hub / pdf-reader /
    markitdown / RE string dumps). Those are UNTRUSTED, so D2 uses the FULL
    grammar - directive AND payload (exec / exfil).

  * B1 - the recall-index `poisoned` pre-scan (index-time, recall_index.py):
    scans the owner's OWN vault notes. A "poisoned memory" is one that tries to
    STEER the agent when recalled, so B1 scopes to the DIRECTIVE categories.
    Payload grammar (a `curl ... | sh` one-liner, `subprocess.run(`) is ordinary
    DOCUMENTATION inside a trusted note and must NOT hide it from recall.

Both import `INJECTION_PATTERNS` from here, so the grammar cannot drift between
them (share the list -> they agree). Category scoping is the only difference.

Fail-open by contract: `looks_poisoned` / `scan` never raise - a scan error or a
non-string input returns the empty / False result so the ingesting pipeline keeps
working. The redaction / quarantine layer, not this heuristic, is the guardrail
(D2 mandate; AGENTS.md section 6 fail-open). Seeded from the Lasso / OWASP
LLM-Prompt-Injection corpus (a representative subset; extend HERE and both
consumers inherit it).
"""
from __future__ import annotations

import re
from typing import Iterable, Pattern

# Category tags. A poisoned MEMORY is a DIRECTIVE aimed at the agent; PAYLOAD
# (exec / exfil) grammar is a threat in an untrusted tool RESULT but is benign
# documentation in the owner's trusted vault.
CATEGORY_DIRECTIVE = "directive"
CATEGORY_PAYLOAD = "payload"

# The category subset B1 uses for the recall `poisoned` flag (trusted vault):
# only agent-steering grammar counts, never documented shell commands.
DIRECTIVE_CATEGORIES: tuple[str, ...] = (CATEGORY_DIRECTIVE,)

# Each entry: (reason_code, category, compiled pattern). reason_code is STABLE
# so D2 can render a per-match quarantine banner and B1 can log which grammar
# tripped. Patterns are compiled with re.I (and re.M where line-anchored) via the
# flags argument - NO inline `(?i)` mid-pattern (Python rejects non-leading
# global flags).
INJECTION_PATTERNS: tuple[tuple[str, str, Pattern[str]], ...] = (
    # --- DIRECTIVE: instruction-override / role-spoof / jailbreak / exfil-ask ---
    (
        "ignore_prior",
        CATEGORY_DIRECTIVE,
        re.compile(
            r"\b(?:ignore|disregard|forget|override|do\s+not\s+follow)\b"
            r"[\s\S]{0,40}?\b(?:previous|prior|above|earlier|preceding|foregoing|all|any)\b"
            r"[\s\S]{0,30}?\b(?:instruction|prompt|rule|direction|directive|context|guideline|message|command)s?\b",
            re.I,
        ),
    ),
    (
        "new_instructions",
        CATEGORY_DIRECTIVE,
        re.compile(
            r"\b(?:here\s+are\s+(?:the\s+)?)?(?:new|updated|revised|real|actual|true|corrected)\b"
            r"[\s\S]{0,20}?\binstructions?\b\s*[:\-]",
            re.I,
        ),
    ),
    (
        "role_tag",
        CATEGORY_DIRECTIVE,
        re.compile(r"<\s*/?\s*\|?\s*(?:system|assistant|user|im_start|im_end)\b", re.I),
    ),
    (
        "act_as",
        CATEGORY_DIRECTIVE,
        re.compile(
            r"\b(?:you\s+are\s+now|from\s+now\s+on\s+you|pretend\s+(?:to\s+be|that\s+you)"
            r"|act\s+as|roleplay\s+as|behave\s+as|imagine\s+you\s+are)\b",
            re.I,
        ),
    ),
    (
        "jailbreak_persona",
        CATEGORY_DIRECTIVE,
        re.compile(
            r"\b(?:developer\s+mode|jailbreak|do\s+anything\s+now|unfiltered\s+mode"
            r"|sudo\s+mode|god\s+mode)\b|\bDAN\b",
            re.I,
        ),
    ),
    (
        "reveal_secret",
        CATEGORY_DIRECTIVE,
        re.compile(
            r"\b(?:reveal|print|show|repeat|output|disclose|leak|dump|send|exfiltrate)\b"
            r"[\s\S]{0,40}?\b(?:your\s+)?(?:system\s+prompt|initial\s+instructions"
            r"|these\s+instructions|the\s+prompt|api[\s_-]?keys?|access[\s_-]?keys?"
            r"|secrets?|passwords?|credentials?|tokens?)\b",
            re.I,
        ),
    ),
    (
        "tool_command",
        CATEGORY_DIRECTIVE,
        re.compile(
            r"\b(?:you\s+must|you\s+should|please|now|immediately)\b"
            r"[\s\S]{0,40}?\b(?:run|execute|call|invoke|issue)\b"
            r"[\s\S]{0,30}?\b(?:the\s+)?(?:following\s+)?(?:command|tool|function|shell|script)s?\b",
            re.I,
        ),
    ),
    (
        "injection_marker",
        CATEGORY_DIRECTIVE,
        re.compile(
            r"\b(?:begin|start|end\s+of)\b[\s\S]{0,20}?\b(?:prompt\s+injection|jailbreak"
            r"|system\s+(?:prompt|message))\b",
            re.I,
        ),
    ),
    # --- PAYLOAD: exec / exfil one-liners (untrusted RESULTS only, not vault) ---
    (
        "pipe_to_shell",
        CATEGORY_PAYLOAD,
        re.compile(
            r"\b(?:curl|wget|iwr|invoke-webrequest)\b[^\n|]{0,200}\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b",
            re.I,
        ),
    ),
    (
        "base64_exec",
        CATEGORY_PAYLOAD,
        re.compile(
            r"\bbase64\b[^\n|]{0,80}\|\s*(?:ba)?sh\b"
            r"|\b(?:powershell|pwsh)\b[^\n]{0,60}\s-e(?:nc(?:odedcommand)?)?\b",
            re.I,
        ),
    ),
    (
        "eval_exec",
        CATEGORY_PAYLOAD,
        re.compile(
            r"\b(?:eval|invoke-expression|iex|os\.system|subprocess\.(?:run|popen|call|check_output))\s*\(",
            re.I,
        ),
    ),
)


def _select(categories: Iterable[str] | None) -> tuple[tuple[str, str, Pattern[str]], ...]:
    if categories is None:
        return INJECTION_PATTERNS
    wanted = {str(c) for c in categories}
    return tuple(entry for entry in INJECTION_PATTERNS if entry[1] in wanted)


def looks_poisoned(text: object, *, categories: Iterable[str] | None = None) -> bool:
    """True when `text` carries injection grammar in any selected `categories`.

    `categories=None` scans the FULL grammar (D2 / untrusted results). Pass
    `DIRECTIVE_CATEGORIES` for the B1 trusted-vault `poisoned` flag. Fail-open:
    a non-string input or a scan error returns False (never raises)."""
    try:
        if not text or not isinstance(text, str):
            return False
        for _code, _category, pattern in _select(categories):
            if pattern.search(text):
                return True
        return False
    except Exception:
        return False


def scan(text: object, *, categories: Iterable[str] | None = None) -> list[str]:
    """Return the stable reason_codes of every selected pattern that matched.

    Bounded by the fixed pattern count; fail-open (empty list on error)."""
    hits: list[str] = []
    try:
        if not text or not isinstance(text, str):
            return hits
        for code, _category, pattern in _select(categories):
            if pattern.search(text):
                hits.append(code)
    except Exception:
        return hits
    return hits
