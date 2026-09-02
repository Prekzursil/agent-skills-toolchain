#!/usr/bin/env python3
"""Downstream fusion precondition checker driven only through the query interface.

This consumer must not open registry.json / compat.json itself. Probe 2 compares
its fusible-pair set to the independent file-walk in expected.py.
"""

from __future__ import annotations

from typing import Any

import query as Q


def fusible_pair_set(interface: Q.RegistryQueryInterface) -> set[str]:
    result = interface.query("fusibility", "fusible")
    return set(Q.require_ids(result))


def incompatible_pair_set(interface: Q.RegistryQueryInterface) -> set[str]:
    result = interface.query("fusibility", "incompatible")
    return set(Q.require_ids(result))


def partners_of(interface: Q.RegistryQueryInterface, blueprint_id: str) -> set[str]:
    result = interface.query("fusibility", blueprint_id)
    return set(Q.require_ids(result))


def precondition_report(interface: Q.RegistryQueryInterface) -> dict[str, Any]:
    fusible = sorted(fusible_pair_set(interface))
    incompatible = sorted(incompatible_pair_set(interface))
    return {
        "consumer": "fusion-precondition-checker",
        "driven_through": "RegistryQueryInterface.query",
        "interface_version": Q.INTERFACE_VERSION,
        "artifact_version": interface.artifact_version,
        "fusible_pairs": fusible,
        "incompatible_pairs": incompatible,
        "fusible_count": len(fusible),
        "incompatible_count": len(incompatible),
        "naive_compat_count": len(fusible) + len(incompatible),
        "conflict_subtraction_visible": len(incompatible) > 0
        and len(fusible) < (len(fusible) + len(incompatible)),
    }
