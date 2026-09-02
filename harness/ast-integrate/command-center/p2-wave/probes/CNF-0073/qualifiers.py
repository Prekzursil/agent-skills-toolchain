#!/usr/bin/env python3
"""Hedge/qualifier lexicon and qualifier-diff for CNF-0073."""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
HEDGES_PATH = HERE / "fixtures" / "hedges.json"

_WORD = re.compile(r"[A-Za-z]+(?:-[A-Za-z]+)?|[\u00C0-\u024F]+|[\u0400-\u04FF]+|[\u4E00-\u9FFF]+|[\u3040-\u30FF]+|[\uAC00-\uD7AF]+", re.UNICODE)


def load_hedges() -> list[dict]:
    doc = json.loads(HEDGES_PATH.read_text(encoding="utf-8"))
    return list(doc.get("hedges") or [])


def hedge_forms() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for row in load_hedges():
        hid = str(row["id"])
        forms = set()
        for form in list(row.get("source_forms") or []) + list(row.get("english_forms") or []):
            forms.add(str(form).casefold())
        out[hid] = forms
    return out


def all_form_to_id() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for hid, forms in hedge_forms().items():
        for form in forms:
            mapping[form] = hid
    return mapping


def extract_hedge_ids(text: str) -> list[str]:
    """Return sorted unique canonical hedge ids found in text."""
    blob = text or ""
    found: set[str] = set()
    mapping = all_form_to_id()
    # Longest form first so すべての is not required here; hedges are short.
    forms = sorted(mapping.keys(), key=len, reverse=True)
    lowered = blob.casefold()
    used_spans: list[tuple[int, int]] = []
    for form in forms:
        start = 0
        while True:
            idx = lowered.find(form, start)
            if idx < 0:
                break
            end = idx + len(form)
            if any(not (end <= a or idx >= b) for a, b in used_spans):
                start = idx + 1
                continue
            # Word-ish boundary for alphabetic forms; CJK can match substring.
            if form.isascii() or any("a" <= c <= "z" for c in form):
                before = lowered[idx - 1] if idx > 0 else " "
                after = lowered[end] if end < len(lowered) else " "
                if before.isalnum() or after.isalnum():
                    start = idx + 1
                    continue
            found.add(mapping[form])
            used_spans.append((idx, end))
            start = end
    return sorted(found)


def qualifier_diff(original: str, recorded: str, independent: str) -> dict:
    orig = extract_hedge_ids(original)
    rec = extract_hedge_ids(recorded)
    indep = extract_hedge_ids(independent)
    dropped = sorted(set(orig) - set(rec))
    introduced = sorted(set(rec) - set(orig))
    material = bool(dropped or introduced)
    return {
        "original_hedges": orig,
        "recorded_hedges": rec,
        "independent_hedges": indep,
        "dropped_by_recorded": dropped,
        "introduced_by_recorded": introduced,
        "independent_restored": sorted(set(orig) & set(indep) - set(rec)),
        "material_change": material,
    }


def content_lemmas(text: str) -> set[str]:
    stop = {
        "the", "a", "an", "is", "be", "in", "of", "at", "after", "to", "and",
        "will", "not", "this", "an-error",
    }
    hedge_surface = set()
    for forms in hedge_forms().values():
        hedge_surface |= forms
    tokens = [t.casefold() for t in _WORD.findall(text or "")]
    out = set()
    for tok in tokens:
        if tok in stop or tok in hedge_surface:
            continue
        if len(tok) <= 1:
            continue
        out.add(tok)
    return out


def claim_survives(recorded: str, independent: str) -> bool:
    a = content_lemmas(recorded)
    b = content_lemmas(independent)
    if not a or not b:
        return False
    overlap = len(a & b)
    union = len(a | b)
    if overlap >= 2:
        return True
    return (overlap / union) >= 0.35 if union else False
