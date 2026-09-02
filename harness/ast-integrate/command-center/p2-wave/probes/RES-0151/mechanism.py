#!/usr/bin/env python3
"""Structured mechanism-key extraction for RES-0151 distinctness.

This is the catalog method (mechanism-level, not string equality). RES-0173's
artifact is absent on this worktree; planted mutants in controls.py are the
both-states proof that paraphrases collapse and true distinctions stay apart.
"""
from __future__ import annotations

import re

# Phrase folds applied before tokenization so paraphrases share a slot.
PHRASE_FOLDS: tuple[tuple[str, str], ...] = (
    ("unknown fields", "unknownfield"),
    ("unknown field", "unknownfield"),
    ("additional properties", "unknownfield"),
    ("unexpected keys", "unknownfield"),
    ("unexpected key", "unknownfield"),
    ("duplicate keys", "duplicatekey"),
    ("duplicate key", "duplicatekey"),
    ("last wins", "lastwins"),
    ("last-wins", "lastwins"),
    ("case distinct", "casedistinct"),
    ("case-distinct", "casedistinct"),
    ("ready units", "readyunits"),
    ("ready_units", "readyunits"),
    ("self test", "selftest"),
    ("auto deploy", "autodeploy"),
)

STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "to",
        "in",
        "on",
        "for",
        "and",
        "or",
        "is",
        "are",
        "be",
        "by",
        "with",
        "that",
        "this",
        "it",
        "as",
        "at",
        "from",
        "its",
        "their",
        "was",
        "were",
        "been",
        "being",
        "has",
        "have",
        "had",
        "do",
        "does",
        "did",
        "not",
        "no",
        "nor",
        "so",
        "if",
        "then",
        "than",
        "into",
        "over",
        "under",
        "via",
        "per",
        "vs",
        "versus",
        "will",
        "can",
        "must",
        "should",
        "may",
        "get",
        "gets",
        "got",
        "make",
        "makes",
        "made",
        "also",
        "only",
        "both",
        "each",
        "all",
        "any",
        "same",
        "such",
        "other",
        "own",
        "just",
        "more",
        "most",
        "very",
        "still",
        "already",
        "here",
        "there",
        "when",
        "where",
        "what",
        "which",
        "who",
        "how",
        "why",
        "after",
        "before",
        "between",
        "without",
        "within",
        "using",
        "used",
        "use",
        "one",
        "two",
        "new",
        "old",
        "true",
        "false",
        "value",
        "values",
        "done",
        "only",
    }
)

# Verb / predicate synonyms collapse to one action slot. Status words
# like "blocked" are NOT mapped; they would otherwise swallow every
# "BLOCKED artifact" mention into reject.
ACTION_MAP = {
    "reject": "reject",
    "rejects": "reject",
    "rejected": "reject",
    "refuse": "reject",
    "refuses": "reject",
    "refused": "reject",
    "error": "reject",
    "errors": "reject",
    "errored": "reject",
    "fail": "reject",
    "fails": "reject",
    "failed": "reject",
    "raise": "reject",
    "raises": "reject",
    "raised": "reject",
    "deny": "reject",
    "denies": "reject",
    "denied": "reject",
    "fire": "fire",
    "fires": "fire",
    "fired": "fire",
    "trigger": "fire",
    "triggers": "fire",
    "triggered": "fire",
    "activate": "fire",
    "trip": "fire",
    "silent": "silent",
    "quiet": "silent",
    "invalidate": "invalidate",
    "invalidates": "invalidate",
    "restore": "restore",
    "restores": "restore",
    "restored": "restore",
    "agree": "agree",
    "agrees": "agree",
    "collide": "collide",
    "collides": "collide",
    "hide": "hide",
    "hides": "hide",
    "mask": "hide",
    "bypass": "bypass",
    "skip": "bypass",
    "skips": "bypass",
    "collapse": "collapse",
    "collapses": "collapse",
    "merge": "collapse",
    "dedup": "collapse",
    "rank": "rank",
    "prove": "prove",
    "refute": "refute",
    "refuted": "refute",
    "confirm": "confirm",
    "confirmed": "confirm",
    "saturate": "saturate",
    "stop": "stop",
}


def _candidates(word: str) -> list[str]:
    out = [word]
    if word.endswith("ies") and len(word) > 5:
        out.append(word[:-3] + "y")
    if word.endswith("ing") and len(word) > 6:
        out.append(word[:-3])
        out.append(word[:-3] + "e")
    if word.endswith("ed") and len(word) > 5:
        out.append(word[:-2])
        out.append(word[:-1])
        out.append(word[:-2] + "e")
    if word.endswith("es") and len(word) > 4:
        out.append(word[:-2])
        out.append(word[:-1])
    if word.endswith("s") and not word.endswith("ss") and len(word) > 4:
        out.append(word[:-1])
    # unique, stable order
    seen: set[str] = set()
    uniq: list[str] = []
    for item in out:
        if item not in seen:
            seen.add(item)
            uniq.append(item)
    return uniq


def _canonical(word: str) -> str:
    for cand in _candidates(word):
        if cand in ACTION_MAP:
            return ACTION_MAP[cand]
    if word.endswith("ies") and len(word) > 5:
        return word[:-3] + "y"
    if word.endswith("ing") and len(word) > 6:
        return word[:-3]
    if word.endswith("ed") and len(word) > 5:
        return word[:-2]
    if word.endswith("es") and len(word) > 4:
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 4:
        return word[:-1]
    return word


def _fold_phrases(text: str) -> str:
    low = text.lower()
    for src, dst in PHRASE_FOLDS:
        low = low.replace(src, dst)
    return low


def content_tokens(text: str) -> list[str]:
    folded = _fold_phrases(text)
    raw = re.findall(r"[a-z0-9]+", folded)
    out: list[str] = []
    for tok in raw:
        if tok in STOP or tok.isdigit() or len(tok) < 3:
            continue
        stem = _canonical(tok)
        if stem in STOP or len(stem) < 3:
            continue
        out.append(stem)
    return out


def mechanism_key(text: str) -> str:
    """Return a structured key: action|sorted-content-stems."""
    tokens = content_tokens(text)
    action = "claim"
    rest: list[str] = []
    found_action = False
    for tok in tokens:
        mapped = ACTION_MAP.get(tok, tok)
        if not found_action and tok in ACTION_MAP:
            action = mapped
            found_action = True
            continue
        rest.append(mapped)
    content = "+".join(sorted(set(rest))) if rest else "empty"
    return f"{action}|{content}"


def jaccard(a: str, b: str) -> float:
    sa, sb = set(content_tokens(a)), set(content_tokens(b))
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / float(len(sa | sb))
