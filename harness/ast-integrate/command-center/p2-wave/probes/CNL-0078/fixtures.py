#!/usr/bin/env python3
"""Deterministic ledgers for CNL-0078 both-states, AND-not-OR, and identity-disagree."""
from __future__ import annotations

from typing import Any

REQUIRED = {
    "subquestions": [f"Q{i}" for i in range(10)],
    "categories": [f"C{i}" for i in range(10)],
    "evidence_classes": [f"E{i}" for i in range(5)],
}

PARAPHRASE_TEMPLATES = [
    "{m} solves {subq} in {cat} with {evid}.",
    "Restate {m}: a wording variant aimed at {subq} / {cat} ({evid}).",
    "Full rewrite of the same mechanism {m} — different sentences, same family, {subq} {cat} {evid}.",
    "One-parameter fork of {m} with k={k} still {subq} {cat} {evid}.",
    "Renamed title for {m}: '{alias}' covering {subq} in {cat} ({evid}).",
    "Paraphrase-B of {m} addressing {subq} under {cat} evidenced by {evid}.",
    "Paraphrase-C {m} / {subq} / {cat} / {evid} with no new information.",
    "Paraphrase-D {m} quota-padding text for {subq} {cat} {evid}.",
    "Paraphrase-E {m} still the same idea {subq} {cat} {evid}.",
    "Paraphrase-F {m} trivial variant {subq} {cat} {evid}.",
    "Paraphrase-G {m} {subq} {cat} {evid} synonym swap.",
    "Paraphrase-H {m} {subq} {cat} {evid} token shuffle.",
    "Paraphrase-I {m} {subq} {cat} {evid} padding row.",
]


def _idea(
    *,
    i: int,
    mechanism: str,
    category: str,
    subq: str,
    evid: str,
    text: str,
    params: dict[str, Any] | None = None,
    gamed_category: str | None = None,
    gamed_subquestions: list[str] | None = None,
    gamed_evidence_class: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": f"idea-{i:04d}",
        "mechanism": mechanism,
        "params": params or {"k": i},
        "text": text,
        "category": category,
        "subquestions": [subq],
        "evidence_class": evid,
    }
    if gamed_category is not None:
        row["gamed_category"] = gamed_category
    if gamed_subquestions is not None:
        row["gamed_subquestions"] = gamed_subquestions
    if gamed_evidence_class is not None:
        row["gamed_evidence_class"] = gamed_evidence_class
    return row


def fire_ledger() -> list[dict[str, Any]]:
    """100 genuine distinct mechanisms, full requirement coverage → FIRE."""
    out = []
    for i in range(100):
        m = f"M{i:03d}"
        cat = f"C{i % 10}"
        subq = f"Q{i % 10}"
        evid = f"E{i % 5}"
        out.append(
            _idea(
                i=i,
                mechanism=m,
                category=cat,
                subq=subq,
                evid=evid,
                text=(
                    f"Distinct mechanism {m} uses primitive P{i} to discharge "
                    f"{subq} in category {cat} with evidence class {evid}."
                ),
                params={"k": i, "primitive": f"P{i}"},
            )
        )
    return out


def silent_incomplete_ledger() -> list[dict[str, Any]]:
    """100 distinct mechanisms clustered in C0/Q0/E0 → unique ok, completeness low."""
    out = []
    for i in range(100):
        m = f"N{i:03d}"
        out.append(
            _idea(
                i=i,
                mechanism=m,
                category="C0",
                subq="Q0",
                evid="E0",
                text=(
                    f"Distinct mechanism {m} primitive P{i} still stuck on Q0/C0/E0."
                ),
                params={"k": i, "primitive": f"P{i}"},
            )
        )
    return out


def silent_low_unique_ledger() -> list[dict[str, Any]]:
    """40 distinct well-spread mechanisms → completeness high, unique < 100."""
    out = []
    for i in range(40):
        m = f"P{i:03d}"
        cat = f"C{i % 10}"
        subq = f"Q{i % 10}"
        evid = f"E{i % 5}"
        out.append(
            _idea(
                i=i,
                mechanism=m,
                category=cat,
                subq=subq,
                evid=evid,
                text=(
                    f"Distinct mechanism {m} primitive P{i} covers {subq}/{cat}/{evid}."
                ),
                params={"k": i, "primitive": f"P{i}"},
            )
        )
    return out


def planted_bad_ledger() -> list[dict[str, Any]]:
    """8 mechanisms × 13 wording variants = 104 raw. Quota-filling. Must stay SILENT."""
    out = []
    n = 0
    for mech_i in range(8):
        m = f"G{mech_i:03d}"
        cat = f"C{mech_i % 2}"
        subq = f"Q{mech_i % 2}"
        evid = f"E{mech_i % 2}"
        alias = f"alias-{m}"
        for t_i, tmpl in enumerate(PARAPHRASE_TEMPLATES):
            text = tmpl.format(m=m, subq=subq, cat=cat, evid=evid, k=t_i, alias=alias)
            out.append(
                _idea(
                    i=n,
                    mechanism=m,
                    category=cat,
                    subq=subq,
                    evid=evid,
                    text=text,
                    params={"k": t_i, "fork": t_i},
                )
            )
            n += 1
    return out


def disagree_ledger() -> list[dict[str, Any]]:
    """10 real mechanisms × 10 paraphrases with gamed coverage tags on raw rows.

    Canonical identity: unique=10, completeness uses true category (10/10) = 1.0
    → unique < 100, SILENT.
    Raw identity: unique=100, gamed coverage = 1.0 → naive AND would FIRE.
    Mixed bind is UNBOUND and must not fire.
    """
    out = []
    n = 0
    for mech_i in range(10):
        m = f"D{mech_i:03d}"
        true_cat = f"C{mech_i}"
        true_subq = f"Q{mech_i}"
        true_evid = f"E{mech_i % 5}"
        for t_i, tmpl in enumerate(PARAPHRASE_TEMPLATES[:10]):
            gamed_cat = f"C{n % 10}"
            gamed_subq = [f"Q{n % 10}"]
            gamed_evid = f"E{n % 5}"
            text = tmpl.format(
                m=m, subq=true_subq, cat=true_cat, evid=true_evid, k=t_i, alias=f"x-{m}"
            )
            out.append(
                _idea(
                    i=n,
                    mechanism=m,
                    category=true_cat,
                    subq=true_subq,
                    evid=true_evid,
                    text=text,
                    params={"k": t_i},
                    gamed_category=gamed_cat,
                    gamed_subquestions=gamed_subq,
                    gamed_evidence_class=gamed_evid,
                )
            )
            n += 1
    return out


FIXTURES = {
    "fire": fire_ledger,
    "silent_incomplete": silent_incomplete_ledger,
    "silent_low_unique": silent_low_unique_ledger,
    "planted_bad": planted_bad_ledger,
    "disagree": disagree_ledger,
}
