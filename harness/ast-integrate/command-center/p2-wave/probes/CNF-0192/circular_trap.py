"""Negative control: a circular verifier that trusts the manifest's own claims.

This is NOT the gate. Probe 1 uses it to prove that citing the manifest as
evidence of itself would stay green after a deletion. gate.py must not import
this module.
"""
from __future__ import annotations

import json
from pathlib import Path


def trust_manifest_claims(manifest_path: Path) -> bool:
    """Return True iff every row's claimed_present field is true (no disk I/O)."""
    doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = doc.get("artifacts") or []
    if not rows:
        return False
    return all(bool(item.get("claimed_present", True)) for item in rows)
