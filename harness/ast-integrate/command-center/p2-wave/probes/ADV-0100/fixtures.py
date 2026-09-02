#!/usr/bin/env python3
"""Council composition fixtures for ADV-0100.

Planted direct self-review, planted transitive lineage, independent-only
clean panel, empty roster, and a detector-control known-present row.
JSON copies live under fixtures/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX_DIR = HERE / "fixtures"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from coi_filter import INDEPENDENT_ID, KNOWN_LINEAGE_AUTHOR, KNOWN_SELF_AUTHOR  # noqa: E402

# Planted ids the instrument must name: KNOWN-SELF-AUTHOR, KNOWN-LINEAGE-AUTHOR, IND-DANA.
CONTROL_ID = "detector-control-known-present"
DIRECT_ID = "planted-direct-self-review"
TRANSITIVE_ID = "planted-transitive-lineage"
CLEAN_ID = "clean-independent-panel"
EMPTY_ID = "empty-roster"
UNDECLARED_ID = "undeclared-direct-coi"

PLANTED_DIRECT_IDS = (CONTROL_ID, DIRECT_ID, UNDECLARED_ID)
PLANTED_TRANSITIVE_IDS = (TRANSITIVE_ID,)
CLEAN_IDS = (CLEAN_ID,)


def _seat(sid: str, *roles: str, **extra: Any) -> dict[str, Any]:
    row = {"id": sid, "roles": list(roles)}
    row.update(extra)
    return row


def _doc(
    fixture_id: str,
    artifact: dict[str, Any],
    roster: list[dict[str, Any]],
    nodes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "fixture_id": fixture_id,
        "artifact": artifact,
        "roster": roster,
        "nodes": nodes or [],
    }


def detector_control_known_present() -> dict[str, Any]:
    """Known-present planted ids the instrument must FIRE on first."""
    return _doc(
        CONTROL_ID,
        {
            "id": "ART-KNOWN-PRESENT",
            "author_id": KNOWN_SELF_AUTHOR,
            "conflicts_declared": [],
        },
        [
            _seat(KNOWN_SELF_AUTHOR, "author", "reviewer", "judge"),
            _seat(INDEPENDENT_ID, "reviewer"),
        ],
    )


def planted_direct() -> dict[str, Any]:
    """Same identity authored the artifact and sits as reviewer/judge."""
    return _doc(
        DIRECT_ID,
        {
            "id": "ART-DIRECT",
            "author_id": KNOWN_SELF_AUTHOR,
            "title": "proposal under review",
        },
        [
            _seat(KNOWN_SELF_AUTHOR, "author", "reviewer"),
            _seat(INDEPENDENT_ID, "reviewer"),
        ],
    )


def undeclared_direct() -> dict[str, Any]:
    """Provenance join must fire even when the declaration field is empty."""
    return _doc(
        UNDECLARED_ID,
        {
            "id": "ART-UNDECLARED",
            "author_id": KNOWN_SELF_AUTHOR,
            "conflicts_declared": [],
            "conflict_declaration": "",
        },
        [
            _seat(
                KNOWN_SELF_AUTHOR,
                "reviewer",
                "judge",
                conflicts=[],
                declared_interest=None,
            ),
            _seat(INDEPENDENT_ID, "reviewer", conflicts=[]),
        ],
    )


def planted_transitive() -> dict[str, Any]:
    """Third party is the immediate author; original writer is in lineage."""
    return _doc(
        TRANSITIVE_ID,
        {
            "id": "ART-COMPOSED",
            "author_id": "CAROL-THIRD",
            "lineage": [
                {
                    "artifact_id": "FRAG-A",
                    "author_id": KNOWN_LINEAGE_AUTHOR,
                    "relation": "incorporated",
                }
            ],
        },
        [
            _seat(KNOWN_LINEAGE_AUTHOR, "reviewer"),
            _seat("CAROL-THIRD", "author", "composer"),
            _seat(INDEPENDENT_ID, "reviewer"),
        ],
        nodes=[
            {
                "id": "ART-COMPOSED",
                "author_id": "CAROL-THIRD",
                "incorporates": ["FRAG-A"],
            },
            {
                "id": "FRAG-A",
                "author_id": KNOWN_LINEAGE_AUTHOR,
                "incorporates": [],
            },
        ],
    )


def clean_independent() -> dict[str, Any]:
    """Author is not a reviewer. Independent panel must stay seated."""
    return _doc(
        CLEAN_ID,
        {
            "id": "ART-CLEAN",
            "author_id": "AUTHOR-OUTSIDE",
        },
        [
            _seat(INDEPENDENT_ID, "reviewer"),
            _seat("BOB-REVIEWER", "reviewer"),
        ],
    )


def empty_roster() -> dict[str, Any]:
    return _doc(
        EMPTY_ID,
        {"id": "ART-EMPTY", "author_id": "anyone"},
        [],
    )


def all_fixtures() -> dict[str, dict[str, Any]]:
    return {
        CONTROL_ID: detector_control_known_present(),
        DIRECT_ID: planted_direct(),
        UNDECLARED_ID: undeclared_direct(),
        TRANSITIVE_ID: planted_transitive(),
        CLEAN_ID: clean_independent(),
        EMPTY_ID: empty_roster(),
    }


def dump_json() -> None:
    FIX_DIR.mkdir(parents=True, exist_ok=True)
    for fid, doc in all_fixtures().items():
        path = FIX_DIR / f"{fid}.json"
        path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
