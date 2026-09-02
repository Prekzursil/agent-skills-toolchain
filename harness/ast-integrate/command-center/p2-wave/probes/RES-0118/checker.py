#!/usr/bin/env python3
"""Structural checker for RES-0118 hit-register + no-scope-interpretation.

Interpretive fields are scanned for legal-analysis language. Quoted patent
claim text is not scanned: a claim that contains the word "comprising" is
not this unit offering a scope interpretation.
"""
from __future__ import annotations

import copy
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UID = "RES-0118"
OUT_REL = "command-center/research/RES-0118.json"
SENTINEL = (
    "SUCCESS:RES-0118 in the receipt AND a hit register with publication "
    "numbers and statuses plus an explicit not-legal-advice statement"
)
NOT_LEGAL_ADVICE = (
    "THIS RECORD IS NOT LEGAL ADVICE. It is a factual landscape of "
    "publication numbers, jurisdictions, reported statuses, and the specific "
    "claim text that was read. No interpretation of claim scope is provided "
    "and none may be inferred. No unit may treat this output as legal advice. "
    "If a hit is flagged material_for_owner_review, that flag is a "
    "keyword-overlap alert against this program's intended-mechanism "
    "inventory and is not a determination of infringement, validity, "
    "enforceability, or freedom to operate. Downstream units must not act on "
    "any classification until the owner records an explicit sign-off; owner "
    "sign-off has not been obtained."
)
NO_SCOPE = (
    "No interpretation of claim scope is provided and none may be inferred."
)
HIT_FIELDS = (
    "publication_number",
    "jurisdiction",
    "legal_status",
    "claim_number_read",
    "claim_text_read",
    "fetch_timestamp",
    "snapshot_sha256",
    "source_url",
)
SCOPE_FORBIDDEN = re.compile(
    r"(infring(?:e|es|ed|ing|ement)"
    r"|freedom\s+to\s+operate|\bFTO\b"
    r"|claim\s+construction"
    r"|doctrine\s+of\s+equivalents"
    r"|this\s+patent\s+covers"
    r"|this\s+claim\s+covers"
    r"|would\s+block"
    r"|we\s+infringe"
    r"|patentability\s+opinion"
    r"|invalidit(?:y|ies)"
    r"|literal\s+infringement)",
    re.IGNORECASE,
)
INTERPRETIVE_KEYS = frozenset(
    {
        "findings",
        "notes",
        "landscape_summary",
        "question",
        "title",
        "residual_unknowns",
    }
)


