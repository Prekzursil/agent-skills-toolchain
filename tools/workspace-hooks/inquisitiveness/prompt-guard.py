#!/usr/bin/env python
"""UserPromptSubmit hook — inquisitiveness guard (EVPI-gated, pre-execution only).

Design rationale (from workspace-knowledge-base.md + design-v1.md):
- A UserPromptSubmit hook CANNOT call AskUserQuestion (synchronous transform, 30s limit).
  It can ONLY inject additionalContext text that ROUTES the agent to a skill that asks.
- Mid-execution clarification amplifies prompt-injection 15-16x (ASPI); inquisitiveness
  must be PRE-EXECUTION ONLY, EVPI-gated (only when genuinely vague/ambiguous).
- A '*' prefix in the prompt is the bypass sentinel for already-clarified rephrases.
- Heavy blocking makes the agent evade; this hook NEVER blocks (always exit 0).
- Fail-open: any error → silent exit 0 (must never crash a session).

Wire spec:
  Event:   UserPromptSubmit
  Command: python C:/Users/Prekzursil/.claude/hooks/inquisitiveness/prompt-guard.py
  Stdin:   {"prompt": "...", "cwd": "...", ...}
  Stdout (when vague): JSON {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                               "additionalContext": "<guidance>"}}
  Stdout (when clear): (empty — no output)
  Exit:    always 0
"""
from __future__ import annotations

import json
import re
import sys

# ---------------------------------------------------------------------------
# Vague-verb and pronoun lists (cheap heuristics — no dependencies)
# ---------------------------------------------------------------------------
VAGUE_VERBS = frozenset([
    "fix", "improve", "better", "make", "update", "change", "refactor",
    "clean", "optimize", "enhance", "adjust", "tweak", "rework", "redo",
])

VAGUE_PRONOUNS = frozenset(["it", "that", "this", "them", "these", "those", "everything"])

# Tokens that indicate concreteness — their presence reduces vagueness score
CONCRETE_TOKENS = re.compile(
    r"(https?://|/[a-zA-Z]|\\[a-zA-Z]|\.[a-z]{2,5}\b|"          # URL or path
    r"line\s+\d+|:\d+|file\s+\w|class\s+\w|function\s+\w|"       # code ref
    r"error|traceback|exception|raise|import|def |class |return|" # error/code kw
    r"\btest\b|\bspec\b|\bpr\b|\bissue\b|\bbug\b)",               # task tokens
    re.IGNORECASE,
)

# Minimum word count below which a prompt is considered suspiciously short
SHORT_WORD_THRESHOLD = 8

# Score thresholds
VAGUE_SCORE_THRESHOLD = 3  # must hit at least 3 vagueness signals


def _vagueness_score(prompt: str) -> int:
    """Return an integer vagueness score. Higher = more vague."""
    words = prompt.lower().split()
    word_count = len(words)
    score = 0

    # Signal 1: very short prompt
    if word_count < SHORT_WORD_THRESHOLD:
        score += 2
    elif word_count < 12:
        score += 1

    # Signal 2: contains a vague verb
    for w in words:
        clean = re.sub(r"[^a-z]", "", w)
        if clean in VAGUE_VERBS:
            score += 2
            break

    # Signal 3: pronoun with no likely referent (no concrete token nearby)
    has_pronoun = any(re.sub(r"[^a-z]", "", w) in VAGUE_PRONOUNS for w in words)
    if has_pronoun:
        score += 1

    # Signal 4: no concrete path/error/URL/code token
    if not CONCRETE_TOKENS.search(prompt):
        score += 1

    # Concrete tokens heavily reduce score (clear specificity)
    concrete_hits = len(CONCRETE_TOKENS.findall(prompt))
    if concrete_hits >= 2:
        score -= 3
    elif concrete_hits == 1:
        score -= 1

    # A longer prompt with technical words is rarely vague enough to intervene
    if word_count >= 20:
        score -= 2

    return score


def _guidance(prompt: str) -> str:
    return (
        "**[Inquisitiveness Guard — pre-execution check]**\n"
        "Before editing any files, do the following:\n"
        "1. Restate your understanding of the user's goal in ONE sentence.\n"
        "2. If material ambiguity remains after that restatement — i.e., there are "
        "two or more meaningfully different ways to interpret the request — invoke "
        "the `clarify-requirements` skill and use `AskUserQuestion` to ask 1-3 "
        "focused, grounded questions. Keep questions mutually exclusive; do not ask "
        "about things you can infer from the codebase.\n"
        "3. Only proceed with implementation AFTER the goal is unambiguous OR after "
        "confirming there is no remaining ambiguity worth asking about.\n"
        "Note: a prompt beginning with '*' bypasses this check entirely."
    )


def main() -> int:
    try:
        raw = sys.stdin.read() or "{}"
        data = json.loads(raw)
    except Exception:
        return 0  # fail-open: malformed stdin → do nothing

    try:
        prompt = str(data.get("prompt") or "").strip()

        # '*' prefix = explicit bypass (user already clarified or is rephrasing)
        if prompt.startswith("*"):
            return 0

        score = _vagueness_score(prompt)
        if score >= VAGUE_SCORE_THRESHOLD:
            guidance = _guidance(prompt)
            payload = {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": guidance,
                }
            }
            print(json.dumps(payload))
    except Exception:
        pass  # fail-open: never crash a session

    return 0


if __name__ == "__main__":
    sys.exit(main())
