#!/usr/bin/env python3
"""Freeze ceremony: trigger moment and armed marker.

Trigger is not 'catalog phase number' and not 'first IMP-* row'. The freeze
arms at the instant this ceremony records freeze_armed=true together with the
hash manifest. That write is the start of implementation-wave change control
for schemas and launchers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

TRIGGER_ID = "FIRST-IMPLEMENTATION-WAVE-START"

NOT_THE_TRIGGER = (
    "catalog phase number increment",
    "first IMP-* unit appearing in the catalog",
    "git commit of this tree",
    "presence of the conformance report file alone without the armed marker",
)


def trigger(*, armed_at: str, set_sha256: str) -> dict[str, Any]:
    return {
        "id": TRIGGER_ID,
        "predicate": (
            "The freeze is armed when this ceremony records freeze_armed=true "
            "with the frozen-set hash manifest. That write is the mechanical "
            "start of implementation-wave change control for schemas and launchers."
        ),
        "armed_at": armed_at,
        "armed": True,
        "set_sha256": set_sha256,
        "not_the_trigger": list(NOT_THE_TRIGGER),
        "editable_after": (
            "Everything classify() returns as not-frozen, plus new versioned "
            "migration records that admit a frozen-path change."
        ),
    }


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
