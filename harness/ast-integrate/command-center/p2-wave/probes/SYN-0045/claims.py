#!/usr/bin/env python3
"""Mechanical no-new-claims invariant for SYN-0045.

Claim identity is a normalized verbatim string. A brief claim is allowed
only when that string already exists on the bound report. Rephrasing is
invention. Markdown claim bullets are scanned, not just the JSON array.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

LABELS = (
    "VERIFIED",
    "INFERRED",
    "UNVERIFIED",
    "REJECTED",
    "DEFERRED",
)
LABEL_RE = re.compile(
    r"^(VERIFIED|INFERRED|UNVERIFIED|REJECTED|DEFERRED):\s+(.*)$"
)
DECISION_KEYS = (
    "question",
    "recommendation",
    "strongest_tradeoff",
    "default_if_unanswered",
)
CLAIM_SECTIONS = ("what was built", "what is proven", "what is open")
ITEM_LIST_KEYS = ("items", "claims", "entries", "report_items")
CLAIM_FIELD_KEYS = ("claim", "text", "statement", "claim_text")
LABEL_FIELD_KEYS = ("label", "status", "band")
WS_RE = re.compile(r"\s+")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

ONE_PAGE_MAX_WORDS = 500
ONE_PAGE_MIN_WORDS = 40


def normalize(text: str) -> str:
    return WS_RE.sub(" ", (text or "").strip()).casefold()


def claim_key(text: str) -> str:
    return normalize(text).rstrip(".,;:")


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"not an object: {path}")
    return data


def _first_list(doc: dict) -> list:
    for key in ITEM_LIST_KEYS:
        val = doc.get(key)
        if isinstance(val, list) and val:
            return val
    return []


def _item_claim(item: dict) -> str:
    if not isinstance(item, dict):
        return ""
    for key in CLAIM_FIELD_KEYS:
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _item_label(item: dict) -> str:
    if not isinstance(item, dict):
        return "UNVERIFIED"
    for key in LABEL_FIELD_KEYS:
        val = str(item.get(key) or "").strip().upper()
        if val in LABELS:
            return val
    return "UNVERIFIED"


def _item_id(item: dict, index: int) -> str:
    if not isinstance(item, dict):
        return f"R-{index:03d}"
    for key in ("id", "item_id", "claim_id"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return f"R-{index:03d}"


def extract_report_claims(report: dict) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for i, item in enumerate(_first_list(report), start=1):
        text = _item_claim(item if isinstance(item, dict) else {})
        if not text:
            continue
        key = claim_key(text)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "id": _item_id(item if isinstance(item, dict) else {}, i),
                "label": _item_label(item if isinstance(item, dict) else {}),
                "text": text,
                "key": key,
            }
        )
    return rows


def extract_brief_claim_rows(brief: dict) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for i, item in enumerate(brief.get("claims") or [], start=1):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        key = claim_key(text)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "id": str(item.get("id") or f"B-{i:03d}"),
                "source_item_id": str(item.get("source_item_id") or ""),
                "label": str(item.get("label") or ""),
                "text": text,
                "key": key,
            }
        )
    return rows


def markdown_claim_texts(markdown: str) -> list[str]:
    """Pull claim bullets from the owner-readable sections.

    Decision and next-action sections are not claims. Section headers,
    evidence lines, and the sentinel are skipped.
    """
    texts: list[str] = []
    section = ""
    for raw in (markdown or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            section = line.lstrip("#").strip().casefold()
            continue
        if section not in CLAIM_SECTIONS:
            continue
        if not line.startswith("- "):
            continue
        body = line[2:].strip()
        match = LABEL_RE.match(body)
        if match:
            body = match.group(2).strip()
        if body:
            texts.append(body)
    return texts


def set_difference(brief_texts: list[str], report_texts: list[str]) -> list[str]:
    report_keys = {claim_key(t) for t in report_texts if claim_key(t)}
    extra: list[str] = []
    seen: set[str] = set()
    for text in brief_texts:
        key = claim_key(text)
        if not key or key in report_keys or key in seen:
            continue
        seen.add(key)
        extra.append(text)
    return extra


def invariant(brief: dict, report: dict) -> dict:
    report_rows = extract_report_claims(report)
    json_rows = extract_brief_claim_rows(brief)
    md_texts = markdown_claim_texts(str(brief.get("markdown") or ""))
    json_texts = [r["text"] for r in json_rows]
    report_texts = [r["text"] for r in report_rows]
    extra_json = set_difference(json_texts, report_texts)
    extra_md = set_difference(md_texts, report_texts)
    extra = extra_json + [t for t in extra_md if claim_key(t) not in {claim_key(x) for x in extra_json}]
    missing_source = [
        r["id"]
        for r in json_rows
        if r["source_item_id"]
        and r["source_item_id"] not in {row["id"] for row in report_rows}
    ]
    empty = not extra and not missing_source
    return {
        "empty": empty,
        "brief_minus_report": extra,
        "markdown_minus_report": extra_md,
        "json_minus_report": extra_json,
        "missing_source_item_id": missing_source,
        "report_claim_count": len(report_rows),
        "brief_claim_count": len(json_rows),
        "markdown_claim_count": len(md_texts),
        "retention_rate": (
            (len(json_rows) / len(report_rows)) if report_rows else 0.0
        ),
        "printed": (
            "brief-claims minus report-claims = []"
            if empty
            else f"brief-claims minus report-claims = {extra}"
        ),
    }


def word_count(text: str) -> int:
    return len([w for w in WS_RE.split((text or "").strip()) if w])


def within_one_page(markdown: str) -> dict:
    n = word_count(markdown)
    return {
        "word_count": n,
        "min": ONE_PAGE_MIN_WORDS,
        "max": ONE_PAGE_MAX_WORDS,
        "ok": ONE_PAGE_MIN_WORDS <= n <= ONE_PAGE_MAX_WORDS,
    }


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def decision_errors(entry: dict) -> list[str]:
    if not isinstance(entry, dict):
        return ["decision-not-object"]
    errors: list[str] = []
    for key in DECISION_KEYS:
        if not _nonempty(entry.get(key)):
            errors.append(f"{key}-empty")
    q = str(entry.get("question") or "")
    if q.count("?") > 1:
        errors.append("compound-question")
    return errors


def decisions_complete(entries: list) -> dict:
    rows = [e for e in (entries or []) if isinstance(e, dict)]
    failed = []
    for i, entry in enumerate(rows, start=1):
        errs = decision_errors(entry)
        if errs:
            failed.append({"id": entry.get("id") or f"D-{i:03d}", "errors": errs})
    return {
        "ok": not failed,
        "count": len(rows),
        "failed": failed,
    }


def plant_invention(brief: dict, sentence: str) -> dict:
    """Return a mutated brief that adds an unsupported claim in JSON and markdown."""
    import copy

    planted = copy.deepcopy(brief)
    claims = list(planted.get("claims") or [])
    claims.append(
        {
            "id": "PLANTED-INVENTION",
            "label": "VERIFIED",
            "source_item_id": "NONE",
            "text": sentence,
        }
    )
    planted["claims"] = claims
    md = str(planted.get("markdown") or "")
    needle = "## What is proven"
    insert = f"{needle}\n\n- VERIFIED: {sentence}"
    if needle in md:
        planted["markdown"] = md.replace(needle, insert, 1)
    else:
        planted["markdown"] = md + f"\n\n- VERIFIED: {sentence}\n"
    return planted


def locate_report(repo: Path, fixture: Path) -> dict:
    live = repo / "command-center" / "synthesis" / "SYN-0041.final-report.json"
    if live.is_file() and live.stat().st_size > 0:
        return {
            "kind": "live",
            "path": live.relative_to(repo).as_posix(),
            "present": True,
            "abs": live,
        }
    return {
        "kind": "frozen-fixture",
        "path": fixture.relative_to(repo).as_posix(),
        "present": False,
        "abs": fixture,
    }


def payload(doc: dict) -> dict:
    """Domain owner-brief fields live under report (receipt_core)."""
    if not isinstance(doc, dict):
        return {}
    report = doc.get("report")
    if isinstance(report, dict) and (
        report.get("kind") == "owner-brief"
        or "claims" in report
        or "markdown" in report
    ):
        return report
    return doc


# Names used by emit.py / probes (aliases of the functions above).
load_json = load_json
locate_report = locate_report
extract_report_claims = extract_report_claims
markdown_claim_texts = markdown_claim_texts
within_one_page = within_one_page
decisions_complete = decisions_complete
plant_invention = plant_invention
