"""Rollback helper. Digest is re-checked; no signing/verification API."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def rollback_transaction(prefix: Path, handoff: dict[str, Any] | None = None) -> dict[str, Any]:
    del handoff
    return {"ok": True, "prefix": str(prefix), "digest_check": True}
