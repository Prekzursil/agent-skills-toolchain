"""Extract evidence-bearing verdicts from a BLD receipt.

Reviewer.verdict and state are not coverage verdicts. Claim-shaped rows
(claims, evidence, evidence_verdicts, findings, cells) and an explicit
coverage_verdicts list count. Estate receipts store CONFIRMED/REFUTED on
evidence[].verdict; skipping that list would mark every question UNCOVERED.
"""
from __future__ import annotations

EVIDENCE = frozenset({"CONFIRMED", "REFUTED"})
WEAK = frozenset({"NOT-CHECKED", "PARTIAL"})
KNOWN = EVIDENCE | WEAK
SKIP_KEYS = frozenset({"reviewer", "review", "assigned_model_vendor_role"})
CLAIM_LIST_KEYS = (
    "claims",
    "evidence",
    "evidence_verdicts",
    "findings",
    "cells",
    "coverage_verdicts",
)


def _norm(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    v = value.strip().upper()
    return v if v in KNOWN else None


def collect_verdicts(doc: object) -> list[str]:
    found: list[str] = []

    def from_claim_list(rows: object) -> None:
        if isinstance(rows, list) and rows and all(isinstance(x, str) for x in rows):
            for item in rows:
                n = _norm(item)
                if n:
                    found.append(n)
            return
        if not isinstance(rows, list):
            return
        for row in rows:
            if isinstance(row, dict):
                n = _norm(row.get("verdict"))
                if n:
                    found.append(n)
            else:
                n = _norm(row)
                if n:
                    found.append(n)

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            for key in CLAIM_LIST_KEYS:
                if key in obj:
                    from_claim_list(obj.get(key))
            n = _norm(obj.get("phase13_verdict"))
            if n:
                found.append(n)
            for key, val in obj.items():
                if key in SKIP_KEYS or key in CLAIM_LIST_KEYS:
                    continue
                if key == "verdict":
                    continue
                walk(val)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(doc)
    return found


def classify_unit(verdicts: list[str], parse_ok: bool, empty_file: bool) -> str:
    if empty_file or not parse_ok:
        return "empty"
    if any(v in EVIDENCE for v in verdicts):
        return "evidence-bearing"
    if verdicts:
        return "not-checked-only"
    return "empty"


def receipt_question(doc: dict, catalog_tag: str | None) -> str | None:
    declared = doc.get("phase13_question")
    if isinstance(declared, str) and declared.strip() in {
        "what files were never read",
        "what clients were never tested",
        "what platforms were never tested",
        "what owner requirements disappeared",
        "what option IDs were silently dropped",
        "what failures were normalized away",
        "what unknowns remain",
        "what existing work was ignored",
        "what test could falsely pass",
        "what threat actor was not modeled",
        "what would break at 10x scale",
    }:
        return declared.strip()
    from questions import parse_tag, ELEVEN_LABELS, is_meta

    for key in ("question_or_target", "question"):
        tag = parse_tag(str(doc.get(key) or ""))
        if tag in ELEVEN_LABELS:
            return tag
        if is_meta(tag):
            return None
    if catalog_tag in ELEVEN_LABELS:
        return catalog_tag
    return None
