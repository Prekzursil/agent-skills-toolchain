"""Per-blueprint extractors. Each emitted statement is tagged before return."""
from __future__ import annotations

from typing import Any, Mapping

from classify import (
    UnclassifiedPost,
    classify_forum_post,
    classify_standard_statement,
    decide_translated,
    translation_record,
)
from taxonomy import WORKING_LANGUAGE_DEFAULT


def _claim(
    *,
    cid: str,
    text: str,
    source_id: str,
    blueprint_id: str,
    evidence_class: str,
    source: Mapping[str, Any],
    working_language: str,
) -> dict[str, Any]:
    is_tr, lang, orig, translator = decide_translated(source, working_language)
    rec = translation_record(
        source_language=lang,
        working_language=working_language,
        original_span=orig,
        is_translated=is_tr,
        translator=translator,
    )
    out = {
        "id": cid,
        "text": text.strip(),
        "source_id": source_id,
        "blueprint_id": blueprint_id,
        "evidence_class": evidence_class,
        **rec,
    }
    return out


def extract_patent(
    sources: list[Mapping[str, Any]],
    *,
    working_language: str = WORKING_LANGUAGE_DEFAULT,
) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    n = 0
    for src in sources:
        sid = str(src["id"])
        family = src.get("family_id")
        if family:
            n += 1
            claims.append(
                _claim(
                    cid=f"pat-fam-{n:03d}",
                    text=f"Application {sid} is a member of patent family {family}.",
                    source_id=sid,
                    blueprint_id="prior-art-patent",
                    evidence_class="patent_family",
                    source=src,
                    working_language=working_language,
                )
            )
        for item in src.get("claims") or []:
            n += 1
            num = item.get("number") or item.get("num") or n
            claims.append(
                _claim(
                    cid=f"pat-clm-{n:03d}",
                    text=f"Claim {num}: {item['text']}",
                    source_id=sid,
                    blueprint_id="prior-art-patent",
                    evidence_class="patent_claim",
                    source=src,
                    working_language=working_language,
                )
            )
        for cite in src.get("citations") or []:
            n += 1
            cite_id = cite.get("id") or cite.get("doc_id")
            claims.append(
                _claim(
                    cid=f"pat-cit-{n:03d}",
                    text=f"Cites prior-art document {cite_id} ({cite.get('kind') or 'citation'}).",
                    source_id=sid,
                    blueprint_id="prior-art-patent",
                    evidence_class="patent_citation",
                    source=src,
                    working_language=working_language,
                )
            )
    return claims


def extract_standards(
    sources: list[Mapping[str, Any]],
    *,
    working_language: str = WORKING_LANGUAGE_DEFAULT,
) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    n = 0
    for src in sources:
        sid = str(src["id"])
        statements = list(src.get("statements") or [])
        if not statements and src.get("body"):
            statements = [
                {"text": part.strip()}
                for part in str(src["body"]).split("\n")
                if part.strip()
            ]
        for stmt in statements:
            text = str(stmt.get("text") if isinstance(stmt, Mapping) else stmt)
            n += 1
            klass = classify_standard_statement(text)
            claims.append(
                _claim(
                    cid=f"std-{n:03d}",
                    text=text,
                    source_id=sid,
                    blueprint_id="standards-regulatory",
                    evidence_class=klass,
                    source=src,
                    working_language=working_language,
                )
            )
    return claims


def extract_forum(
    sources: list[Mapping[str, Any]],
    *,
    working_language: str = WORKING_LANGUAGE_DEFAULT,
) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    n = 0
    for src in sources:
        sid = str(src["id"])
        posts = list(src.get("posts") or [])
        if not posts and src.get("body"):
            posts = [{"id": sid, "body": src["body"]}]
        for post in posts:
            body = str(post.get("body") or post.get("text") or "")
            n += 1
            try:
                klass = classify_forum_post(body)
            except UnclassifiedPost as exc:
                raise UnclassifiedPost(
                    f"forum post {post.get('id') or n} refused: no evidence class"
                ) from exc
            claims.append(
                _claim(
                    cid=f"frm-{n:03d}",
                    text=body,
                    source_id=str(post.get("id") or sid),
                    blueprint_id="niche-forum",
                    evidence_class=klass,
                    source={**src, **post, "text": body},
                    working_language=working_language,
                )
            )
    return claims


def extract_multilingual(
    sources: list[Mapping[str, Any]],
    *,
    working_language: str = WORKING_LANGUAGE_DEFAULT,
) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    n = 0
    originals = {
        str(s["id"]): s for s in sources if s.get("role") != "translation"
    }
    for src in sources:
        sid = str(src["id"])
        statements = list(src.get("statements") or [])
        if not statements:
            text = str(src.get("text") or src.get("body") or "")
            if text:
                statements = [{"text": text, "original_span": src.get("original_span")}]
        parent = originals.get(str(src.get("translated_from") or ""))
        for stmt in statements:
            text = str(stmt.get("text") if isinstance(stmt, Mapping) else stmt)
            n += 1
            merged = dict(src)
            if isinstance(stmt, Mapping):
                merged = {**src, **stmt}
            if parent:
                merged["original_language"] = parent.get("language")
                merged["role"] = "translation"
                merged["translated_from"] = parent["id"]
                if not merged.get("original_span"):
                    merged["original_span"] = str(
                        parent.get("text") or parent.get("body") or ""
                    )
            claims.append(
                _claim(
                    cid=f"mul-{n:03d}",
                    text=text,
                    source_id=sid,
                    blueprint_id="multilingual",
                    evidence_class="mixed_source_statement",
                    source=merged,
                    working_language=working_language,
                )
            )
    return claims


EXTRACTORS = {
    "prior-art-patent": extract_patent,
    "standards-regulatory": extract_standards,
    "niche-forum": extract_forum,
    "multilingual": extract_multilingual,
}
