"""Install-time signature gate. Fail-closed."""
from __future__ import annotations

from typing import Any, Mapping

from marketplace.signature import VALID, verify_signature

GATE_SIGNATURE = "GATE_SIGNATURE"
GATE_COMPATIBILITY = "GATE_COMPATIBILITY"
GATE_LOCKFILE_DIGEST = "GATE_LOCKFILE_DIGEST"
GATE_REVOCATION = "GATE_REVOCATION"
VERIFY_ORDER = ("signature", "revocation", "compatibility", "lockfile")


class GateFailure(Exception):
    def __init__(self, message: str, gate: str = GATE_SIGNATURE) -> None:
        super().__init__(message)
        self.gate = gate


def check_signature(digest: str, record: Mapping[str, Any] | None, store: Mapping[str, str]) -> str:
    result = verify_signature(digest, record, store)
    if result.status != VALID:
        raise GateFailure(result.reason or result.status, gate=GATE_SIGNATURE)
    if not result.key_id:
        raise GateFailure("valid without key id", gate=GATE_SIGNATURE)
    return result.key_id
