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


# --------------------------------------------------------------------------- calibrated-silence
# Fail-open shim: every proactive interjection is SDT-gated by should_interject(). ANY error
# (gate missing, corrupt ledger, bad input) returns ALLOW — suppression is the dangerous
# failure, so we never let the gate silence a turn by crashing.
def _cs_allow(itype, ctx):
    try:
        import sys as _s
        from pathlib import Path as _P

        _s.path.insert(
            0, str(_P(__file__).resolve().parent.parent / "calibrated-silence")
        )
        import calibrated_silence as _c

        return _c.should_interject(itype, ctx)[0]
    except Exception:
        return True


def _cs_record(itype, ck, sid):
    try:
        import calibrated_silence as _c

        _c.record_interjection(itype, ck, sid)
    except Exception:
        pass


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

# ToolUniverse-first router: fire ONLY on UNAMBIGUOUS biomedical/scientific terms (proper-noun
# DBs + bio-specific tokens) so it never nags on code tasks (no bare "structure"/"target"/"string").
# Supplies the external signal (which TU tools exist) + routes to the index — NOT an "are you sure?".
TU_STRONG_RE = re.compile(
    r"\b("
    r"pubmed|openalex|crossref|pubtator|europepmc|"
    r"smiles|inchi|pubchem|chembl|chebi|opsin|unichem|"
    r"gtopdb|guide.?to.?pharmacology|bindingdb|dgidb|pharos|opentargets|"
    r"uniprot|alphafold|pdbe|rcsb|foldseek|interpro|swissmodel|esmfold|"
    r"admet|admetai|swissadme|aopwiki|"
    r"faers|openfda|dailymed|pharmacovigilance|boxed.warning|"
    r"clinvar|gnomad|dbsnp|ensembl|alphamissense|spliceai|"
    r"mondo|hgnc|"
    r"gtex|depmap|cbioportal|protein.atlas|"
    r"enrichr|g:?profiler|msigdb|omnipath|reactome|kegg|signor|"
    r"ic50|ec50|binding.affinit|drug.gene.interaction|"
    r"clinical.trial|nct\d|"
    r"blood.brain.barrier|druglik|lipinski"
    r")\b",
    re.IGNORECASE,
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


def _tu_directive() -> str:
    return (
        "**[ToolUniverse-first]** This is a biomedical/scientific query and ToolUniverse "
        "(2,526 tools / 12 domains, live via `mcp__tooluniverse__find_tools`) very likely has a "
        "primary-source tool for it. BEFORE web-searching:\n"
        "1. Check `~/.claude/TU-MODULE-INDEX.md` for the matching module + its real tool names.\n"
        "2. Call `mcp__tooluniverse__find_tools` / `grep_tools` then `execute_tool` for the data "
        "(pull abbreviated names verbatim from `list_tools` — never guess).\n"
        "3. Web search is the FALLBACK only. If a TU tool is down, record it once (no retry-loop) "
        "and use the module's documented fallback in the index."
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

        sid = str(data.get("session_id") or "default")
        ctx = {"prompt": prompt, "session_id": sid}

        # Each lane is an independent interjection type, SDT-gated + recorded when surfaced.
        pieces = []
        if _vagueness_score(prompt) >= VAGUE_SCORE_THRESHOLD and _cs_allow(
            "question", ctx
        ):
            pieces.append(_guidance(prompt))
            _cs_record("question", "skill:clarify-requirements", sid)
        if len(prompt.split()) >= RECALL_WORD_THRESHOLD and _cs_allow(
            "suggestion", ctx
        ):
            pieces.append(_recall_directive())
            _cs_record("suggestion", "mcp:basic-memory", sid)
        if TU_STRONG_RE.search(prompt) and _cs_allow("route", ctx):
            pieces.append(_tu_directive())
            _cs_record("route", "mcp:tooluniverse", sid)
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
