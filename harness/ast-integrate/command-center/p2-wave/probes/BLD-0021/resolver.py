#!/usr/bin/env python3
"""Mechanical id-reference resolver with UNDECIDABLE as a first-class verdict.

Never guesses. A bare M-NN whose number is declared in more than one M-NN
namespace, and whose context carries no discriminating token, is UNDECIDABLE.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

ID_RE = re.compile(r"(?<![A-Za-z0-9])([A-Z]{1,8})-(\d{1,4})(?![A-Za-z0-9])")
FENCE_RE = re.compile(r"```.*?```", re.S)
INLINE_RE = re.compile(r"`[^`\n]+`")
QUOTED_RE = re.compile(r'"[^"\n]{0,80}"|\'[^\'\n]{0,80}\'')
EXAMPLE_LINE_RE = re.compile(
    r"(?i)\b(for example|e\.g\.|example:|quoted example)\b"
)

# Masked-context patterns. Tokens themselves are blanked before matching so a
# MECH-NN id does not inject a false MECH discriminator onto a sibling M-NN.
DISCRIMINATORS: dict[str, tuple[re.Pattern[str], ...]] = {
    "option-universe": (re.compile(r"(?i)\boptions?\b"),),
    "architecture-candidates": (
        re.compile(r"\bMECH\b"),
        re.compile(r"(?i)\bmechanisms?\b"),
    ),
    "wave3-deep-research": (re.compile(r"(?i)\bharness\b"),),
    "wave1-register": (
        re.compile(r"(?i)\bmission-grade\b"),
        re.compile(r"(?i)\bmission grade\b"),
    ),
}

COLLIDING_BARE_PREFIX = "M"


@dataclass(frozen=True)
class Declaration:
    namespace_id: str
    prefix: str
    number: int
    declared_id: str
    title: str
    also_bare_m: bool
    source: str


@dataclass
class Reference:
    token: str
    prefix: str
    number: int
    path: str
    line: int
    start: int
    end: int
    snippet: str
    context: str
    classification: str
    candidates: list[dict]
    discriminators_in_context: list[str]
    mention_reason: str | None = None


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_registries(paths: Iterable[Path]) -> list[Declaration]:
    out: list[Declaration] = []
    for path in paths:
        doc = load_json(path)
        if not isinstance(doc, dict):
            continue
        ns = str(doc.get("namespace_id") or "")
        prefix = str(doc.get("prefix") or "")
        also = bool(doc.get("also_bare_m"))
        rel = str(doc.get("source") or path.as_posix())
        for card in doc.get("cards") or []:
            if not isinstance(card, dict):
                continue
            number = int(card["number"])
            declared = str(card.get("id") or f"{prefix}-{number}")
            title = str(card.get("title") or declared)
            out.append(
                Declaration(
                    namespace_id=ns,
                    prefix=prefix,
                    number=number,
                    declared_id=declared,
                    title=title,
                    also_bare_m=also,
                    source=rel,
                )
            )
    return out


def _spans(text: str, rx: re.Pattern[str]) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in rx.finditer(text)]


def mention_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for start, end in _spans(text, FENCE_RE):
        spans.append((start, end, "fenced-code"))
    for start, end in _spans(text, INLINE_RE):
        spans.append((start, end, "inline-code"))
    for start, end in _spans(text, QUOTED_RE):
        spans.append((start, end, "quoted-example"))
    return spans


def _covered(pos: int, end: int, spans: list[tuple[int, int, str]]) -> str | None:
    for a, b, reason in spans:
        if pos >= a and end <= b:
            return reason
    return None


def _line_of(text: str, pos: int) -> int:
    return text[:pos].count("\n") + 1


def _line_text(text: str, pos: int) -> str:
    line_start = text.rfind("\n", 0, pos) + 1
    line_end = text.find("\n", pos)
    if line_end < 0:
        line_end = len(text)
    return text[line_start:line_end]


def _mask_ids(text: str) -> str:
    return ID_RE.sub(" ", text)


def discriminators_hit(masked_context: str) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for ns, patterns in DISCRIMINATORS.items():
        found: list[str] = []
        for rx in patterns:
            m = rx.search(masked_context)
            if m:
                found.append(m.group(0))
        if found:
            hits[ns] = found
    return hits


def candidates_for(
    prefix: str, number: int, declarations: list[Declaration]
) -> list[Declaration]:
    if prefix == COLLIDING_BARE_PREFIX:
        return [
            d
            for d in declarations
            if d.number == number and (d.prefix == prefix or d.also_bare_m)
        ]
    return [d for d in declarations if d.prefix == prefix and d.number == number]


def classify(
    prefix: str,
    number: int,
    declarations: list[Declaration],
    masked_context: str,
) -> tuple[str, list[Declaration], list[str]]:
    cands = candidates_for(prefix, number, declarations)
    hits = discriminators_hit(masked_context)
    disc_list: list[str] = []
    for ns, words in sorted(hits.items()):
        for w in words:
            disc_list.append(f"{ns}:{w}")

    if not cands:
        return "RESOLVES-NONE", [], disc_list

    namespaces = {d.namespace_id for d in cands}
    if len(cands) == 1:
        return "RESOLVES-ONE", cands, disc_list

    if len(namespaces) == 1:
        return "RESOLVES-MANY", cands, disc_list

    # Multiple namespaces. Discriminators may select exactly one of them.
    selected = [d for d in cands if d.namespace_id in hits]
    selected_ns = {d.namespace_id for d in selected}
    if len(selected_ns) == 1:
        if len(selected) == 1:
            return "RESOLVES-ONE", selected, disc_list
        return "RESOLVES-MANY", selected, disc_list
    # Zero hits, or hits that do not uniquely select one namespace: do not guess.
    return "UNDECIDABLE", cands, disc_list


def cand_rows(cands: list[Declaration]) -> list[dict]:
    rows = []
    seen = set()
    for d in cands:
        key = (d.namespace_id, d.declared_id, d.source)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "namespace_id": d.namespace_id,
                "declared_id": d.declared_id,
                "title": d.title,
                "source": d.source,
            }
        )
    return rows


def extract_references(
    path: Path,
    text: str,
    declarations: list[Declaration],
    *,
    relpath: str,
    detect_mentions: bool = True,
) -> list[Reference]:
    spans = mention_spans(text) if detect_mentions else []
    refs: list[Reference] = []
    for m in ID_RE.finditer(text):
        prefix, num_s = m.group(1), m.group(2)
        number = int(num_s)
        token = m.group(0)
        reason = _covered(m.start(), m.end(), spans) if detect_mentions else None
        line = _line_of(text, m.start())
        line_txt = _line_text(text, m.start())
        if (
            detect_mentions
            and reason is None
            and EXAMPLE_LINE_RE.search(line_txt)
        ):
            reason = "example-line"
        snippet = line_txt.strip()[:240]
        window = line_txt
        masked = _mask_ids(window)
        if reason:
            refs.append(
                Reference(
                    token=token,
                    prefix=prefix,
                    number=number,
                    path=relpath,
                    line=line,
                    start=m.start(),
                    end=m.end(),
                    snippet=snippet,
                    context=window,
                    classification="MENTION",
                    candidates=[],
                    discriminators_in_context=[],
                    mention_reason=reason,
                )
            )
            continue
        classification, cands, discs = classify(prefix, number, declarations, masked)
        refs.append(
            Reference(
                token=token,
                prefix=prefix,
                number=number,
                path=relpath,
                line=line,
                start=m.start(),
                end=m.end(),
                snippet=snippet,
                context=window,
                classification=classification,
                candidates=cand_rows(cands),
                discriminators_in_context=discs,
                mention_reason=None,
            )
        )
    return refs


def sweep_files(
    files: list[tuple[str, Path]],
    declarations: list[Declaration],
    *,
    detect_mentions: bool = True,
) -> list[Reference]:
    out: list[Reference] = []
    for rel, path in files:
        text = path.read_text(encoding="utf-8")
        out.extend(
            extract_references(
                path,
                text,
                declarations,
                relpath=rel,
                detect_mentions=detect_mentions,
            )
        )
    return out


def as_dict(ref: Reference) -> dict:
    return {
        "token": ref.token,
        "prefix": ref.prefix,
        "number": ref.number,
        "path": ref.path,
        "line": ref.line,
        "snippet": ref.snippet,
        "classification": ref.classification,
        "candidates": ref.candidates,
        "discriminators_in_context": ref.discriminators_in_context,
        "mention_reason": ref.mention_reason,
    }
