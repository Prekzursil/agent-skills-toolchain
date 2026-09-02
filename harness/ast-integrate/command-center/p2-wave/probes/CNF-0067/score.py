#!/usr/bin/env python3
"""Mechanical Jaccard score + independent load-bearing-slot verdict.

The two signals are mechanically different:
  * mechanical: token-set Jaccard on the raw mechanism strings
  * independent: equality of a folded load-bearing signature (verdict words,
    field names, and meaning-changing qualifiers)

A one-parameter fork shares most tokens (high Jaccard) but changes a
load-bearing slot (independent DISTINCT). A full rewrite of the same
mechanism can sit in the low-Jaccard band (mechanical DISTINCT) while
the signatures still match (independent DUPLICATE).
"""
from __future__ import annotations

import re
from typing import Iterable

MECHANICAL_DUP_THRESHOLD = 0.50

STOP = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "by",
        "for",
        "with",
        "that",
        "this",
        "any",
        "must",
        "be",
        "is",
        "are",
        "as",
        "in",
        "on",
        "at",
        "from",
        "plus",
        "rather",
        "than",
        "because",
        "whose",
        "only",
        "after",
        "before",
        "same",
        "using",
        "over",
        "into",
        "not",
        "do",
        "does",
        "can",
        "each",
        "its",
        "no",
        "it",
        "if",
        "was",
        "were",
        "has",
        "have",
        "been",
        "among",
        "left",
        "one",
        "other",
        "nothing",
        "hands",
        "confirmer",
        "claim",
        "row",
        "field",
        "spec",
        "exact",
        "mandatory",
        "schema",
        "records",
        "record",
        "original",
        "candidate",
        "flags",
        "name",
        "mechanisms",
        "token",
        "genuinely",
        "distinct",
        "use",
        "permits",
        "forbid",
        "verbatim",
        "recorded",
        "copying",
        "id",
        "file",
        "blob",
        "hashing",
        "confirm",
        "read",
        "trust",
        "repository",
        "package",
        "item",
        "identify",
        "find",
        "search",
        "detector",
        "recovers",
        "valid",
        "accepting",
        "exit",
        "nonzero",
        "zero",
        "rejected",
        "reject",
        "validator",
        "canonical",
        "omits",
        "makes",
        "additional",
        "term",
        "never",
    }
)

# Fold surface forms onto an explicit canon (not min(), which mis-orders licence/license).
_SYNONYM_CANON: tuple[tuple[str, frozenset[str]], ...] = (
    ("source_probe", frozenset({"source_probe", "sourceprobe"})),
    ("settling", frozenset({"settling", "settling_probe", "settlingprobe"})),
    ("license", frozenset({"license", "licence"})),
    ("pinned", frozenset({"pinned", "commit", "pin"})),
    ("badge", frozenset({"badge", "metadata", "registry", "spdx"})),
    (
        "control",
        frozenset({"plant", "planted", "known", "present", "control", "knownpresent"}),
    ),
    ("absence", frozenset({"absence", "absent", "negative"})),
    ("receipt", frozenset({"receipt", "confirmation"})),
    ("cycle", frozenset({"cycle", "loop", "cycle_edge"})),
    ("rename", frozenset({"rename", "renames"})),
    ("decoy", frozenset({"decoy", "decoys"})),
    ("rider", frozenset({"rider", "riders"})),
    ("jaccard", frozenset({"jaccard"})),
    ("confirmed", frozenset({"confirmed"})),
    ("partial", frozenset({"partial"})),
    ("refuted", frozenset({"refuted"})),
    ("conclusion", frozenset({"conclusion", "prose", "confidence", "summary"})),
    ("leak", frozenset({"leak", "flag", "deliberately"})),
)

_FOLD: dict[str, str] = {}
for _canon, _g in _SYNONYM_CANON:
    for _t in _g:
        _FOLD[_t] = _canon

