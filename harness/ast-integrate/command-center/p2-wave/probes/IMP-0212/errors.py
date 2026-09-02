"""Typed forge failures. A looks-right workflow is never smuggled in these payloads."""
from __future__ import annotations

from typing import Any


class ForgeError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def typed_failure(code: str, message: str, **extra: Any) -> dict[str, Any]:
    """Caller-visible refusal. `workflow` is always None so a broken input cannot leak."""
    payload: dict[str, Any] = {
        "ok": False,
        "status": "TYPED_FAILURE",
        "error_type": "ForgeTypedFailure",
        "error_code": code,
        "message": message,
        "workflow": None,
        "simulation_receipt": None,
    }
    payload.update(extra)
    return payload
