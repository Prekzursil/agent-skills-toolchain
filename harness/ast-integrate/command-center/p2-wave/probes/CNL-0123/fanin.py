"""CNL-0123 council-of-councils fan-in simulation (not a production runtime).

The parent reads child evidence receipts. A child verdict label and a claimed
digest are claims. Majority of labels is not a completion rule.
"""
from __future__ import annotations

import hashlib
import json
from typing import Callable, Mapping

ReadBytes = Callable[[str], bytes | None]

PASS = "PASS"
REFUTED = "REFUTED"
DISAGREEMENT = "DISAGREEMENT"
FAILED = "FAILED"
RECEIPT_OK = "RECEIPT-OK"
CLAIM_NOT_RECEIPT = "CLAIM-NOT-RECEIPT"
UNPARSEABLE = "UNPARSEABLE"
DIGEST_MISMATCH = "DIGEST-MISMATCH"

RULE_ID = "surface-split-never-majority"
SPEC_ANCHOR = (
    "_USER-PROMPTS.md:11343 nested councils disagree on completion; "
    "digest is a claim not a receipt applies to child councils"
)


def sha256_raw(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def canonical_digest(obj: Mapping) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _excerpt(text: str, n: int = 180) -> str:
    return text[:n]


def read_child_receipt(rel: str, claimed: str, read_bytes: ReadBytes) -> dict:
    raw = read_bytes(rel)
    if raw is None or len(raw.replace(b"\r\n", b"\n")) <= 0:
        return {
            "status": CLAIM_NOT_RECEIPT,
            "sha256": None,
            "bytes": 0,
            "excerpt": None,
        }
    norm = raw.replace(b"\r\n", b"\n")
    digest = hashlib.sha256(norm).hexdigest()
    try:
        text = norm.decode("utf-8")
        parsed = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {
            "status": UNPARSEABLE,
            "sha256": digest,
            "bytes": len(norm),
            "excerpt": None,
        }
    excerpt = _excerpt(json.dumps(parsed, sort_keys=True, separators=(",", ":")))
    if claimed and claimed != digest:
        return {
            "status": DIGEST_MISMATCH,
            "sha256": digest,
            "bytes": len(norm),
            "excerpt": excerpt,
        }
    return {
        "status": RECEIPT_OK,
        "sha256": digest,
        "bytes": len(norm),
        "excerpt": excerpt,
    }


def _tally_key(row: dict) -> str:
    if row["receipt_status"] == RECEIPT_OK:
        return str(row["live_verdict"])
    return str(row["receipt_status"])


def fan_in(children: list[dict], read_bytes: ReadBytes, parent_id: str = "parent") -> dict:
    """Evidence-reading parent. Split child verdicts surface as DISAGREEMENT."""
    ids = [c.get("id") for c in children]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate child id (double-count)")

    rows = []
    for child in children:
        rel = str(child["evidence_path"]).replace("\\", "/")
        claimed = str(child.get("digest") or "")
        receipt = read_child_receipt(rel, claimed, read_bytes)
        ok = receipt["status"] == RECEIPT_OK
        rows.append(
            {
                "id": child["id"],
                "claimed_verdict": child["verdict"],
                "receipt_status": receipt["status"],
                "evidence_path": rel,
                "claimed_digest": claimed or None,
                "evidence_sha256": receipt["sha256"],
                "evidence_bytes": receipt["bytes"],
                "evidence_excerpt": receipt["excerpt"],
                "live_verdict": child["verdict"] if ok else None,
            }
        )

    live = [r for r in rows if r["live_verdict"] is not None]
    failures = [r for r in rows if r["receipt_status"] != RECEIPT_OK]
    distinct = sorted({r["live_verdict"] for r in live})
    tally: dict[str, int] = {}
    for row in rows:
        key = _tally_key(row)
        tally[key] = tally.get(key, 0) + 1

    if not live:
        verdict, reason = FAILED, "no-child-receipt"
    elif failures:
        verdict, reason = DISAGREEMENT, "claim-not-receipt"
    elif len(distinct) == 1 and distinct[0] == PASS:
        verdict, reason = PASS, "unanimous-pass-with-receipts"
    elif len(distinct) == 1:
        verdict, reason = distinct[0], "unanimous-nonpass-with-receipts"
    else:
        verdict, reason = DISAGREEMENT, "nested-councils-disagree-on-completion"

    minority = [r for r in live if r["live_verdict"] != PASS]
    label_counts: dict[str, int] = {}
    for child in children:
        v = str(child["verdict"])
        label_counts[v] = label_counts.get(v, 0) + 1
    majority_label = max(label_counts, key=lambda k: (label_counts[k], k))

    body = {
        "parent_id": parent_id,
        "verdict": verdict,
        "reason": reason,
        "rule_id": RULE_ID,
        "spec_anchor": SPEC_ANCHOR,
        "majority_forbidden": True,
        "majority_of_labels": majority_label,
        "children": rows,
        "tally": tally,
        "distinct_source_count": len(rows),
        "distinct_live_verdicts": distinct,
        "minority": minority,
    }
    out = dict(body)
    out["parent_digest"] = canonical_digest(body)
    return out


def vote_count_parent(children: list[dict], parent_id: str = "vote-counter") -> dict:
    """Known-broken parent: hashes only (id, verdict). Ignores evidence.

    This is the negative-control substrate. It is not the spec.
    """
    votes = sorted((str(c["id"]), str(c["verdict"])) for c in children)
    tally: dict[str, int] = {}
    for _cid, verdict in votes:
        tally[verdict] = tally.get(verdict, 0) + 1
    winner = max(tally, key=lambda k: (tally[k], k))
    body = {
        "parent_id": parent_id,
        "verdict": winner,
        "reason": "majority-of-child-labels",
        "votes": votes,
        "tally": tally,
        "reads_evidence": False,
    }
    out = dict(body)
    out["parent_digest"] = canonical_digest(body)
    return out


def recount(parent: Mapping) -> dict[str, int]:
    tally: dict[str, int] = {}
    for row in parent.get("children") or []:
        if not isinstance(row, dict):
            continue
        key = _tally_key(row)
        tally[key] = tally.get(key, 0) + 1
    return tally