# Only these folded tokens participate in the independent signature.
LOAD_BEARING = frozenset(
    {
        "confirmed",
        "partial",
        "refuted",
        "source_probe",
        "settling",
        "cycle",
        "license",
        "rider",
        "pinned",
        "badge",
        "absence",
        "control",
        "rename",
        "decoy",
        "jaccard",
        "receipt",
        "conclusion",
        "leak",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def prepare(text: str) -> str:
    s = (text or "").lower()
    s = s.replace("known-present", " knownpresent ")
    s = s.replace("source_probe", " source_probe ")
    s = s.replace("settling probe", " settling ")
    s = s.replace("duplicate-of cycle", " cycle ")
    s = s.replace("duplicate of cycle", " cycle ")
    s = s.replace("non-zero", " nonzero ")
    s = s.replace("verdict=", " ")
    return s


def tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(prepare(text))


def token_set(text: str) -> set[str]:
    return {t for t in tokens(text) if t not in STOP and len(t) > 1}


def jaccard(a: str, b: str) -> float:
    sa, sb = token_set(a), token_set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def mechanical_score(a: str, b: str) -> float:
    return round(jaccard(a, b), 4)


def mechanical_verdict(score: float) -> str:
    return "DUPLICATE" if score >= MECHANICAL_DUP_THRESHOLD else "DISTINCT"


def fold_token(tok: str) -> str:
    return _FOLD.get(tok, tok)


def signature(text: str) -> frozenset[str]:
    folded = [fold_token(t) for t in tokens(text)]
    return frozenset(t for t in folded if t in LOAD_BEARING)


def independent_verdict(a: str, b: str) -> str:
    sa, sb = signature(a), signature(b)
    if not sa or not sb:
        return "DISTINCT"
    return "DUPLICATE" if sa == sb else "DISTINCT"


def order_verdicts(
    mech_verdict: str, mech_score: float, indep_verdict: str
) -> tuple[str, list[dict]]:
    """When the two verdicts differ, mechanical is reported first."""
    mech = {"kind": "mechanical", "verdict": mech_verdict, "score": mech_score}
    indep = {"kind": "independent", "verdict": indep_verdict}
    if mech_verdict != indep_verdict:
        return "mechanical", [mech, indep]
    return "independent", [indep, mech]


def judge_pair(a: str, b: str) -> dict:
    score = mechanical_score(a, b)
    mv = mechanical_verdict(score)
    iv = independent_verdict(a, b)
    first, ordered = order_verdicts(mv, score, iv)
    return {
        "mechanical_score": score,
        "mechanical_verdict": mv,
        "independent_verdict": iv,
        "signatures": {
            "from": sorted(signature(a)),
            "to": sorted(signature(b)),
        },
        "reported_first": first,
        "verdicts_in_order": ordered,
        "signals_agree": mv == iv,
    }


def _claim_map(claims: Iterable[dict]) -> dict[str, dict]:
    return {c["id"]: c for c in claims}


def assert_controls(claims: list[dict]) -> None:
    """Planted pairs the independent signature must get right.

    These are the unit's calibration, not the original corpus verdicts.
    """
    by = _claim_map(claims)
    expect = [
        (
            "CLM-CNF-RECEIPT-EMPTY-SOURCE",
            "CLM-CNF-RECEIPT-EMPTY-SOURCE-PARA",
            "DUPLICATE",
        ),
        (
            "CLM-CNF-RECEIPT-EMPTY-SOURCE",
            "CLM-CNF-RECEIPT-EMPTY-PARTIAL",
            "DISTINCT",
        ),
        (
            "CLM-CLAIMREC-NO-SETTLING-PROBE",
            "CLM-CLAIMREC-NO-SETTLING-PARA",
            "DUPLICATE",
        ),
        (
            "CLM-CLAIMREC-NO-SETTLING-PROBE",
            "CLM-CLAIMREC-DUP-CYCLE",
            "DISTINCT",
        ),
        (
            "CLM-DETECTOR-KNOWN-PRESENT",
            "CLM-DETECTOR-KNOWN-PRESENT-REWRITE",
            "DUPLICATE",
        ),
        (
            "CLM-LICENSE-BLOB-PINNED",
            "CLM-LICENSE-BLOB-PINNED-PARA",
            "DUPLICATE",
        ),
        ("CLM-LICENSE-BLOB-PINNED", "CLM-LICENSE-RIDER", "DISTINCT"),
        ("CLM-JACCARD-RENAME", "CLM-JACCARD-DECOY", "DISTINCT"),
        (
            "CLM-BLIND-BRIEF-STRIPS-CONCLUSION",
            "CLM-BLIND-BRIEF-LEAK-CONTROL",
            "DISTINCT",
        ),
    ]
    failed = []
    for a, b, want in expect:
        got = independent_verdict(by[a]["mechanism"], by[b]["mechanism"])
        if got != want:
            failed.append(
                {
                    "a": a,
                    "b": b,
                    "want": want,
                    "got": got,
                    "sig_a": sorted(signature(by[a]["mechanism"])),
                    "sig_b": sorted(signature(by[b]["mechanism"])),
                }
            )
    if failed:
        raise SystemExit(f"FAILED:CNF-0067 independent-control {failed}")