def strip_markup(chunk: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", chunk)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return digest_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def load_artifact(path: Path | None = None) -> dict[str, Any]:
    target = path or (REPO / OUT_REL)
    return json.loads(target.read_text(encoding="utf-8"))


def _legal_status_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        parts = [
            str(value.get("as_printed") or ""),
            str(value.get("as_reported_by_source") or ""),
            str(value.get("kind_code") or ""),
            str(value.get("source") or ""),
        ]
        return " ".join(p for p in parts if p).strip()
    return ""


def _walk_interpretive(obj: Any, path: str, acc: list[tuple[str, str]]) -> None:
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key in {
                "claim_text_read",
                "snapshot_sha256",
                "raw_output",
                "html_excerpt",
                "not_legal_advice",
                "no_scope_interpretation",
            }:
                continue
            child = f"{path}.{key}" if path else key
            if key in INTERPRETIVE_KEYS or key in {
                "statement",
                "note",
                "reason",
                "summary",
                "claim",
                "obligation",
            }:
                if isinstance(val, str) and val.strip():
                    acc.append((child, val))
            _walk_interpretive(val, child, acc)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _walk_interpretive(item, f"{path}[{i}]", acc)


def hit_field_errors(hit: Any, idx: int) -> list[str]:
    errors: list[str] = []
    prefix = f"hit[{idx}]"
    if not isinstance(hit, dict):
        return [f"{prefix} is not an object"]
    for field in HIT_FIELDS:
        if field not in hit:
            errors.append(f"{prefix} missing {field}")
            continue
        val = hit[field]
        if field == "legal_status":
            text = _legal_status_text(val)
            if len(text) < 3:
                errors.append(f"{prefix} legal_status empty")
        elif field == "claim_number_read":
            if not isinstance(val, int) or val < 1:
                errors.append(f"{prefix} claim_number_read must be int>=1")
        elif field == "snapshot_sha256":
            if not isinstance(val, str) or len(val) != 64:
                errors.append(f"{prefix} snapshot_sha256 is not sha256 hex")
        elif not isinstance(val, str) or not val.strip():
            errors.append(f"{prefix} {field} empty")
    pub = str(hit.get("publication_number") or "")
    if pub and not re.match(r"^[A-Z]{2}\w+$", pub):
        errors.append(f"{prefix} publication_number shape {pub!r}")
    jur = str(hit.get("jurisdiction") or "")
    if jur and len(jur) < 2:
        errors.append(f"{prefix} jurisdiction too short")
    text = str(hit.get("claim_text_read") or "")
    if text and len(text) < 40:
        errors.append(f"{prefix} claim_text_read too short to be a claim")
    ts = str(hit.get("fetch_timestamp") or "")
    if ts and not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", ts):
        errors.append(f"{prefix} fetch_timestamp not ISO-8601 Z")
    return errors


def snapshot_errors(hit: dict[str, Any], idx: int) -> list[str]:
    rel = str(hit.get("snapshot_path") or "")
    if not rel:
        return [f"hit[{idx}] snapshot_path missing"]
    path = REPO / rel.replace("\\", "/")
    if not path.is_file():
        return [f"hit[{idx}] snapshot absent {rel}"]
    sha, _size = digest_file(path)
    want = str(hit.get("snapshot_sha256") or "")
    if sha != want:
        return [f"hit[{idx}] snapshot sha mismatch live={sha} recorded={want}"]
    needle = str(hit.get("claim_text_read") or "")[:120].strip()
    if needle:
        blob = path.read_text(encoding="utf-8", errors="replace")
        compact_blob = strip_markup(blob)
        compact_needle = re.sub(r"\s+", " ", needle)
        if compact_needle not in compact_blob:
            return [
                f"hit[{idx}] claim_text_read prefix not present in snapshot {rel}"
            ]
    return []


def hit_register_errors(doc: dict[str, Any], *, check_snapshots: bool = True) -> list[str]:
    errors: list[str] = []
    if doc.get("unit_id") != UID:
        errors.append(f"unit_id {doc.get('unit_id')!r} != {UID}")
    text = json.dumps(doc, ensure_ascii=True)
    if SENTINEL not in text:
        errors.append("completion sentinel absent")
    hits = doc.get("hit_register")
    if not isinstance(hits, list) or len(hits) < 1:
        errors.append("hit_register missing or empty")
        return errors
    pubs: list[str] = []
    for i, hit in enumerate(hits):
        errors.extend(hit_field_errors(hit, i))
        if isinstance(hit, dict):
            pubs.append(str(hit.get("publication_number") or ""))
            if check_snapshots:
                errors.extend(snapshot_errors(hit, i))
    if not any(p.startswith("US") or p.startswith("CN") for p in pubs):
        errors.append("hit_register has no US or CN publication number")
    return errors


def no_scope_errors(doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    nla = doc.get("not_legal_advice")
    if not isinstance(nla, dict):
        return ["not_legal_advice missing"]
    statement = str(nla.get("statement") or "")
    if NOT_LEGAL_ADVICE not in statement:
        errors.append("not_legal_advice.statement is not the required text")
    if nla.get("downstream_may_treat_as_legal_advice") is not False:
        errors.append("downstream_may_treat_as_legal_advice must be false")
    noscope = doc.get("no_scope_interpretation")
    if not isinstance(noscope, dict):
        errors.append("no_scope_interpretation missing")
    else:
        if NO_SCOPE not in str(noscope.get("statement") or ""):
            errors.append("no_scope_interpretation.statement missing control sentence")
        if noscope.get("scope_interpretation_provided") is not False:
            errors.append("scope_interpretation_provided must be false")
        if noscope.get("scope_may_be_inferred") is not False:
            errors.append("scope_may_be_inferred must be false")
    owner = doc.get("owner_decision")
    if not isinstance(owner, dict):
        errors.append("owner_decision missing")
    else:
        if owner.get("required") is not True:
            errors.append("owner_decision.required must be true when hits exist")
        if owner.get("obtained") is not False:
            errors.append("owner_sign-off must be recorded as not obtained")
        if owner.get("blocks_downstream_action") is not True:
            errors.append("owner_decision must block downstream action")
    interpretive: list[tuple[str, str]] = []
    _walk_interpretive(doc, "", interpretive)
    for path, val in interpretive:
        if path.endswith("claim_text_read"):
            continue
        if SCOPE_FORBIDDEN.search(val):
            errors.append(f"scope-interpretation language at {path}")
    return errors


def validate_hit_register(doc: dict[str, Any], *, check_snapshots: bool = True) -> dict[str, Any]:
    errors = hit_register_errors(doc, check_snapshots=check_snapshots)
    return {"pass": not errors, "errors": errors}


def validate_no_scope(doc: dict[str, Any]) -> dict[str, Any]:
    errors = no_scope_errors(doc)
    return {"pass": not errors, "errors": errors}


def mutant_missing_publication(doc: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(doc)
    hits = out.get("hit_register") or []
    if hits and isinstance(hits[0], dict):
        hits[0].pop("publication_number", None)
    return out


def mutant_empty_register(doc: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(doc)
    out["hit_register"] = []
    return out


def mutant_scope_language(doc: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(doc)
    out["landscape_summary"] = (
        "This patent covers the council runtime and would block implementation."
    )
    return out


def mutant_drop_not_legal_advice(doc: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(doc)
    out["not_legal_advice"] = {"statement": "informational only"}
    return out
