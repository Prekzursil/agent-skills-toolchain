#!/usr/bin/env python3
"""Shared structural checks for RES-0067 (hashes, dual rails, anti-adoption)."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART_REL = "command-center/research/RES-0067.json"
SENTINEL = (
    "SUCCESS:RES-0067 in the receipt AND a corroborate-or-refute verdict "
    "on anti-adoption 1 plus at least one counter-case reported"
)
VERDICTS = frozenset({"CORROBORATED", "REFUTED", "PARTIAL"})
RAIL_KINDS = frozenset({"api", "prose"})
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
REQUIRED_CLAIM_IDS = frozenset(
    {
        "C-DAGGER-CUE-TO-SDK",
        "C-JENKINS-DECLARATIVE",
        "C-GHA-HCL-TO-YAML",
        "C-PREFECT-DAG-FREE",
        "C-AIRFLOW-PYTHON-VS-XML",
        "C-ASL-IR-PLUS-CDK",
    }
)


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_path(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return digest_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def load_artifact(path: Path | None = None) -> dict[str, Any]:
    target = path or (REPO / ART_REL)
    return json.loads(target.read_text(encoding="utf-8"))


def capture_haystack(raw: bytes) -> str:
    text = raw.decode("utf-8", "replace")
    hay = text
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return hay
    if isinstance(doc, dict) and doc.get("encoding") == "base64" and doc.get("content"):
        try:
            hay += "\n" + base64.b64decode(doc["content"]).decode("utf-8", "replace")
        except (ValueError, TypeError, UnicodeDecodeError):
            pass
    return hay


def fail(reason: str) -> tuple[bool, str]:
    return False, reason


def check_structure(doc: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return fail("not-an-object")
    if doc.get("unit_id") != "RES-0067":
        return fail(f"unit_id:{doc.get('unit_id')}")
    state = str(doc.get("state") or "").upper()
    if state in NOT_DELIVERING:
        return fail(f"self-declared:{state}")
    if state != "SUCCESS":
        return fail(f"state:{state}")
    blob = json.dumps(doc, ensure_ascii=False)
    if SENTINEL not in blob:
        return fail("sentinel-absent")
    aa = doc.get("anti_adoption") or {}
    if not isinstance(aa, dict):
        return fail("anti-adoption-missing")
    label_blob = f"{aa.get('id') or ''} {aa.get('label') or ''}".lower()
    if "anti-adoption-1" not in label_blob and "anti-adoption 1" not in label_blob:
        return fail("anti-adoption-id")
    statement = str(aa.get("statement") or "")
    if "do not build a workflow language" not in statement.lower():
        return fail("anti-adoption-statement-absent")
    verdict = str(aa.get("verdict") or "").upper()
    if verdict not in VERDICTS:
        return fail(f"anti-adoption-verdict:{verdict}")
    cases = doc.get("counter_cases") or []
    against = [
        c
        for c in cases
        if isinstance(c, dict) and c.get("cuts_against_anti_adoption") is True
    ]
    if not against:
        return fail("counter-case-absent")
    claims = doc.get("claims") or []
    if not isinstance(claims, list) or len(claims) < 4:
        return fail(f"claims-count:{len(claims) if isinstance(claims, list) else 'na'}")
    ids = {c.get("id") for c in claims if isinstance(c, dict)}
    missing = REQUIRED_CLAIM_IDS - ids
    if missing:
        return fail(f"required-claims-missing:{sorted(missing)}")
    return True, "structure-ok"


def _rails_of(claim: dict[str, Any]) -> list[dict[str, Any]]:
    rails = claim.get("rails") or claim.get("evidence_rails") or []
    return [r for r in rails if isinstance(r, dict)]


def check_rails(doc: dict[str, Any]) -> tuple[bool, str]:
    claims = doc.get("claims") or []
    for claim in claims:
        if not isinstance(claim, dict):
            return fail("claim-not-object")
        cid = str(claim.get("id") or "?")
        rails = _rails_of(claim)
        if len(rails) < 2:
            return fail(f"{cid}:single-signal-only")
        kinds = {str(r.get("kind") or "") for r in rails}
        if not {"api", "prose"} <= kinds:
            return fail(f"{cid}:rails-not-api-and-prose:{sorted(kinds)}")
        for i, rail in enumerate(rails):
            kind = str(rail.get("kind") or "")
            if kind not in RAIL_KINDS:
                return fail(f"{cid}:rail[{i}]-kind:{kind}")
            status = rail.get("http_status")
            if not isinstance(status, int) or status < 200 or status >= 300:
                return fail(f"{cid}:rail[{i}]-http:{status}")
            permalink = str(rail.get("permalink") or "")
            if not permalink.startswith("http"):
                return fail(f"{cid}:rail[{i}]-permalink")
            ts = str(rail.get("fetch_timestamp") or "")
            if len(ts) < 16:
                return fail(f"{cid}:rail[{i}]-timestamp")
            rel = str(rail.get("capture_path") or "")
            cap = REPO / rel
            if not cap.is_file():
                return fail(f"{cid}:rail[{i}]-capture-absent:{rel}")
            live_sha, live_bytes = digest_path(cap)
            rec_sha = str(rail.get("sha256") or "")
            if rec_sha != live_sha:
                return fail(f"{cid}:rail[{i}]-sha-mismatch")
            rec_bytes = rail.get("bytes")
            if rec_bytes is not None and int(rec_bytes) != live_bytes and int(rec_bytes) != cap.stat().st_size:
                # tolerate raw vs LF-normalised length if sha already matched
                if int(rec_bytes) not in {live_bytes, cap.stat().st_size}:
                    return fail(f"{cid}:rail[{i}]-bytes-mismatch")
            quote = str(rail.get("quote") or "")
            if len(quote) < 8:
                return fail(f"{cid}:rail[{i}]-quote-too-short")
        tier = str(claim.get("evidence_tier") or "")
        if tier in {"E3", "E4"}:
            return fail(f"{cid}:tier-{tier}-not-citable")
        if tier not in {"E1", "E2"}:
            return fail(f"{cid}:tier:{tier}")
    return True, "rails-ok"


def check_quotes(doc: dict[str, Any]) -> tuple[bool, str]:
    for claim in doc.get("claims") or []:
        if not isinstance(claim, dict):
            return fail("claim-not-object")
        cid = str(claim.get("id") or "?")
        for i, rail in enumerate(_rails_of(claim)):
            rel = str(rail.get("capture_path") or "")
            cap = REPO / rel
            hay = capture_haystack(cap.read_bytes())
            quote = str(rail.get("quote") or "")
            if quote not in hay:
                return fail(f"{cid}:rail[{i}]-quote-not-in-capture")
    return True, "quotes-ok"


def check_anti_adoption(doc: dict[str, Any]) -> tuple[bool, str]:
    aa = doc.get("anti_adoption") or {}
    verdict = str(aa.get("verdict") or "").upper()
    against = [
        c
        for c in (doc.get("counter_cases") or [])
        if isinstance(c, dict) and c.get("cuts_against_anti_adoption") is True
    ]
    # Failure mode named by the unit: confirming the inherited position
    # without testing it. A CORROBORATED verdict with zero counter-cases
    # is that failure. REFUTED/PARTIAL still require a named counter-case.
    if verdict == "CORROBORATED" and not against:
        return fail("untested-corroboration")
    if not against:
        return fail("counter-case-absent")
    jenkins = [
        c
        for c in against
        if str(c.get("engine") or "").lower() == "jenkins"
        or str(c.get("claim_id") or "") == "C-JENKINS-DECLARATIVE"
    ]
    if not jenkins:
        return fail("named-counter-case-jenkins-absent")
    return True, f"anti-adoption:{verdict}:counter-cases={len(against)}"
