#!/usr/bin/env python3
"""Both-states checker for the RES-0001 schema family."""
from __future__ import annotations

import copy
from typing import Any

import consumers as C
import fixtures as F
import schema_lib as S

DELETED_NO_CONSUMER = ("narrative", "author", "tags")


def _strip_source_lineage(claim: dict[str, Any]) -> dict[str, Any]:
    mutant = copy.deepcopy(claim)
    mutant.pop("source_lineage", None)
    return mutant


def field_necessity(green: dict[str, Any], peers: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    all_red = True
    for field in S.REQUIRED_FIELDS:
        mutant = copy.deepcopy(green)
        if field not in mutant:
            rows.append({"field": field, "error": "already-absent", "consumer_red": False})
            all_red = False
            continue
        del mutant[field]
        report = C.run_all(mutant, peers)
        red_names = [
            name
            for name in ("phase1_dedup", "phase4_contract", "phase12_refutation")
            if not report[name]["ok"]
        ]
        consumer_red = len(red_names) >= 1
        if not consumer_red:
            all_red = False
        schema_ok, schema_errs = S.validate_claim(mutant)
        rows.append(
            {
                "field": field,
                "named_consumers": C.FIELD_CONSUMERS[field],
                "consumer_red": consumer_red,
                "consumers_that_went_red": red_names,
                "schema_rejected": not schema_ok,
                "schema_errors_head": schema_errs[:3],
            }
        )
    return {"ok": all_red and len(rows) == len(S.REQUIRED_FIELDS), "rows": rows}


def unused_field_deletion(green: dict[str, Any]) -> dict[str, Any]:
    """Fields nobody consumes are not in the schema. additionalProperties: false."""
    baseline = C.run_all(green)
    rows = []
    for name in DELETED_NO_CONSUMER:
        extra = copy.deepcopy(green)
        extra[name] = "not-a-consumer-input"
        schema_ok, errs = S.validate_claim(extra)
        still_ok = C.run_all(green)["ok"]
        rows.append(
            {
                "field": name,
                "consumer_needs_it": False,
                "schema_rejects_when_present": not schema_ok,
                "consumers_ok_when_absent": still_ok,
                "schema_errors_head": errs[:2],
            }
        )
    return {
        "ok": baseline["ok"] and all(r["schema_rejects_when_present"] and r["consumers_ok_when_absent"] for r in rows),
        "deleted_fields": list(DELETED_NO_CONSUMER),
        "rows": rows,
    }


def roundtrip_ten(claims: list[dict[str, Any]]) -> dict[str, Any]:
    validator = S.claim_validator()
    rows = []
    ok = True
    if len(claims) != 10:
        return {"ok": False, "error": f"want 10 claims, got {len(claims)}"}
    for claim in claims:
        v_ok, v_err = S.validate_claim(claim, validator)
        rt_ok, first, second = S.roundtrip_bytes(claim)
        if not v_ok or not rt_ok:
            ok = False
        rows.append(
            {
                "claim_id": claim.get("claim_id"),
                "schema_ok": v_ok,
                "schema_errors": v_err[:4],
                "byte_stable": rt_ok,
                "canonical_bytes": len(first.encode("utf-8")),
                "mismatch": None if rt_ok else {"first_len": len(first), "second_len": len(second)},
            }
        )
    return {"ok": ok, "n": len(claims), "rows": rows}


def both_states(green: dict[str, Any]) -> dict[str, Any]:
    """Known-good stays green. source_lineage-stripped copy is RED (FAIL, not warn)."""
    good_schema, good_err = S.validate_claim(green)
    good_cons = C.run_all(green)
    bad = _strip_source_lineage(green)
    bad_schema, bad_err = S.validate_claim(bad)
    bad_cons = C.run_all(bad)
    silent_both = good_schema and bad_schema
    warn_only = (not bad_schema) is False and any("warn" in e.lower() for e in bad_err)
    return {
        "ok": good_schema and good_cons["ok"] and (not bad_schema) and (not bad_cons["ok"]) and not silent_both,
        "known_good": {
            "schema_ok": good_schema,
            "consumers_ok": good_cons["ok"],
            "schema_errors": good_err,
            "consumers": good_cons,
        },
        "source_lineage_stripped": {
            "schema_ok": bad_schema,
            "consumers_ok": bad_cons["ok"],
            "schema_errors": bad_err[:6],
            "consumers": bad_cons,
            "failed_not_warned": (not bad_schema) and not warn_only,
        },
        "silent_in_both_states": silent_both,
    }


def run_report() -> dict[str, Any]:
    missing = S.missing_schema_files()
    pack = F.materialize()
    claims = pack["claims"]
    green = pack["green"]
    peers = [c for c in claims if c["claim_id"] != green["claim_id"]]
    rt = roundtrip_ten(claims)
    necessity = field_necessity(green, peers)
    unused = unused_field_deletion(green)
    states = both_states(green)
    eight = len(missing) == 0 and len(S.SCHEMA_FILES) == 8
    ok = eight and rt["ok"] and necessity["ok"] and unused["ok"] and states["ok"]
    return {
        "ok": ok,
        "schema_files_present": eight,
        "schema_files": [p.as_posix() for p in S.schema_paths()],
        "missing_schema_files": missing,
        "roundtrip": rt,
        "field_necessity": necessity,
        "unused_field_deletion": unused,
        "both_states": states,
        "green_claim_id": green["claim_id"],
        "claim_ids": [c["claim_id"] for c in claims],
        "eco_absent": pack["eco_absent"],
        "pack": pack,
    }
