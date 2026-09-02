"""Mechanical checks for coverage, recruitment efficacy, and false-gap silence."""
from __future__ import annotations

from typing import Any

from fixtures import UNIQUE_CLAIM_ID, UNIQUE_CLAIM_TEXT


def hole_verdict(run: dict[str, Any]) -> dict[str, Any]:
    cov = run.get("coverage") or {}
    rec = run.get("recruitment") or {}
    transcript = str(run.get("transcript") or "")
    exclusive = list(run.get("exclusive_claims") or [])
    exclusive_ids = {str(c.get("id")) for c in exclusive}
    reasons: list[str] = []
    named = list(cov.get("named_gap") or [])
    if "cryptography" not in named:
        reasons.append("gap-not-named:cryptography")
    if not cov.get("fires"):
        reasons.append("coverage-silent-on-hole")
    if rec.get("trigger") != "missing-expertise":
        reasons.append("trigger-not-missing-expertise")
    if not rec.get("triggered") or not rec.get("executed"):
        reasons.append("recruitment-did-not-execute")
    if "recruited-crypto-critic" not in (rec.get("seated_ids") or []):
        reasons.append("crypto-critic-not-seated")
    if UNIQUE_CLAIM_ID not in exclusive_ids:
        reasons.append("exclusive-claim-missing")
    if UNIQUE_CLAIM_TEXT not in transcript:
        reasons.append("exclusive-claim-not-in-transcript")
    if rec.get("cosmetic"):
        reasons.append("recruitment-cosmetic")
    authors = {c.get("author") for c in exclusive if c.get("id") == UNIQUE_CLAIM_ID}
    if authors and authors != {"recruited-crypto-critic"}:
        reasons.append("exclusive-claim-wrong-author")
    original_ids = {c.get("id") for c in (run.get("original_claims") or [])}
    if UNIQUE_CLAIM_ID in original_ids:
        reasons.append("exclusive-claim-already-in-round1")
    return {
        "pass": not reasons,
        "reasons": reasons,
        "named_gap": named,
        "uncovered_competency": "cryptography" if "cryptography" in named else None,
        "trigger": rec.get("trigger"),
        "exclusive_claim_id": UNIQUE_CLAIM_ID if UNIQUE_CLAIM_ID in exclusive_ids else None,
        "exclusive_claim_author": "recruited-crypto-critic" if UNIQUE_CLAIM_ID in exclusive_ids else None,
    }


def covered_verdict(run: dict[str, Any]) -> dict[str, Any]:
    cov = run.get("coverage") or {}
    rec = run.get("recruitment") or {}
    transcript = str(run.get("transcript") or "")
    reasons: list[str] = []
    if cov.get("fires"):
        reasons.append("false-gap-fired")
    if cov.get("uncovered"):
        reasons.append("false-gap-named")
    if rec.get("triggered") or rec.get("executed"):
        reasons.append("false-gap-recruited")
    if rec.get("seated_ids"):
        reasons.append("false-gap-seated")
    if UNIQUE_CLAIM_ID in transcript or UNIQUE_CLAIM_TEXT in transcript:
        reasons.append("recruited-claim-leaked-into-covered")
    required = list(cov.get("required") or [])
    covered = set(cov.get("covered") or [])
    if set(required) != covered:
        reasons.append("covered-set-incomplete")
    return {
        "pass": not reasons,
        "reasons": reasons,
        "uncovered": list(cov.get("uncovered") or []),
        "triggered": bool(rec.get("triggered")),
    }


def cosmetic_verdict(run: dict[str, Any]) -> dict[str, Any]:
    rec = run.get("recruitment") or {}
    exclusive = list(run.get("exclusive_claims") or [])
    fired = bool(rec.get("executed")) and (rec.get("cosmetic") is True) and not exclusive
    reasons: list[str] = []
    if not rec.get("executed"):
        reasons.append("rubberstamp-did-not-recruit")
    if exclusive:
        reasons.append("rubberstamp-emitted-new-claim")
    if rec.get("cosmetic") is not True:
        reasons.append("cosmetic-flag-not-set")
    return {
        "pass": fired and not reasons,
        "reasons": reasons,
        "cosmetic": rec.get("cosmetic"),
        "classification": "cosmetic-recruitment" if fired else None,
    }


def synonym_verdict(run: dict[str, Any]) -> dict[str, Any]:
    cov = run.get("coverage") or {}
    named = list(cov.get("named_gap") or [])
    ignored = list(cov.get("undeclared_ids_ignored") or [])
    reasons: list[str] = []
    for need in ("cryptography", "threat-modeling", "legal-compliance"):
        if need not in named:
            reasons.append(f"synonym-covered-{need}")
    if not cov.get("fires"):
        reasons.append("synonym-panel-silent")
    if "crypto" not in ignored:
        reasons.append("alias-crypto-not-ignored")
    return {"pass": not reasons, "reasons": reasons, "named_gap": named, "ignored": ignored}
