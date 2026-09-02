"""Recompute each promotion condition from named receipts. Never fold absence into pass."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

from conditions import PROMOTION_CONDITIONS, SUBSTITUTE_RECEIPTS
from catalog_bind import oq9_substitute

Lookup = Callable[[str], dict | None]

SATISFIED = "SATISFIED"
NOT_CHECKED = "NOT-CHECKED"
UNSAT = "UNSATISFIABLE-AS-WRITTEN"
FALSE = "FALSE"


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def disk_lookup(root: Path) -> Lookup:
    def lookup(rel: str) -> dict | None:
        path = root / rel
        if not path.is_file():
            return None
        try:
            raw = path.read_bytes()
        except OSError:
            return None
        if len(raw) <= 0:
            return None
        return {
            "path": rel,
            "present": True,
            "bytes": len(raw.replace(b"\r\n", b"\n")),
            "sha256": digest_bytes(raw),
            "raw": raw,
        }

    return lookup


def consult(rel: str, lookup: Lookup) -> dict:
    hit = lookup(rel)
    if not hit:
        return {"path": rel, "present": False, "bytes": 0, "sha256": None}
    return {
        "path": rel,
        "present": True,
        "bytes": int(hit.get("bytes") or 0),
        "sha256": hit.get("sha256"),
    }


def receipt_supports(raw: bytes) -> bool:
    """A present receipt supports SATISFIED only if it parses and claims success.

    Passing-looking garbage does not count. Absence is handled before this.
    """
    try:
        text = raw.decode("utf-8")
        doc = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(doc, dict) or not doc:
        return False
    checks = doc.get("checks")
    if isinstance(checks, list) and checks:
        if not all(isinstance(c, dict) and c.get("pass") is True for c in checks):
            return False
        total = doc.get("checks_total")
        if total is not None and int(total) != len(checks):
            return False
        return True
    st = str(doc.get("state") or doc.get("status") or doc.get("verdict") or "").upper()
    if st in {"SUCCESS", "PASS", "SATISFIED", "GO", "DELIVERED"}:
        return True
    return False


def _state_from_receipts(receipts: list[dict], lookup: Lookup) -> tuple[str, str]:
    present = [r for r in receipts if r.get("present") is True]
    if not present:
        return (
            NOT_CHECKED,
            "no supporting receipt on disk; never assumed satisfied",
        )
    supporting = 0
    unparseable = 0
    for r in present:
        hit = lookup(str(r["path"]))
        raw = hit.get("raw") if hit else None
        if not isinstance(raw, (bytes, bytearray)):
            unparseable += 1
            continue
        if receipt_supports(bytes(raw)):
            supporting += 1
        else:
            unparseable += 1
    if supporting == len(present) and supporting > 0:
        return SATISFIED, "every named present receipt parsed and claimed success"
    return (
        FALSE,
        "named receipt present but does not support the condition "
        f"(supporting={supporting} present={len(present)} rejected={unparseable})",
    )


def evaluate_substitute(lookup: Lookup, oq9: dict | None = None) -> dict:
    oq9 = oq9 if oq9 is not None else oq9_substitute()
    receipts = [consult(p, lookup) for p in SUBSTITUTE_RECEIPTS]
    state, reason = _state_from_receipts(receipts, lookup)
    owner_state = str(oq9.get("state") or "").upper()
    approved = owner_state == "ANSWERED" and bool(str(oq9.get("answer") or "").strip())
    return {
        "owner_question_id": "OQ-9",
        "owner_question_state": oq9.get("state"),
        "owner_approved_substitute_recorded": approved,
        "text": str(oq9.get("answer") or ""),
        "detail": str(oq9.get("answer_detail") or ""),
        "receipt_path": oq9.get("receipt_path"),
        "substitute_receipts": receipts,
        "substitute_computed_state": state,
        "reason": reason,
        "does_not_silently_rewrite_as_written": True,
    }


def evaluate_condition(cond: dict, release_mode: str, lookup: Lookup) -> dict:
    receipts = [consult(p, lookup) for p in cond["receipt_paths"]]
    unsat_under = cond.get("unsatisfiable_under")
    if unsat_under and release_mode == unsat_under:
        state = UNSAT
        reason = str(cond.get("unsatisfiable_wording") or "")
    else:
        state, reason = _state_from_receipts(receipts, lookup)
    return {
        "id": cond["id"],
        "spec_anchor": cond["spec_anchor"],
        "wording": cond["wording"],
        "wording_provenance": cond.get("wording_provenance"),
        "computed_state": state,
        "reason": reason,
        "receipts_consulted": receipts,
        "derived_from_named_receipts": True,
        "unsatisfiable_under": unsat_under,
        "release_mode_applied": release_mode,
    }


def promotion_verdict(rows: list[dict], escalations: list[dict]) -> tuple[str, str]:
    esc_by_id = {e["condition_id"]: e for e in escalations}
    blockers = []
    for row in rows:
        st = row["computed_state"]
        if st == SATISFIED:
            continue
        if st == UNSAT:
            esc = esc_by_id.get(row["id"]) or {}
            sub = esc.get("proposed_substitute") or {}
            if sub.get("substitute_computed_state") == SATISFIED and sub.get(
                "owner_approved_substitute_recorded"
            ):
                continue
            blockers.append(row["id"] + ":unsat-without-satisfied-substitute")
            continue
        blockers.append(row["id"] + ":" + st)
    if blockers:
        return "NO-GO", "NOT-CHECKED and FALSE block as hard as unsat; " + "; ".join(
            blockers
        )
    return "GO", "every condition SATISFIED or unsat-with-satisfied-owner-substitute"


def evaluate(
    release_mode: str,
    lookup: Lookup,
    conditions: list[dict] | None = None,
    oq9: dict | None = None,
) -> dict:
    conditions = conditions if conditions is not None else PROMOTION_CONDITIONS
    rows = [evaluate_condition(c, release_mode, lookup) for c in conditions]
    substitute = evaluate_substitute(lookup, oq9)
    escalations = []
    for row, cond in zip(rows, conditions):
        if row["computed_state"] != UNSAT:
            continue
        escalations.append(
            {
                "condition_id": row["id"],
                "classification": "unsatisfiable-condition",
                "exact_wording_that_makes_it_so": str(
                    cond.get("unsatisfiable_wording") or row["reason"]
                ),
                "proposed_substitute": substitute,
                "silently_dropped": False,
            }
        )
    dropped = [
        c["id"]
        for c, row in zip(conditions, rows)
        if c.get("unsatisfiable_under") == release_mode
        and not any(r["id"] == c["id"] for r in rows)
    ]
    if dropped:
        raise RuntimeError(f"unsatisfiable conditions dropped: {dropped}")
    verdict, verdict_reason = promotion_verdict(rows, escalations)
    return {
        "release_mode": release_mode,
        "conditions": rows,
        "escalations": escalations,
        "promotion_verdict": verdict,
        "promotion_verdict_reason": verdict_reason,
        "unsatisfiable_ids": [r["id"] for r in rows if r["computed_state"] == UNSAT],
        "not_checked_ids": [r["id"] for r in rows if r["computed_state"] == NOT_CHECKED],
        "satisfied_ids": [r["id"] for r in rows if r["computed_state"] == SATISFIED],
        "false_ids": [r["id"] for r in rows if r["computed_state"] == FALSE],
        "input_ids": [c["id"] for c in conditions],
        "output_ids": [r["id"] for r in rows],
    }


def map_lookup(files: dict[str, bytes]) -> Lookup:
    def lookup(rel: str) -> dict | None:
        raw = files.get(rel)
        if not raw:
            return None
        return {
            "path": rel,
            "present": True,
            "bytes": len(raw.replace(b"\r\n", b"\n")),
            "sha256": digest_bytes(raw),
            "raw": raw,
        }

    return lookup
