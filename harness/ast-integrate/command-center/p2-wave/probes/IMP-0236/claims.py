"""Harvested-claim records and the coverage / provenance invariants."""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from taxonomy import (
    EVIDENCE_CLASSES,
    NATIVE_PATH,
    TRANSLATED_PATH,
    WORKING_LANGUAGE_DEFAULT,
)

NATIVE_ID = str(NATIVE_PATH["id"])
TRANSLATED_ID = str(TRANSLATED_PATH["id"])


class ClaimError(ValueError):
    """A harvested claim failed the output schema."""


def evidence_class_coverage(claims: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Computed coverage: tagged / total. Empty harvest is 0, not vacuously 1."""
    total = len(claims)
    if total == 0:
        return {
            "total": 0,
            "tagged": 0,
            "untagged": 0,
            "coverage": 0.0,
            "untagged_ids": [],
        }
    untagged_ids: list[str] = []
    tagged = 0
    for claim in claims:
        klass = claim.get("evidence_class")
        cid = str(claim.get("id") or "")
        if klass in EVIDENCE_CLASSES:
            tagged += 1
        else:
            untagged_ids.append(cid or "<missing-id>")
    return {
        "total": total,
        "tagged": tagged,
        "untagged": total - tagged,
        "coverage": tagged / total,
        "untagged_ids": untagged_ids,
    }


def validate_claim(claim: Mapping[str, Any]) -> None:
    cid = claim.get("id")
    if not cid or not isinstance(cid, str):
        raise ClaimError("claim.id required")
    if not claim.get("text") or not isinstance(claim.get("text"), str):
        raise ClaimError(f"{cid}: text required")
    if not claim.get("source_id"):
        raise ClaimError(f"{cid}: source_id required")
    if not claim.get("blueprint_id"):
        raise ClaimError(f"{cid}: blueprint_id required")
    klass = claim.get("evidence_class")
    if klass not in EVIDENCE_CLASSES:
        raise ClaimError(f"{cid}: evidence_class {klass!r} not in closed enum")

    src_lang = claim.get("source_language")
    if not src_lang or not isinstance(src_lang, str):
        raise ClaimError(f"{cid}: source_language required")
    work_lang = claim.get("working_language") or WORKING_LANGUAGE_DEFAULT
    trans = claim.get("translation")
    if not isinstance(trans, Mapping):
        raise ClaimError(f"{cid}: translation object required")
    path = claim.get("confidence_path")
    if not isinstance(path, Mapping) or not path.get("id"):
        raise ClaimError(f"{cid}: confidence_path.id required")

    is_tr = trans.get("is_translated")
    if is_tr is True:
        if path.get("id") != TRANSLATED_ID:
            raise ClaimError(
                f"{cid}: translated claim must use confidence_path.id="
                f"{TRANSLATED_ID!r}, got {path.get('id')!r}"
            )
        if path.get("requires_second_path") is not True:
            raise ClaimError(f"{cid}: translated path must require a second path")
        if not trans.get("original_span"):
            raise ClaimError(f"{cid}: translated claim needs original_span")
        if path.get("id") == NATIVE_ID:
            raise ClaimError(f"{cid}: translated claim used native path")
    elif is_tr is False:
        if path.get("id") != NATIVE_ID:
            raise ClaimError(
                f"{cid}: native claim must use confidence_path.id="
                f"{NATIVE_ID!r}, got {path.get('id')!r}"
            )
        if path.get("requires_second_path") is True:
            raise ClaimError(f"{cid}: native path must not require a second path")
        if trans.get("original_span") not in (None, ""):
            raise ClaimError(f"{cid}: native claim must not carry original_span")
    else:
        raise ClaimError(f"{cid}: translation.is_translated must be boolean")


def validate_harvest(claims: Sequence[Mapping[str, Any]]) -> None:
    seen: set[str] = set()
    for claim in claims:
        validate_claim(claim)
        cid = str(claim["id"])
        if cid in seen:
            raise ClaimError(f"duplicate claim id {cid}")
        seen.add(cid)


def translation_distinctness(claims: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Native vs translated claims must be distinguishable in the schema."""
    native_ids: set[str] = set()
    translated_ids: set[str] = set()
    native_paths: set[str] = set()
    translated_paths: set[str] = set()
    for claim in claims:
        path_id = str((claim.get("confidence_path") or {}).get("id") or "")
        is_tr = bool((claim.get("translation") or {}).get("is_translated"))
        if is_tr:
            translated_ids.add(str(claim.get("id")))
            translated_paths.add(path_id)
        else:
            native_ids.add(str(claim.get("id")))
            native_paths.add(path_id)
    overlap = native_paths & translated_paths
    return {
        "native_count": len(native_ids),
        "translated_count": len(translated_ids),
        "native_path_ids": sorted(native_paths),
        "translated_path_ids": sorted(translated_paths),
        "path_id_overlap": sorted(overlap),
        "distinguishable": bool(native_ids)
        and bool(translated_ids)
        and not overlap
        and native_paths == {NATIVE_ID}
        and translated_paths == {TRANSLATED_ID},
    }


def forum_class_split(claims: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    anecdote = [
        c["id"]
        for c in claims
        if c.get("evidence_class") == "practitioner_anecdote"
    ]
    docs = [c["id"] for c in claims if c.get("evidence_class") == "documentation"]
    return {
        "anecdote_ids": anecdote,
        "documentation_ids": docs,
        "anecdote_count": len(anecdote),
        "documentation_count": len(docs),
        "classes_distinct": "practitioner_anecdote" != "documentation",
        "split_ok": bool(anecdote) and bool(docs) and not (set(anecdote) & set(docs)),
    }
