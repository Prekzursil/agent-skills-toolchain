"""Dissent-preservation check: set-diff of claim ids PLUS token/counterexample.

A check that is green on both the intact synthesis and a planted drop
measures nothing. This check is silent only when every transcript dissent
claim_id, its unique token, and its counterexample all appear in synthesis.
Generic 'dissent was considered' language does not satisfy the check.
"""
from __future__ import annotations

import json
from typing import Any

GENERIC_PHRASES = (
    "dissent was considered",
    "dissent was noted",
    "minority views were heard",
)


def dissent_claims(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for turn in transcript.get("turns") or []:
        if not isinstance(turn, dict):
            continue
        if str(turn.get("vote") or "").upper() != "NO":
            continue
        claims.append(
            {
                "claim_id": str(turn.get("claim_id") or ""),
                "token": str(turn.get("token") or ""),
                "counterexample": str(turn.get("counterexample") or ""),
                "participant_id": str(turn.get("participant_id") or ""),
            }
        )
    return [c for c in claims if c["claim_id"]]


def report_claim_ids(synthesis: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for row in synthesis.get("minority_report") or []:
        if isinstance(row, dict) and row.get("claim_id"):
            ids.add(str(row["claim_id"]))
    return ids


def synthesis_blob(synthesis: dict[str, Any]) -> str:
    return json.dumps(synthesis, ensure_ascii=True, sort_keys=True)


def check(transcript: dict[str, Any], synthesis: dict[str, Any]) -> dict[str, Any]:
    claims = dissent_claims(transcript)
    n = len(claims)
    if n != 1:
        return {
            "ok": False,
            "verdict": "RED",
            "fired": True,
            "reason": "expected-exactly-one-dissent",
            "dissent_count": n,
            "lost_claim_ids": [],
            "token_present": False,
            "counterexample_present": False,
            "generic_phrase_only": False,
        }
    d = claims[0]
    lost = sorted({d["claim_id"]} - report_claim_ids(synthesis))
    blob = synthesis_blob(synthesis)
    token_present = bool(d["token"]) and d["token"] in blob
    cex_present = bool(d["counterexample"]) and d["counterexample"] in blob
    generic_hit = any(p in blob.lower() for p in GENERIC_PHRASES)
    generic_only = generic_hit and not token_present
    fired = bool(lost) or (not token_present) or (not cex_present)
    return {
        "ok": not fired,
        "verdict": "RED" if fired else "GREEN",
        "fired": fired,
        "silent": not fired,
        "reason": "lost-or-stripped" if fired else "preserved",
        "dissent_count": n,
        "lost_claim_ids": lost,
        "token_present": token_present,
        "counterexample_present": cex_present,
        "generic_phrase_only": generic_only,
        "claim_id": d["claim_id"],
        "token": d["token"],
        "signals": ["claim-id-set-diff", "token-and-counterexample-in-synthesis-json"],
    }


def vacuous_nonempty(synthesis: dict[str, Any]) -> bool:
    """A check green in both states: synthesis exists and has a decision string."""
    return bool(synthesis) and bool(str(synthesis.get("decision") or "").strip())
