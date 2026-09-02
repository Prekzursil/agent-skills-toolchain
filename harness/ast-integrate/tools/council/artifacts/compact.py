"""Council compact: copy dissent verbatim into reinjection; decide from votes."""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def collect_records(transcript: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    claims: dict[str, dict[str, Any]] = {}
    for claim in transcript.get("claims") or []:
        if isinstance(claim, dict) and claim.get("id"):
            claims[str(claim["id"])] = dict(claim)
    dissents: dict[str, dict[str, Any]] = {}
    for dissent in transcript.get("dissents") or []:
        if isinstance(dissent, dict) and dissent.get("id"):
            dissents[str(dissent["id"])] = dict(dissent)
    return {"claim": claims, "dissent": dissents}


def compact(transcript: dict[str, Any]) -> dict[str, Any]:
    """Least-sanitised path: dissent statements are copied verbatim into reinjection."""
    chunks: list[str] = []
    for dissent in transcript.get("dissents") or []:
        if isinstance(dissent, dict) and isinstance(dissent.get("statement"), str):
            chunks.append(dissent["statement"])
    scores: dict[str, float] = defaultdict(float)
    for vote in transcript.get("votes") or []:
        if not isinstance(vote, dict):
            continue
        choice = str(vote.get("choice") or "")
        if not choice:
            continue
        try:
            weight = float(vote.get("weight") or 1)
        except (TypeError, ValueError):
            weight = 1.0
        scores[choice] += weight
    winner = ""
    if scores:
        winner = max(sorted(scores), key=lambda cid: (scores[cid], cid))
    return {
        "kind": "compact",
        "reinjection": "\n".join(chunks),
        "scores": dict(scores),
        "winner_claim_id": winner,
        "records": collect_records(transcript),
    }


def decide_compact(compacted: dict[str, Any]) -> dict[str, Any]:
    """Winner from vote weights / edges, never from English in briefs."""
    scores = compacted.get("scores") or {}
    winner = str(compacted.get("winner_claim_id") or "")
    if scores and not winner:
        winner = max(sorted(scores), key=lambda cid: (float(scores[cid]), cid))
    return {
        "winner_claim_id": winner,
        "scores": dict(scores),
        "source": "votes",
    }


KINDS = ("claim", "objection", "dissent")


def _ids_from_registry(transcript: dict[str, Any], kind: str) -> list[str]:
    registry = transcript.get("registry") or {}
    key = {"claim": "claims", "objection": "objections", "dissent": "dissents"}[kind]
    rows = list(transcript.get(key) or []) + list(registry.get(key) or [])
    out: list[str] = []
    for row in rows:
        if isinstance(row, dict) and row.get("id") and str(row["id"]) not in out:
            out.append(str(row["id"]))
    for turn in transcript.get("turns") or []:
        if not isinstance(turn, dict):
            continue
        for row in turn.get(key) or []:
            if isinstance(row, dict) and row.get("id") and str(row["id"]) not in out:
                out.append(str(row["id"]))
    return out


def collect_ids(transcript: dict[str, Any]) -> dict[str, set[str]]:
    return {kind: set(_ids_from_registry(transcript, kind)) for kind in KINDS}


def _decision(transcript: dict[str, Any] | None, compacted: dict[str, Any] | None) -> dict[str, Any]:
    src = compacted if isinstance(compacted, dict) else {}
    votes = (transcript or {}).get("votes") if transcript else src.get("votes")
    scores: dict[str, float] = {}
    for vote in votes or src.get("votes") or []:
        if not isinstance(vote, dict):
            continue
        choice = str(vote.get("choice") or "")
        if not choice:
            continue
        try:
            weight = float(vote.get("weight") or 1)
        except (TypeError, ValueError):
            weight = 1.0
        scores[choice] = scores.get(choice, 0.0) + weight
    winner = ""
    if scores:
        winner = max(sorted(scores), key=lambda cid: (scores[cid], cid))
    dissent_ids = []
    if compacted and compacted.get("order"):
        dissent_ids = list((compacted.get("order") or {}).get("dissent") or [])
    elif transcript:
        dissent_ids = sorted(collect_ids(transcript)["dissent"])
    return {"winner_claim_id": winner, "dissent_ids": dissent_ids, "scores": scores}


def compact(transcript: dict[str, Any]) -> dict[str, Any]:  # type: ignore[no-redef]
    """Lossless-by-id compact form: keep ids and verbatim dissent, drop turn padding."""
    ids = collect_ids(transcript)
    records = collect_records(transcript)
    chunks: list[str] = []
    for dissent in (transcript.get("registry") or {}).get("dissents") or transcript.get("dissents") or []:
        if isinstance(dissent, dict) and isinstance(dissent.get("statement"), str):
            chunks.append(dissent["statement"])
    decided = _decision(transcript, None)
    return {
        "kind": "compact",
        "reinjection": "\n".join(chunks),
        "order": {k: sorted(v) for k, v in ids.items()},
        "records": records,
        "votes": list(transcript.get("votes") or []),
        "winner_claim_id": decided["winner_claim_id"],
        "scores": decided["scores"],
        "dissent_ids": decided["dissent_ids"],
    }


def reachability(transcript: dict[str, Any], compacted: dict[str, Any]) -> dict[str, Any]:
    full = collect_ids(transcript)
    order = compacted.get("order") or {}
    reachable = {k: set(order.get(k) or []) for k in KINDS}
    unreachable = {k: sorted(full[k] - reachable[k]) for k in KINDS}
    invented = {k: sorted(reachable[k] - full[k]) for k in KINDS}
    counts_full = {k: len(full[k]) for k in KINDS}
    counts_reach = {k: len(reachable[k]) for k in KINDS}
    counts_un = {k: len(unreachable[k]) for k in KINDS}
    claim_loss = counts_un["claim"]
    zero_claim = claim_loss == 0
    zero_loss = all(counts_un[k] == 0 for k in KINDS)
    fires = (not zero_loss) or any(invented[k] for k in KINDS)
    return {
        "full_counts": counts_full,
        "reachable_counts": counts_reach,
        "unreachable_counts": counts_un,
        "unreachable": unreachable,
        "invented": invented,
        "claim_id_loss": claim_loss,
        "zero_claim_loss": zero_claim,
        "zero_loss": zero_loss,
        "fires": fires,
    }


def measure_compaction(transcript: dict[str, Any]) -> dict[str, Any]:
    import json as _json

    compacted = compact(transcript)
    full_bytes = len(_json.dumps(transcript).encode("utf-8"))
    compact_bytes = len(_json.dumps(compacted).encode("utf-8"))
    report = reachability(transcript, compacted)
    return {
        "compacted": compacted,
        "reachability": report,
        "full_bytes": full_bytes,
        "compact_bytes": compact_bytes,
        "shrank": compact_bytes < full_bytes,
    }


def drop_one_dissent(transcript: dict[str, Any], dissent_id: str) -> tuple[dict[str, Any], str]:
    compacted = compact(transcript)
    order = dict(compacted.get("order") or {})
    dissents = [d for d in (order.get("dissent") or []) if d != dissent_id]
    order["dissent"] = dissents
    compacted["order"] = order
    compacted["dissent_ids"] = dissents
    recs = compacted.get("records") or {}
    if isinstance(recs, dict) and "dissent" in recs and dissent_id in recs["dissent"]:
        recs["dissent"] = dict(recs["dissent"])
        recs["dissent"].pop(dissent_id, None)
    return compacted, dissent_id


def decisions_match(transcript: dict[str, Any], compacted: dict[str, Any]) -> dict[str, Any]:
    full = _decision(transcript, None)
    compact_dec = _decision(transcript, compacted)
    return {
        "identical": full["winner_claim_id"] == compact_dec["winner_claim_id"],
        "full": full,
        "compacted": compact_dec,
    }
