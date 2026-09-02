"""Classifiers: forum evidence class, source language, translation flag."""
from __future__ import annotations

import re
from typing import Mapping

from taxonomy import NATIVE_PATH, TRANSLATED_PATH, WORKING_LANGUAGE_DEFAULT

_DOC_CUE = re.compile(
    r"\b("
    r"according to (the )?(docs?|documentation|spec|rfc|manual|standard)|"
    r"see (rfc|iso|docs?|the spec)|"
    r"documented in|"
    r"the official|"
    r"per (the )?(rfc|iso|spec|docs?)"
    r")\b",
    re.I,
)
_ANECDOTE_CUE = re.compile(
    r"\b("
    r"I (tried|shipped|ran|saw|hit|fixed|broke|rolled|deployed)|"
    r"we (run|ran|shipped|hit|saw|tried) .{0,40}(prod|production)|"
    r"in production (we|I)|"
    r"war stor(y|ies)|"
    r"anecdote|"
    r"on our box|"
    r"in our fleet"
    r")\b",
    re.I,
)
_RFC_CUE = re.compile(r"\bRFC\s?\d{3,5}\b", re.I)
_ISO_CUE = re.compile(r"\bISO/\w+\s?\d+", re.I)

_NORMATIVE = re.compile(r"\b(SHALL|MUST|REQUIRED|SHALL NOT|MUST NOT)\b")
_INFORMATIVE = re.compile(r"\b(MAY|OPTIONAL|NOTE:|INFORMATIVE)\b")
_REGULATORY = re.compile(
    r"\b(CFR|fine[ds]?|penalt(y|ies)|shall be liable|regulation)\b", re.I
)

_DE_WORDS = frozenset(
    "der die das und ist nicht eine einer einem des den mit von zu".split()
)
_FR_WORDS = frozenset(
    "le la les une des est pas dans pour avec une du".split()
)
_EN_WORDS = frozenset("the and of a to in is for that with on as".split()
)
_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+")


def classify_forum_post(text: str) -> str:
    """Return practitioner_anecdote or documentation.

    Anecdote wins when first-person practice is present, even if a doc is
    mentioned — the unit's point is that a practitioner report is not the
    same evidence class as a documentation quote.
    """
    if _ANECDOTE_CUE.search(text):
        return "practitioner_anecdote"
    if _DOC_CUE.search(text) or _RFC_CUE.search(text) or _ISO_CUE.search(text):
        return "documentation"
    raise UnclassifiedPost(text)


class UnclassifiedPost(ValueError):
    """Forum extract refused to guess an evidence class."""


def classify_standard_statement(text: str) -> str:
    if _REGULATORY.search(text):
        return "regulatory_requirement"
    if _NORMATIVE.search(text):
        return "standard_normative"
    if _INFORMATIVE.search(text):
        return "standard_informative"
    raise UnclassifiedPost(text)


def detect_language(text: str, declared: str | None = None) -> str:
    if declared:
        return declared.lower()
    if any("\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff" for ch in text):
        return "ja"
    words = {m.group(0).lower() for m in _WORD.finditer(text)}
    if not words:
        return WORKING_LANGUAGE_DEFAULT
    scores = {
        "de": len(words & _DE_WORDS),
        "fr": len(words & _FR_WORDS),
        "en": len(words & _EN_WORDS),
    }
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        return WORKING_LANGUAGE_DEFAULT
    return best


def translation_record(
    *,
    source_language: str,
    working_language: str,
    original_span: str | None,
    is_translated: bool,
    translator: str | None,
) -> dict:
    if is_translated:
        path = dict(TRANSLATED_PATH)
        method = "declared-pair" if original_span else "language-mismatch"
        return {
            "source_language": source_language,
            "working_language": working_language,
            "translation": {
                "is_translated": True,
                "original_span": original_span,
                "translator": translator,
                "method": method,
            },
            "confidence_path": path,
        }
    path = dict(NATIVE_PATH)
    return {
        "source_language": source_language,
        "working_language": working_language,
        "translation": {
            "is_translated": False,
            "original_span": None,
            "translator": None,
            "method": "native",
        },
        "confidence_path": path,
    }


def decide_translated(
    source: Mapping[str, object], working_language: str
) -> tuple[bool, str, str | None, str | None]:
    """Return (is_translated, source_language, original_span, translator)."""
    declared = source.get("language")
    text = str(source.get("text") or source.get("body") or "")
    lang = detect_language(text, str(declared) if declared else None)
    original = source.get("original_span")
    original_span = str(original) if original else None
    translator = source.get("translator")
    translator_s = str(translator) if translator else None
    is_tr = bool(source.get("translated_from") or source.get("role") == "translation")
    if is_tr:
        orig_lang = source.get("original_language")
        if orig_lang:
            lang = str(orig_lang).lower()
        return True, lang, original_span, translator_s
    return False, lang, None, None
