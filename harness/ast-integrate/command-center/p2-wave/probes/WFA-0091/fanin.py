#!/usr/bin/env python3
"""Schema-typed fan-in barrier — WFA-0091 repair.

Repaired barrier (the delivery):
  * existence-check every contracted output path BEFORE any returned digest
    is read (a digest is a claim; a file on disk is the receipt)
  * schema-validate each returned payload and the on-disk JSON
  * tolerate nulls: report them as missing units; do not collapse the barrier
  * record waited_for vs not_received vs missing_null vs rejected vs accepted

Naive barrier (pre-fix both-states control):
  * filter(Boolean) drops nulls with no ledger line
  * a well-formed digest is accepted even when the file is absent
  * schema-invalid payloads are accepted
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import jsonschema

SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")

RESULT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["unit_id", "status", "artifact_kind"],
    "properties": {
        "unit_id": {"type": "string", "minLength": 1},
        "status": {"type": "string", "enum": ["SUCCESS", "FAILED"]},
        "artifact_kind": {"type": "string", "minLength": 1},
    },
}


def lf_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def schema_errors(instance: Any, schema: dict[str, Any] | None = None) -> list[str]:
    schema = schema if schema is not None else RESULT_SCHEMA
    validator = jsonschema.Draft7Validator(schema)
    out: list[str] = []
    for err in validator.iter_errors(instance):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def existence_check(path: Path, events: list[dict[str, Any]], unit_id: str) -> bool:
    """Receipt probe. Must run before read_claimed_digest in repaired mode."""
    present = path.is_file()
    events.append(
        {
            "op": "exists",
            "unit_id": unit_id,
            "path": str(path).replace("\\", "/"),
            "present": present,
        }
    )
    return present


def read_claimed_digest(
    inbound_row: dict[str, Any] | None,
    events: list[dict[str, Any]],
    unit_id: str,
) -> str | None:
    """Parse the returned digest claim. Repaired mode must not call this
    until existence_check has run for every contracted path."""
    claimed = None
    if isinstance(inbound_row, dict):
        raw = inbound_row.get("digest")
        if isinstance(raw, str):
            claimed = raw.strip().lower()
    events.append(
        {
            "op": "read_digest",
            "unit_id": unit_id,
            "digest": claimed,
            "well_formed": bool(claimed and SHA256_RE.match(claimed)),
        }
    )
    return claimed


def _empty_report(mode: str, contracts: list[dict[str, Any]]) -> dict[str, Any]:
    waited = [c["unit_id"] for c in contracts]
    return {
        "mode": mode,
        "completed": True,
        "waited_for": waited,
        "not_received": [],
        "missing_null": [],
        "accepted": [],
        "rejected": [],
        "silently_dropped_nulls": [],
        "silently_accepted_invalid": [],
        "silently_accepted_missing_file": [],
        "events": [],
    }


def repaired_fan_in(
    contracts: list[dict[str, Any]],
    inbound: dict[str, Any],
    workspace: Path,
) -> dict[str, Any]:
    """Null-tolerant, schema-typed fan-in with receipt-before-digest."""
    events: list[dict[str, Any]] = []
    report = _empty_report("repaired", contracts)
    report["events"] = events

    # Phase 1 — receipt: every contracted path, before any digest parse.
    present: dict[str, bool] = {}
    for contract in contracts:
        uid = contract["unit_id"]
        rel = str(contract["output_path"]).replace("\\", "/")
        present[uid] = existence_check(workspace / rel, events, uid)

    # Phase 2 — only now inspect inbound payloads / claimed digests.
    for contract in contracts:
        uid = contract["unit_id"]
        schema = contract.get("schema") or RESULT_SCHEMA
        if uid not in inbound:
            report["not_received"].append(uid)
            continue
        row = inbound[uid]
        if row is None:
            report["missing_null"].append(uid)
            continue
        if not present[uid]:
            # Planted digest-for-a-missing-file: do not parse the claim.
            report["rejected"].append(
                {
                    "unit_id": uid,
                    "reason": "no-receipt",
                    "digest_parsed": False,
                }
            )
            continue

        claimed = read_claimed_digest(row if isinstance(row, dict) else None, events, uid)
        rel = str(contract["output_path"]).replace("\\", "/")
        path = workspace / rel
        actual = lf_sha256(path)
        payload = row.get("payload") if isinstance(row, dict) else None

        file_obj: Any
        try:
            file_obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            report["rejected"].append(
                {
                    "unit_id": uid,
                    "reason": f"unparseable-file:{type(exc).__name__}",
                    "digest_parsed": True,
                }
            )
            continue

        payload_errs = schema_errors(payload, schema)
        file_errs = schema_errors(file_obj, schema)
        if payload_errs or file_errs:
            report["rejected"].append(
                {
                    "unit_id": uid,
                    "reason": "schema-invalid",
                    "payload_errors": payload_errs[:8],
                    "file_errors": file_errs[:8],
                    "digest_parsed": True,
                }
            )
            continue
        if not claimed or not SHA256_RE.match(claimed):
            report["rejected"].append(
                {
                    "unit_id": uid,
                    "reason": "digest-missing-or-malformed",
                    "digest_parsed": True,
                }
            )
            continue
        if claimed != actual:
            report["rejected"].append(
                {
                    "unit_id": uid,
                    "reason": "digest-mismatch",
                    "claimed": claimed,
                    "actual": actual,
                    "digest_parsed": True,
                }
            )
            continue
        report["accepted"].append(
            {
                "unit_id": uid,
                "reason": "receipt-and-schema-ok",
                "digest": actual,
            }
        )

    return report


def naive_fan_in(
    contracts: list[dict[str, Any]],
    inbound: dict[str, Any],
    workspace: Path,
) -> dict[str, Any]:
    """Pre-fix control: filter(Boolean) + digest-as-receipt + no schema."""
    events: list[dict[str, Any]] = []
    report = _empty_report("naive", contracts)
    report["events"] = events

    # Digest-first (the measured failure): parse claims before any Test-Path.
    aligned: list[tuple[str, Any]] = []
    for contract in contracts:
        uid = contract["unit_id"]
        aligned.append((uid, inbound.get(uid, None)))

    kept: list[tuple[str, Any]] = []
    for uid, row in aligned:
        if not row:
            report["silently_dropped_nulls"].append(uid)
            continue
        kept.append((uid, row))

    for uid, row in kept:
        claimed = read_claimed_digest(row if isinstance(row, dict) else None, events, uid)
        payload = row.get("payload") if isinstance(row, dict) else None
        rel = next(c["output_path"] for c in contracts if c["unit_id"] == uid)
        path = workspace / str(rel).replace("\\", "/")
        file_present = path.is_file()
        events.append(
            {
                "op": "exists_after_digest",
                "unit_id": uid,
                "present": file_present,
            }
        )
        schema = next((c.get("schema") or RESULT_SCHEMA) for c in contracts if c["unit_id"] == uid)
        invalid = bool(schema_errors(payload, schema))
        if claimed and SHA256_RE.match(claimed) and not file_present:
            report["silently_accepted_missing_file"].append(uid)
            report["accepted"].append(
                {
                    "unit_id": uid,
                    "reason": "naive-digest-without-file",
                    "digest": claimed,
                }
            )
            continue
        if invalid:
            report["silently_accepted_invalid"].append(uid)
            report["accepted"].append(
                {
                    "unit_id": uid,
                    "reason": "naive-schema-invalid-accepted",
                    "digest": claimed,
                }
            )
            continue
        report["accepted"].append(
            {
                "unit_id": uid,
                "reason": "naive-accepted",
                "digest": claimed,
            }
        )

    return report


def summarize(report: dict[str, Any]) -> dict[str, Any]:
    rejected_reasons = [r.get("reason") for r in report.get("rejected") or []]
    accepted_ids = [a.get("unit_id") for a in report.get("accepted") or []]
    return {
        "mode": report.get("mode"),
        "completed": report.get("completed"),
        "waited_for": list(report.get("waited_for") or []),
        "not_received": list(report.get("not_received") or []),
        "missing_null": list(report.get("missing_null") or []),
        "accepted_ids": accepted_ids,
        "rejected_reasons": rejected_reasons,
        "rejected_ids": [r.get("unit_id") for r in report.get("rejected") or []],
        "silently_dropped_nulls": list(report.get("silently_dropped_nulls") or []),
        "silently_accepted_invalid": list(report.get("silently_accepted_invalid") or []),
        "silently_accepted_missing_file": list(
            report.get("silently_accepted_missing_file") or []
        ),
        "exists_event_count": sum(1 for e in report.get("events") or [] if e.get("op") == "exists"),
        "read_digest_event_count": sum(
            1 for e in report.get("events") or [] if e.get("op") == "read_digest"
        ),
    }
