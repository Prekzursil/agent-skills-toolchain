"""Typed confirmation records. Unsourced CONFIRMED is unrepresentable."""
from __future__ import annotations

import hashlib
from typing import Any


class RecordContractError(ValueError):
    pass


def validate_record(rec: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(rec, dict):
        raise RecordContractError("record must be an object")
    verdict = rec.get("verdict")
    if verdict == "CONFIRMED":
        src = rec.get("source_probe")
        ver = rec.get("verifier_probe")
        if not src or not ver:
            raise RecordContractError("CONFIRMED requires source_probe and verifier_probe")
        if src == ver:
            raise RecordContractError("CONFIRMED must not be a same-probe rerun")
    if verdict in {"CONFIRMED", "REFUTED"} and rec.get("fault_class"):
        raise RecordContractError("claim verdict cannot carry an infra fault_class")
    return rec


def mint_record_id(job_id: str, claim_id: str, kind: str) -> str:
    raw = f"{job_id}|{claim_id}|{kind}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
