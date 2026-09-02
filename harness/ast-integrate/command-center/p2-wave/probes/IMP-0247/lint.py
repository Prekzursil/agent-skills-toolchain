"""Output lint: every forward-looking claim needs a calibrated band + evidence.

Bare hedges such as 'likely fine' are rejected so an unbanded forecast
cannot be scored later. Historical claims do not require a band.
"""
from __future__ import annotations

import re
from typing import Any

from bands import BANDS, UNBANDED_HEDGES, claim_matches_declared

FORWARD_MARKERS = re.compile(
    r"\b(will|won't|wont|expect|forecast|predict|outlook|over the next|"
    r"within \d+|next (?:quarter|year|two quarters)|scenario|"
    r"operating environment)\b",
    re.I,
)
CALIBRATED_BAND = re.compile(
    r"\b(almost-certain|likely|roughly-even|unlikely|remote)\s*"
    r"\(\s*(\d+)\s*[-–]\s*(\d+)\s*%?\s*\)",
    re.I,
)
EVIDENCE_IN_PROSE = re.compile(
    r"\b(?:evidence(?:_tag)?\s*[:=]\s*\S+|measured at \S+)\b",
    re.I,
)
HEDGE_RE = re.compile(
    "|".join(re.escape(h) for h in UNBANDED_HEDGES),
    re.I,
)


def _prose_calibrated(sentence: str) -> bool:
    m = CALIBRATED_BAND.search(sentence)
    if not m:
        return False
    band = m.group(1).lower()
    lo, hi = int(m.group(2)), int(m.group(3))
    return band in BANDS and (lo, hi) == BANDS[band]


def lint_prose(text: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if not text or not str(text).strip():
        return findings
    parts = re.split(r"(?<=[.!?])\s+", str(text).strip())
    for sent in parts:
        hedge = bool(HEDGE_RE.search(sent))
        forward = bool(FORWARD_MARKERS.search(sent) or hedge)
        calibrated = _prose_calibrated(sent)
        evidenced = bool(EVIDENCE_IN_PROSE.search(sent))
        if hedge and not calibrated:
            findings.append(
                {
                    "code": "unbanded-hedge",
                    "sentence": sent,
                    "reason": (
                        "bare hedge has no calibrated band; "
                        "an unbanded forecast cannot be scored later"
                    ),
                }
            )
            continue
        if forward and not calibrated:
            findings.append(
                {
                    "code": "unbanded-forward-claim",
                    "sentence": sent,
                    "reason": "forward-looking sentence lacks band (low-high%)",
                }
            )
            continue
        if calibrated and not evidenced:
            findings.append(
                {
                    "code": "banded-without-evidence",
                    "sentence": sent,
                    "reason": "calibrated band present but no evidence tag",
                }
            )
    return findings


def lint_claim(claim: dict[str, Any], *, index: int) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    cid = str(claim.get("id") or f"claim[{index}]")
    register = str(claim.get("register") or "").lower()
    text = str(claim.get("text") or "")
    if register not in {"forward-looking", "historical"}:
        findings.append(
            {
                "code": "unknown-register",
                "claim_id": cid,
                "reason": f"register must be forward-looking|historical, got {register!r}",
            }
        )
        return findings
    if register == "historical":
        if claim.get("confidence_band"):
            findings.append(
                {
                    "code": "band-on-historical",
                    "claim_id": cid,
                    "reason": "band attached to a past measured fact (category error)",
                }
            )
        return findings
    band = claim.get("confidence_band")
    evidence = str(claim.get("evidence_tag") or "").strip()
    if not band:
        findings.append(
            {
                "code": "unbanded-forward-claim",
                "claim_id": cid,
                "reason": "forward-looking claim has no confidence_band",
            }
        )
    elif not claim_matches_declared(claim):
        findings.append(
            {
                "code": "band-range-mismatch",
                "claim_id": cid,
                "reason": (
                    f"band {band!r} p_low={claim.get('p_low')!r} "
                    f"p_high={claim.get('p_high')!r} does not match declared "
                    f"{BANDS.get(str(band))}"
                ),
            }
        )
    if not evidence:
        findings.append(
            {
                "code": "missing-evidence-tag",
                "claim_id": cid,
                "reason": "forward-looking claim has no evidence_tag",
            }
        )
    if text and HEDGE_RE.fullmatch(text.strip()) and not band:
        findings.append(
            {
                "code": "unbanded-hedge",
                "claim_id": cid,
                "reason": f"bare hedge {text!r} with no band",
            }
        )
    return findings


def lint_document(doc: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    claims = doc.get("claims") or []
    if not isinstance(claims, list):
        findings.append(
            {"code": "claims-not-list", "reason": "document.claims must be a list"}
        )
        claims = []
    for i, claim in enumerate(claims):
        if isinstance(claim, dict):
            findings.extend(lint_claim(claim, index=i))
        else:
            findings.append(
                {"code": "claim-not-object", "reason": f"claims[{i}] is not an object"}
            )
    prose = doc.get("prose")
    if isinstance(prose, str):
        findings.extend(lint_prose(prose))
    blocking = [f for f in findings if f.get("code") != "band-on-historical"]
    return {
        "ok": len(blocking) == 0,
        "finding_count": len(findings),
        "blocking_count": len(blocking),
        "findings": findings,
        "claim_count": len(claims),
    }
