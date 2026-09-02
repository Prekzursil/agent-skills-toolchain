"""Adjudicate each disagreement from the decisive probe, never from head count."""
from __future__ import annotations

from typing import Any

from cases import CASES, with_wording
from router import classify_to_disposition, close


def classify(probe: dict[str, Any]) -> str:
    if probe.get("code_ok") and not probe.get("sentence_ok"):
        return "overclaim"
    if not probe.get("code_ok"):
        return "real-defect"
    if probe.get("irreducible"):
        return "irreducible-disagreement"
    return "overclaim" if not probe.get("sentence_ok") else "real-defect"


def majority_side(votes: dict[str, int]) -> str:
    i = int(votes.get("implementer") or 0)
    c = int(votes.get("confirmer") or 0)
    if i > c:
        return "implementer"
    if c > i:
        return "confirmer"
    return "tie"


def adjudicate_one(case: dict[str, Any]) -> dict[str, Any]:
    row = with_wording(case)
    probe = case["probe"]()
    votes = dict(row["agent_votes"])
    if probe.get("agent_votes"):
        votes = dict(probe["agent_votes"])
    # THE RULE: probe.supports wins. Votes are recorded, never consulted.
    winning = probe["supports"]
    maj = majority_side(votes)
    classification = classify(probe)
    original = row["original_wording"]
    scoped = row["scoped"]
    if classification == "overclaim" and original == scoped:
        raise RuntimeError(f"{row['id']}: overclaim scoped statement equals original wording")
    rec = {
        "id": row["id"],
        "disposition": classify_to_disposition(classification),
    }
    ok, why = close(rec)
    if not ok:
        raise RuntimeError(f"{row['id']}: router refused {why}")
    return {
        "id": row["id"],
        "original_wording": original,
        "implementer_verdict": row["implementer_verdict"],
        "implementer_reasoning": row["implementer_reasoning"],
        "confirmer_verdict": row["confirmer_verdict"],
        "confirmer_reasoning": row["confirmer_reasoning"],
        "agent_votes": votes,
        "majority_would_have_picked": maj,
        "majority_overridden": maj != "tie" and maj != winning,
        "adjudication_method": "decisive-probe",
        "classification": classification,
        "winning_side": winning,
        "code_was_fine": bool(probe.get("code_ok")),
        "sentence_ok": bool(probe.get("sentence_ok")),
        "correctly_scoped_statement": scoped,
        "raw_source": row["raw_source"],
        "claim_path": row["claim_path"],
        "router": {"closed": True, "disposition": rec["disposition"], "why": why},
        "decisive_probe": {
            "id": probe["id"],
            "output": probe["output"],
            "supports": probe["supports"],
            "code_ok": probe.get("code_ok"),
            "sentence_ok": probe.get("sentence_ok"),
        },
    }


def adjudicate_all() -> list[dict[str, Any]]:
    return [adjudicate_one(c) for c in CASES]
