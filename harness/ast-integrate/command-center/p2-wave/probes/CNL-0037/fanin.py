"""Executable nested-council fan-in (CNL-0037)."""
from __future__ import annotations

import hashlib
import json
from typing import Any

CLAIM_VERDICTS = frozenset({"PASS", "REFUTED", "BLOCKED", "INCOMPLETE"})
TERMINAL_COMPLETE = frozenset({"PASS", "REFUTED"})


def evidence_digest(eid: str, body: str) -> str:
    blob = json.dumps({"id": eid, "body": body}, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _normalize_child(raw: dict[str, Any]) -> dict[str, Any]:
    cid = str(raw.get("child_id") or "")
    claimed = str(raw.get("verdict") or "")
    present = bool(raw.get("artifact_present"))
    nbytes = int(raw.get("artifact_bytes") or 0)
    dissent = list(raw.get("dissent") or [])
    evidence: list[dict[str, Any]] = []
    for rec in list(raw.get("evidence") or []):
        eid = str(rec.get("id") or "")
        body = str(rec.get("body") or "")
        if not eid or not body.strip():
            continue
        digest = evidence_digest(eid, body)
        given = rec.get("digest")
        if given not in (None, "") and str(given) != digest:
            return {
                "child_id": cid,
                "normalized": "MALFORMED",
                "claimed": claimed,
                "reason": "EVIDENCE_DIGEST_MISMATCH",
                "artifact_present": present,
                "artifact_bytes": nbytes,
                "evidence": [],
                "dissent": dissent,
            }
        evidence.append({"id": eid, "body": body, "digest": digest})
    if not cid:
        normalized, reason = "MALFORMED", "MISSING_CHILD_ID"
    elif claimed not in CLAIM_VERDICTS:
        normalized, reason = "MALFORMED", "UNKNOWN_CLAIMED_VERDICT"
    elif (not present) or nbytes <= 0:
        normalized, reason = "INCOMPLETE", "DIGEST_IS_CLAIM_NOT_RECEIPT"
    elif not evidence:
        normalized, reason = "INCOMPLETE", "VERDICT_WITHOUT_EVIDENCE"
    else:
        normalized, reason = claimed, "EVIDENCE_PRESENT"
    return {
        "child_id": cid,
        "normalized": normalized,
        "claimed": claimed,
        "reason": reason,
        "artifact_present": present,
        "artifact_bytes": nbytes,
        "evidence": evidence,
        "dissent": dissent,
    }


def _validate_overrule(overrule, by_id, ingested):
    if not overrule:
        return {"accepted": False, "reason": "NO_OVERRULE", "target": None}
    target = str(overrule.get("target_child_id") or "")
    new_verdict = str(overrule.get("new_verdict") or "")
    cited = list(overrule.get("cited") or [])
    child = by_id.get(target)
    if child is None:
        return {"accepted": False, "reason": "UNKNOWN_TARGET", "target": target}
    if new_verdict not in CLAIM_VERDICTS:
        return {"accepted": False, "reason": "BAD_NEW_VERDICT", "target": target}
    if not cited:
        return {"accepted": False, "reason": "NO_CITE", "target": target}
    ev_by_id = {row["id"]: row for row in child["evidence"]}
    for item in cited:
        eid = str(item.get("id") or "")
        digest = str(item.get("digest") or "")
        rec = ev_by_id.get(eid)
        if rec is None:
            return {"accepted": False, "reason": "CITE_NOT_FROM_TARGET_CHILD", "target": target}
        if digest != rec["digest"]:
            return {"accepted": False, "reason": "DIGEST_MISMATCH", "target": target}
        if eid not in ingested:
            return {"accepted": False, "reason": "BLIND_OVERRULE", "target": target}
        if ingested[eid] != rec["body"]:
            return {"accepted": False, "reason": "INGESTED_BODY_MISMATCH", "target": target}
    return {"accepted": True, "reason": "EVIDENCE_GATED", "target": target, "new_verdict": new_verdict}


def fan_in(payload: dict[str, Any]) -> dict[str, Any]:
    children_raw = list(payload.get("children") or [])
    required = list(payload.get("required_child_ids") or [c.get("child_id") for c in children_raw])
    ingested = dict(payload.get("parent_ingested") or {})
    overrule = payload.get("overrule")
    ids = [str(c.get("child_id") or "") for c in children_raw]
    if len(ids) != len(set(ids)):
        return {
            "outcome": "MALFORMED",
            "parent_complete": False,
            "fan_in_defined": True,
            "majority_suppressed": True,
            "overrule": {"accepted": False, "reason": "DUPLICATE_CHILD_ID", "target": None},
            "children": [],
            "forwarded_dissent_ids": [],
            "verdict_set": [],
            "rule": "FANIN-NESTED-V1",
        }
    children = [_normalize_child(c) for c in children_raw]
    by_id = {c["child_id"]: c for c in children}
    dissent_ids = []
    for child in children:
        for row in child["dissent"]:
            did = str(row.get("id") or "")
            if did:
                dissent_ids.append(did)
    if any(c["normalized"] == "MALFORMED" for c in children):
        return {
            "outcome": "MALFORMED",
            "parent_complete": False,
            "fan_in_defined": True,
            "majority_suppressed": True,
            "overrule": {"accepted": False, "reason": "CHILD_MALFORMED", "target": None},
            "children": children,
            "forwarded_dissent_ids": dissent_ids,
            "verdict_set": sorted({c["normalized"] for c in children}),
            "rule": "FANIN-NESTED-V1",
        }
    incomplete = [c for c in children if c["child_id"] in required and c["normalized"] == "INCOMPLETE"]
    if incomplete:
        return {
            "outcome": "INCOMPLETE",
            "parent_complete": False,
            "fan_in_defined": True,
            "majority_suppressed": True,
            "overrule": {"accepted": False, "reason": "REQUIRED_CHILD_INCOMPLETE", "target": None},
            "children": children,
            "forwarded_dissent_ids": dissent_ids,
            "verdict_set": sorted({c["normalized"] for c in children}),
            "incomplete_child_ids": [c["child_id"] for c in incomplete],
            "rule": "FANIN-NESTED-V1",
        }
    ov = _validate_overrule(overrule, by_id, ingested)
    working = {c["child_id"]: c["normalized"] for c in children}
    if ov["accepted"]:
        working[ov["target"]] = ov["new_verdict"]
    verdict_set = sorted(set(working.values()))
    if len(verdict_set) == 1:
        outcome = verdict_set[0]
        return {
            "outcome": outcome,
            "parent_complete": outcome in TERMINAL_COMPLETE,
            "fan_in_defined": True,
            "majority_suppressed": True,
            "overrule": ov,
            "children": children,
            "forwarded_dissent_ids": dissent_ids,
            "verdict_set": verdict_set,
            "working_verdicts": working,
            "rule": "FANIN-NESTED-V1",
        }
    return {
        "outcome": "IRREDUCIBLE_DISAGREEMENT",
        "parent_complete": False,
        "fan_in_defined": True,
        "majority_suppressed": True,
        "overrule": ov,
        "children": children,
        "forwarded_dissent_ids": dissent_ids,
        "verdict_set": verdict_set,
        "working_verdicts": working,
        "rule": "FANIN-NESTED-V1",
    }


def majority_would_pass(payload: dict[str, Any]) -> bool:
    claims = [str(c.get("verdict") or "") for c in payload.get("children") or []]
    if not claims:
        return False
    wins: dict[str, int] = {}
    for v in claims:
        wins[v] = wins.get(v, 0) + 1
    top = max(wins.values())
    leaders = [k for k, n in wins.items() if n == top]
    return "PASS" in leaders and top > len(claims) / 2
