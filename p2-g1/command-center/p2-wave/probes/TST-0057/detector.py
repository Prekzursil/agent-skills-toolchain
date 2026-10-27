#!/usr/bin/env python3
"""TST-0057 detector: NFC/NFD collision groups over an id population.

In-memory planted NFD pair, not a filesystem fixture: the detector must
recover the plant and refuse to certify a zero-collision census that lacks
it. Canonical form is NFC (tools/command-center/id_normalize.py).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
from id_normalize import byte_key, canonical_id, collision_groups  # noqa: E402

NFC_ID = "PLANT-Å-0057"          # PLANT-Å-0057 (U+00C5)
NFD_ID = "PLANT-Å-0057"         # PLANT-A + combining ring (U+030A)


def detect(ids: list[str]) -> dict[str, Any]:
    groups = collision_groups(ids)
    return {
        "group_count": len(groups),
        "groups": groups,
        "planted_hit": any(
            NFC_ID in (g.get("forms") or []) and NFD_ID in (g.get("forms") or [])
            for g in groups
        ),
    }


def detect_planted(extra_ascii_ids: list[str] | None = None) -> dict[str, Any]:
    """ASCII population plus the planted pair; the plant MUST be recovered."""
    ids = list(extra_ascii_ids or []) + [NFC_ID, NFD_ID]
    return detect(ids)
