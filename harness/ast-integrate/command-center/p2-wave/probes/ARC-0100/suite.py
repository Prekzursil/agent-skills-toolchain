"""Live unknown-field suite for ARC-0100.

Tests (catalog):
  * Forward-compat: instance + future optional field, validator under the
    declared policy, outcome matches REJECT vs IGNORE.
  * Both-states: flip the policy flag, verdict.accepted flips.
  * Anti-tautology: a clean instance does not flip; a syntax/schema error is
    not counted as unknown-field.
"""
from __future__ import annotations

from typing import Any

import contracts as C
import validator as V


def contracts_from_artifact(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Policy rows live on report.contracts (receipt_core forbids extra top-level keys)."""
    rows = doc.get("contracts")
    if isinstance(rows, list) and rows:
        return [r for r in rows if isinstance(r, dict)]
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    rows = report.get("contracts")
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, dict)]
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    rows = ext.get("contracts")
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, dict)]
    return []


def flip(policy: str) -> str:
    p = policy.upper()
    if p == "REJECT":
        return "IGNORE"
    if p == "IGNORE":
        return "REJECT"
    raise ValueError(policy)


def run_one(uid: str) -> dict[str, Any]:
    schema, source, phase4_path = C.load_schema(uid)
    meta = C.POLICIES[uid]
    policy = meta["policy"]
    golden = C.GOLDEN[uid]
    future = C.with_future_field(golden)

    clean_declared = V.validate(golden, schema, policy)
    clean_flipped = V.validate(golden, schema, flip(policy))
    fut_declared = V.validate(future, schema, policy)
    fut_flipped = V.validate(future, schema, flip(policy))
    syntax = V.validate(["not", "an", "object"], schema, policy)
    missing = V.validate({}, schema, policy)

    want_accept_future = policy == "IGNORE"
    forward_ok = (
        fut_declared.accepted is want_accept_future
        and (
            fut_declared.reason_kind == "ok"
            if want_accept_future
            else fut_declared.reason_kind == "unknown-field"
        )
        and C.FUTURE_FIELD in fut_declared.extras
    )
    both_states_ok = (
        fut_declared.accepted is not fut_flipped.accepted
        and fut_flipped.reason_kind
        in ({"ok"} if policy == "REJECT" else {"unknown-field"})
    )
    clean_stable_ok = (
        clean_declared.accepted is True
        and clean_flipped.accepted is True
        and clean_declared.reason_kind == "ok"
        and not clean_declared.extras
    )
    anti_tautology_ok = (
        syntax.accepted is False
        and syntax.reason_kind == "syntax"
        and missing.accepted is False
        and missing.reason_kind == "schema"
        and not missing.reason.startswith("unknown-field:")
    )
    pair_named = bool(meta.get("producer") and meta.get("consumer") and meta.get("who_moves_first"))
    justified_ok = (meta.get("justification") == "JUSTIFIED") is pair_named

    ok = all(
        [
            forward_ok,
            both_states_ok,
            clean_stable_ok,
            anti_tautology_ok,
            justified_ok,
            pair_named,
        ]
    )
    return {
        "contract_id": uid,
        "policy": policy,
        "flipped_policy": flip(policy),
        "schema_source": source,
        "phase4_path": phase4_path,
        "producer": meta["producer"],
        "consumer": meta["consumer"],
        "who_moves_first": meta["who_moves_first"],
        "justification": meta["justification"],
        "why": meta["why"],
        "consequence_if_reject_wrong": meta["consequence_if_reject_wrong"],
        "consequence_if_ignore_wrong": meta["consequence_if_ignore_wrong"],
        "forward_compat": {
            "ok": forward_ok,
            "want_accept": want_accept_future,
            "declared": fut_declared.as_dict(),
        },
        "both_states": {
            "ok": both_states_ok,
            "declared_accepted": fut_declared.accepted,
            "flipped_accepted": fut_flipped.accepted,
            "flipped": fut_flipped.as_dict(),
        },
        "clean_stable": {
            "ok": clean_stable_ok,
            "declared": clean_declared.as_dict(),
            "flipped": clean_flipped.as_dict(),
        },
        "anti_tautology": {
            "ok": anti_tautology_ok,
            "syntax": syntax.as_dict(),
            "missing_required": missing.as_dict(),
        },
        "pair_named": pair_named,
        "justified_ok": justified_ok,
        "ok": ok,
    }


def live_catalog_arc0083() -> dict[str, Any]:
    """REJECT on a live catalog unit: extras and missing mandated field `target`."""
    schema, source, _ = C.load_schema("ARC-0083")
    unit = C.catalog_unit("ARC-0100") or {}
    v = V.validate(unit, schema, "REJECT")
    extras = V.unknown_keys(unit, schema)
    missing = [
        f
        for f in (schema.get("required") or [])
        if f not in unit
    ]
    return {
        "schema_source": source,
        "sample_id": unit.get("id"),
        "accepted": v.accepted,
        "reason_kind": v.reason_kind,
        "reason": v.reason,
        "unknown_keys": extras,
        "missing_required": missing,
        "notes": (
            "Live WORK-UNIT-CATALOG.json uses question_or_target and "
            "assigned_model_vendor_role; Prompt Two mandated target and assignment. "
            "REJECT surfaces both the unknown keys and the missing mandated fields. "
            "This is evidence for the ARC-0083 policy, not a blocker for ARC-0100."
        ),
    }


def run_all() -> dict[str, Any]:
    rows = [run_one(uid) for uid in C.CONTRACT_IDS]
    return {
        "ok": all(r["ok"] for r in rows),
        "contracts": rows,
        "live_catalog_arc0083": live_catalog_arc0083(),
        "validator_flag": "unknown_field_policy",
        "validator_module": "command-center/p2-wave/probes/ARC-0100/validator.py",
        "future_field": C.FUTURE_FIELD,
    }
