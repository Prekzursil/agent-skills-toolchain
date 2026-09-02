"""Option-id namespace resolver for SYN-0005.

Bare M-NN is ambiguous across four namespaces named by CC-0021. This
resolver does not guess: a bare M-NN is REJECTED until a disjoint prefix
is supplied. command-center/OPTION-ID-RESOLUTION.json is absent on this
worktree; the namespace table is derived from the CC-0021 catalog entry.
"""
from __future__ import annotations

import re

# CC-0021, command-center/WORK-UNIT-CATALOG.json: four M-NN namespaces.
NAMESPACES = (
    {
        "id": "option-universe-family-M",
        "prefix": "OPT-M-",
        "bare": "M-",
        "note": "07-OPTION-UNIVERSE family M (33 ids)",
    },
    {
        "id": "architecture-candidates",
        "prefix": "MECH-",
        "bare": "M-",
        "note": "13-ARCHITECTURE-CANDIDATES mechanisms; re-prefixed MECH-NN on 2026-08-07",
    },
    {
        "id": "wave3-research-harness",
        "prefix": "WAVE3-M-",
        "bare": "M-",
        "note": "wave3 deep-research SKILL.md Research Harness (M-16)",
    },
    {
        "id": "wave1-mission-grade",
        "prefix": "WAVE1-M-",
        "bare": "M-",
        "note": "wave1/REGISTER.md single-digit M-1/M-3",
    },
)

# Prefixes with a single declaring registry on this estate (not M).
UNIQUE_OPTION = {
    "A": "option-universe-family-A",
    "C": "option-universe-family-C",
    "I": "option-universe-family-I",
    "J": "option-universe-family-J",
    "RT": "option-universe-family-RT",
}

# Program-B numbering collides with option-universe family B at B3/B4/B5 (OQ-7).
PROGRAM_B_CLASH = frozenset({"B-3", "B-4", "B-5", "B3", "B4", "B5"})

TOKEN_RE = re.compile(r"\b((?:WAVE3-M|WAVE1-M|MECH|OQ|RT|[A-Z])-?\d{1,4})\b")
HYPHEN_TOKEN_RE = re.compile(r"\b([A-Z]{1,5}-\d{1,4})\b")
BARE_M_RE = re.compile(r"^M-\d+$")
MECH_RE = re.compile(r"^MECH-\d+$")
WAVE3_RE = re.compile(r"^WAVE3-M-\d+$")
WAVE1_RE = re.compile(r"^WAVE1-M-\d+$")
OQ_RE = re.compile(r"^OQ-\d+$")
Q_RE = re.compile(r"^Q\d+$")
UNIT_RE = re.compile(r"^[A-Z]{2,5}-\d{4}$")
REG_ITEM_RE = re.compile(r"^R-[A-Z]\d{2}$")


def extract_tokens(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for rx in (HYPHEN_TOKEN_RE, TOKEN_RE, Q_RE):
        for tok in rx.findall(text or ""):
            if tok not in seen:
                seen.add(tok)
                found.append(tok)
    return found


def resolve(token: str) -> dict:
    tok = (token or "").strip()
    if not tok:
        return {
            "token": tok,
            "status": "UNRESOLVED",
            "namespace": None,
            "classification": None,
            "reason": "empty-token",
        }
    if UNIT_RE.match(tok) or REG_ITEM_RE.match(tok):
        return {
            "token": tok,
            "status": "RESOLVED",
            "namespace": "work-unit-or-register-item",
            "classification": None,
            "kind": "unit-id",
            "reason": "unit-id-not-option",
        }
    if Q_RE.match(tok) or OQ_RE.match(tok):
        return {
            "token": tok,
            "status": "RESOLVED",
            "namespace": "owner-question",
            "classification": None,
            "kind": "decision-id",
            "reason": "owner-question-id",
        }
    if BARE_M_RE.match(tok):
        return {
            "token": tok,
            "status": "REJECTED",
            "namespace": None,
            "classification": "ambiguous-option-token",
            "kind": "option-id",
            "reason": (
                "bare M-NN is ambiguous across four namespaces "
                "(option-universe-family-M, architecture-candidates, "
                "wave3-research-harness, wave1-mission-grade); "
                "supply MECH- / WAVE3-M- / WAVE1-M- / OPT-M- first"
            ),
        }
    if tok in PROGRAM_B_CLASH:
        return {
            "token": tok,
            "status": "REJECTED",
            "namespace": None,
            "classification": "ambiguous-option-token",
            "kind": "option-id",
            "reason": (
                "B3/B4/B5 collide between Program-B numbering and "
                "option-universe family B (OQ-7); rejected until namespaced"
            ),
        }
    if MECH_RE.match(tok):
        return {
            "token": tok,
            "status": "RESOLVED",
            "namespace": "architecture-candidates",
            "classification": None,
            "kind": "option-id",
            "reason": "MECH-NN prefix is the post-2026-08-07 architecture namespace",
        }
    if WAVE3_RE.match(tok):
        return {
            "token": tok,
            "status": "RESOLVED",
            "namespace": "wave3-research-harness",
            "classification": None,
            "kind": "option-id",
            "reason": "WAVE3-M- prefix selects the research-harness namespace",
        }
    if WAVE1_RE.match(tok):
        return {
            "token": tok,
            "status": "RESOLVED",
            "namespace": "wave1-mission-grade",
            "classification": None,
            "kind": "option-id",
            "reason": "WAVE1-M- prefix selects the wave1 mission-grade namespace",
        }
    if tok.startswith("OPT-M-"):
        return {
            "token": tok,
            "status": "RESOLVED",
            "namespace": "option-universe-family-M",
            "classification": None,
            "kind": "option-id",
            "reason": "OPT-M- is the disjoint option-universe family-M prefix",
        }
    m = re.match(r"^([A-Z]{1,5})-(\d+)$", tok)
    if m:
        prefix, _num = m.group(1), m.group(2)
        if prefix == "B":
            return {
                "token": tok,
                "status": "RESOLVED",
                "namespace": "option-universe-family-B",
                "classification": None,
                "kind": "option-id",
                "reason": (
                    "two-digit B-NN treated as option-universe family B; "
                    "B3/B4/B5 remain rejected (OQ-7)"
                ),
            }
        ns = UNIQUE_OPTION.get(prefix)
        if ns:
            return {
                "token": tok,
                "status": "RESOLVED",
                "namespace": ns,
                "classification": None,
                "kind": "option-id",
                "reason": f"prefix {prefix}- has a single declaring registry on this estate",
            }
    return {
        "token": tok,
        "status": "UNRESOLVED",
        "namespace": None,
        "classification": None,
        "kind": "unknown",
        "reason": "no declaring registry for this prefix on this worktree",
    }
