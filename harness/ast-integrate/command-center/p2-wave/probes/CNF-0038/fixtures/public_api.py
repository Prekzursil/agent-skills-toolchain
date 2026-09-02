"""Public API surface for CNF-0038 blind test synthesis.

Implementations live only in isolated pre-fix / post-fix snapshots.
This module is the surface a synthesizer may read: names, signatures, docs.
"""

from __future__ import annotations

__all__ = ["validate_receipt"]


def validate_receipt(receipt: dict) -> dict:
    """Validate a confirmation receipt.

    Parameters
    ----------
    receipt:
        Mapping that may include verdict, source_probe, verifier_probe.

    Returns
    -------
    dict
        {"ok": bool, "reason": str}. Documented reason tokens include
        empty-source-probe, same-probe-rerun, independent-probes.
    """
    raise NotImplementedError("surface-only; run against a commit snapshot")
