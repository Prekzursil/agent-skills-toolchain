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
  Command: python {{USER_HOME}}/.claude/hooks/inquisitiveness/prompt-guard.py
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
VAGUE_VERBS = frozenset(
    [
        "fix",
        "improve",
        "better",
        "make",
        "update",
        "change",
        "refactor",
        "clean",
        "optimize",
        "enhance",
        "adjust",
        "tweak",
        "rework",
        "redo",
    ]
)

VAGUE_PRONOUNS = frozenset(
    ["it", "that", "this", "them", "these", "those", "everything"]
)

# Tokens that indicate concreteness — their presence reduces vagueness score
CONCRETE_TOKENS = re.compile(
    r"(https?://|/[a-zA-Z]|\\[a-zA-Z]|\.[a-z]{2,5}\b|"  # URL or path
    r"line\s+\d+|:\d+|file\s+\w|class\s+\w|function\s+\w|"  # code ref
    r"error|traceback|exception|raise|import|def |class |return|"  # error/code kw
    r"\btest\b|\bspec\b|\bpr\b|\bissue\b|\bbug\b)",  # task tokens
    re.IGNORECASE,
)

# Case-SENSITIVE: named targets (CamelCase or ALL-CAPS words) signal a concrete object,
# not a vague verb loop. Compiled without IGNORECASE so "fix" doesn't match [A-Z]{2,}.
NAMED_TARGETS = re.compile(
    r"(\b[A-Z][a-z]+[A-Z]\w*\b|"  # CamelCase: UserService, AuthModule, UserController
    r"\b[A-Z]{2,}\b)"  # ALL-CAPS: README, CHANGELOG, API, URL, PR
)

# Minimum word count below which a prompt is considered suspiciously short
SHORT_WORD_THRESHOLD = 8

# Score thresholds
VAGUE_SCORE_THRESHOLD = 3  # must hit at least 3 vagueness signals
RECALL_WORD_THRESHOLD = (
    15  # prompts with >= this many words get a recall-first directive
)


def _vagueness_score(prompt: str) -> int:
    """Return an integer vagueness score. Higher = more vague.

    Conservative by design (EVPI): a prompt that names a concrete target (a path,
    code ref, error, or a CamelCase/ALL-CAPS identifier like README or UserService)
    is NOT the kind of vagueness that needs clarifying — it tells us what to act on.
    We only intervene on genuinely *targetless* vague requests ("fix it", "make it
    better"), so the guard fires rarely and never nags on reasonable prompts.
    """
    words = prompt.lower().split()
    word_count = len(words)

    # Hard gate: ANY concrete token or named target → the request has a clear object.
    # Return 0 (silent) — clarification would just be a rubber-stamp.
    if CONCRETE_TOKENS.search(prompt) or NAMED_TARGETS.search(prompt):
        return 0

    score = 0
    # Signal 1: very short prompt (no room to be specific)
    if word_count < SHORT_WORD_THRESHOLD:
        score += 2
    elif word_count < 12:
        score += 1

    # Signal 2: a vague action verb with no named object
    if any(re.sub(r"[^a-z]", "", w) in VAGUE_VERBS for w in words):
        score += 2

    # Signal 3: a floating pronoun with no referent ("fix it", "redo that")
    if any(re.sub(r"[^a-z]", "", w) in VAGUE_PRONOUNS for w in words):
        score += 1

    # A long prose request (even targetless) is rarely worth interrupting
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


def _recall_directive() -> str:
    return (
        "**[Recall-first]** Before proposing an approach or writing code for this task:\n"
        "1. Query `mcp__basic-memory__search_notes` on the key nouns of the request, and "
        "check `~/.claude/SELF-CALIBRATION-PLAN.md`, `~/.claude/WORKSPACE-CURATION.md`, and "
        "`MEMORY.md` for a prior solution — do NOT start from zero on a problem you may "
        "have already solved.\n"
        "2. If this is a known task TYPE, run the cheapest deterministic diagnostic FIRST "
        "(invoke the `simplest-probe-first` skill) before committing to an expensive path.\n"
        "3. State what prior art you found (or 'none') before fanning out agents or building."
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

        pieces = []
        if _vagueness_score(prompt) >= VAGUE_SCORE_THRESHOLD:
            pieces.append(_guidance(prompt))
        if len(prompt.split()) >= RECALL_WORD_THRESHOLD:
            pieces.append(_recall_directive())
        if pieces:
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "UserPromptSubmit",
                            "additionalContext": "\n\n".join(pieces),
                        }
                    }
                )
            )
    except Exception:
        pass  # fail-open: never crash a session

    return 0


if __name__ == "__main__":
    sys.exit(main())
