#!/usr/bin/env python3
"""Mechanical namespace resolver for AUD-0034.

Namespace assignment comes only from token rules. There is no LLM classifier.
A hit whose window carries no discriminating token is UNDECIDABLE and is
routed to authors — never guessed. LLM classification of a mechanical
comparison measured 86% accurate on this estate with 100% of errors pointing
at data loss.

Discriminating tokens (evidence_requirement): MECH, mechanism, option,
harness, mission-grade.

Verdicts:
    RESOLVES-ONE / RESOLVES-MANY / RESOLVES-NONE / UNDECIDABLE
    (MENTION is recorded for quoted-collision prose and is not a guess)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from constants import (
    CLASS_MANY,
    CLASS_MENTION,
    CLASS_NONE,
    CLASS_ONE,
    CLASS_UNDECIDABLE,
    MECH_IDS,
    MEANING,
    NS_MECH,
    NS_OPTION,
    NS_WAVE1,
    NS_WAVE3,
    OPTION_IDS,
    PRE_FIX_MECH_IDS,
)

TOKEN_RE = re.compile(r"\b(MECH|M)-(\d{1,4})\b")
DEFINING_HEADING_RE = re.compile(r"^#{1,3}\s+(M|MECH)-(\d{1,4})\b", re.IGNORECASE)
WORD_MECH = re.compile(r"\bmech(?:anism|anisms)?\b", re.IGNORECASE)
WORD_OPTION = re.compile(r"\boptions?\b", re.IGNORECASE)
WORD_HARNESS = re.compile(r"\b(?:research\s+)?harness\b|\bdeep-research\b|\bdeep research\b", re.IGNORECASE)
WORD_MISSION = re.compile(
    r"\bmission[-\s]grade(?:s)?\b|\bwave-1 register\b|\bwave1 register\b",
    re.IGNORECASE,
)

MENTION_MARKERS = (
    "collision",
    "namespaces share",
    "four m-nn",
    "re-prefixed",
    "re-prefix",
    "quoting the collision",
    "queued as p2-09",
    "still live (present tense)",
    "present tense",
)

WINDOW_CHARS = 180

OPTION_SET = set(OPTION_IDS)
MECH_SET = set(MECH_IDS)
PRE_FIX_MECH_SET = set(PRE_FIX_MECH_IDS)


def canonical(prefix: str, number: str) -> str:
    return f"{prefix.upper()}-{int(number)}"


def line_number(text: str, index: int) -> int:
    return text[:index].count("\n") + 1


def line_span(text: str, index: int) -> tuple[int, int]:
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    if end < 0:
        end = len(text)
    return start, end


def window_at(text: str, start: int, end: int) -> str:
    lo = max(0, start - WINDOW_CHARS)
    hi = min(len(text), end + WINDOW_CHARS)
    return text[lo:hi]


def posix_rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix().replace("\\", "/")


def file_role(rel: str) -> str:
    low = rel.replace("\\", "/").lower()
    name = Path(low).name
    if "07-option" in low:
        return "option-universe-defining"
    if "13-architecture" in low:
        return "architecture-defining"
    if "17-decision" in low:
        return "decision-log"
    if "16-grill" in low:
        return "doc-16"
    if "18-open-unknown" in low:
        return "doc-18"
    if "19-substance" in low:
        return "doc-19"
    if "pre-fix-option" in low:
        return "historical-option"
    if "pre-fix-mechanism" in low:
        return "historical-mechanism"
    if name == "register.md" and ("wave1" in low or "wave-1" in low):
        return "wave1-register"
    if "deep-research" in low or "deep_research" in low:
        return "wave3-skill"
    if "mention" in low:
        return "mention-doc"
    if "synthetic" in low:
        return "synthetic"
    if "absent-id" in low:
        return "absent"
    if "resolves-many" in low:
        return "dual-token"
    return "other"


def is_defining_line(line: str) -> bool:
    return bool(DEFINING_HEADING_RE.match(line.strip()))


def is_mention_window(window: str, role: str) -> bool:
    blob = window.lower()
    if role in {"mention-doc", "decision-log"}:
        return True
    return any(m in blob for m in MENTION_MARKERS)


def declared_namespaces(token: str) -> list[str]:
    """Which declaring registries contain a card for this literal token."""
    found: list[str] = []
    if token in OPTION_SET:
        found.append(NS_OPTION)
    if token in MECH_SET or token in PRE_FIX_MECH_SET:
        found.append(NS_MECH)
    if token == "M-16":
        found.append(NS_WAVE3)
    if token in {"M-1", "M-3"}:
        found.append(NS_WAVE1)
    return found


def candidate_pair(token: str) -> list[dict]:
    """Two (or more) candidate meanings printed side by side. Never a guess."""
    rows = []
    for ns in declared_namespaces(token):
        rows.append(
            {
                "namespace": ns,
                "meaning": MEANING[ns],
                "id_in_that_namespace": (
                    token.replace("M-", "MECH-", 1) if ns == NS_MECH and token.startswith("M-") else token
                ),
            }
        )
    if not rows:
        rows.append(
            {
                "namespace": None,
                "meaning": "no declaring registry contains this id",
                "id_in_that_namespace": token,
            }
        )
    return rows


def token_hits_in_window(window: str) -> dict[str, bool]:
    return {
        "mech": bool(WORD_MECH.search(window)),
        "option": bool(WORD_OPTION.search(window)),
        "harness": bool(WORD_HARNESS.search(window)),
        "mission_grade": bool(WORD_MISSION.search(window)),
    }


def classify_hit(
    *,
    prefix: str,
    number: str,
    rel: str,
    line: str,
    window: str,
    role: str,
) -> dict:
    token = canonical(prefix, number)
    prefix_u = prefix.upper()
    defining = is_defining_line(line)
    flags = token_hits_in_window(window)
    declared = declared_namespaces(token)

    # Rule 1: disjoint MECH- prefix. Never a bare M-NN. No adjudication.
    if prefix_u == "MECH":
        return {
            "classification": CLASS_ONE,
            "namespace": NS_MECH,
            "resolved_meaning": MEANING[NS_MECH],
            "confidence": "token-rule",
            "adjudicated": False,
            "rule": "prefix-MECH",
            "candidates": [
                {
                    "namespace": NS_MECH,
                    "meaning": MEANING[NS_MECH],
                    "id_in_that_namespace": token,
                }
            ],
        }

    # Rule 2: use-vs-mention. Quoting the collision is not a binding.
    if (not defining) and is_mention_window(window, role) and role not in {
        "historical-option",
        "historical-mechanism",
        "doc-16",
        "doc-18",
        "doc-19",
        "synthetic",
        "absent",
        "dual-token",
    }:
        return {
            "classification": CLASS_MENTION,
            "namespace": None,
            "resolved_meaning": None,
            "confidence": "use-vs-mention",
            "adjudicated": False,
            "rule": "mention-markers",
            "candidates": candidate_pair(token),
        }

    fired: list[str] = []
    if flags["harness"] and token == "M-16":
        fired.append(NS_WAVE3)
    if flags["mission_grade"] and token in {"M-1", "M-3"}:
        fired.append(NS_WAVE1)
    if flags["option"] or defining and role in {"option-universe-defining", "historical-option"}:
        fired.append(NS_OPTION)
    if flags["mech"] or defining and role in {"architecture-defining", "historical-mechanism"}:
        fired.append(NS_MECH)
    if role == "wave3-skill" and token == "M-16":
        fired.append(NS_WAVE3)
    if role == "wave1-register" and token in {"M-1", "M-3"}:
        fired.append(NS_WAVE1)

    # Preserve order, unique.
    seen: list[str] = []
    for ns in fired:
        if ns not in seen:
            seen.append(ns)

    if len(seen) == 1:
        ns = seen[0]
        return {
            "classification": CLASS_ONE,
            "namespace": ns,
            "resolved_meaning": MEANING[ns],
            "confidence": "token-rule",
            "adjudicated": False,
            "rule": "discriminating-token",
            "candidates": [
                {
                    "namespace": ns,
                    "meaning": MEANING[ns],
                    "id_in_that_namespace": (
                        token.replace("M-", "MECH-", 1) if ns == NS_MECH else token
                    ),
                }
            ],
        }

    if len(seen) > 1:
        return {
            "classification": CLASS_MANY,
            "namespace": None,
            "resolved_meaning": None,
            "confidence": "multiple-discriminators",
            "adjudicated": False,
            "rule": "multiple-discriminating-tokens",
            "candidates": [
                {
                    "namespace": ns,
                    "meaning": MEANING[ns],
                    "id_in_that_namespace": (
                        token.replace("M-", "MECH-", 1) if ns == NS_MECH else token
                    ),
                }
                for ns in seen
            ],
        }

    # No discriminating token.
    if not declared:
        return {
            "classification": CLASS_NONE,
            "namespace": None,
            "resolved_meaning": None,
            "confidence": "none",
            "adjudicated": False,
            "rule": "no-declaring-registry",
            "candidates": candidate_pair(token),
        }

    if len(declared) == 1:
        ns = declared[0]
        # A unique declaring registry with no window token is still a guess
        # when the token is the historically overloaded M- prefix. Only MECH-
        # (already handled) and ids outside the collision set may resolve
        # from registry membership alone. M-34..M-38 exist only as pre-fix
        # mechanism cards; without a token they stay UNDECIDABLE rather than
        # being guessed into the mechanism namespace.
        return {
            "classification": CLASS_UNDECIDABLE,
            "namespace": None,
            "resolved_meaning": None,
            "confidence": "none",
            "adjudicated": False,
            "rule": "no-discriminating-token",
            "author_route": True,
            "candidates": candidate_pair(token),
        }

    return {
        "classification": CLASS_UNDECIDABLE,
        "namespace": None,
        "resolved_meaning": None,
        "confidence": "none",
        "adjudicated": False,
        "rule": "no-discriminating-token",
        "author_route": True,
        "candidates": candidate_pair(token),
    }


def extract_hits(text: str, rel: str) -> list[dict]:
    role = file_role(rel)
    hits: list[dict] = []
    for match in TOKEN_RE.finditer(text):
        prefix, number = match.group(1), match.group(2)
        start, end = match.span()
        ls, le = line_span(text, start)
        line = text[ls:le]
        window = window_at(text, start, end)
        verdict = classify_hit(
            prefix=prefix,
            number=number,
            rel=rel,
            line=line,
            window=window,
            role=role,
        )
        hits.append(
            {
                "id": canonical(prefix, number),
                "raw": match.group(0),
                "artifact": rel,
                "line": line_number(text, start),
                "snippet": line.strip()[:240],
                "window": " ".join(window.split())[:360],
                "role": role,
                "defining_site": is_defining_line(line),
                "discriminators": token_hits_in_window(window),
                **verdict,
            }
        )
    return hits


def scan_file(path: Path, root: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return extract_hits(text, posix_rel(path, root))


def scan_tree(root: Path, *, skip_parts: Iterable[str] = ()) -> list[dict]:
    skip = {s.replace("\\", "/").lower() for s in skip_parts}
    hits: list[dict] = []
    if not root.is_dir():
        return hits
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".json", ".txt"}:
            continue
        rel = posix_rel(path, root)
        low = rel.lower()
        if any(s in low for s in skip):
            continue
        hits.extend(extract_hits(path.read_text(encoding="utf-8"), rel))
    return hits


def count_mech_tokens(text: str) -> dict:
    token_hits = [
        m.group(0) for m in TOKEN_RE.finditer(text) if m.group(1).upper() == "MECH"
    ]
    bare_word = re.findall(r"\bMECH\b", text)
    return {
        "mech_nn_tokens": len(token_hits),
        "bare_MECH_word": len(bare_word),
        "total": len(token_hits) + len(bare_word),
        "samples": token_hits[:8],
    }


def present_tense_collision(text: str) -> bool:
    low = text.lower()
    present = (
        "is still" in low
        or "still live" in low
        or "is live" in low
        or "queued as p2-09" in low
    )
    return "collision" in low and present
