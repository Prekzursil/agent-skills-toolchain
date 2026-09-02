"""Catalog-specified A7 security-first controls, instantiated as an executable model.

phase3/A7/DESIGN.json (ARC-0045) is absent on this worktree. This module is
NOT that dossier and does not claim SUCCESS:ARC-0045. It instantiates the
controls named in the ARC-0045/ARC-0051 catalog questions so the blocking
case can be executed and cited at file:line. That is substrate for the
refutation, not an architecture-tournament rebuild.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE = HERE / "fixtures" / "a7-proposed-design.json"
DOSSIER = REPO / "command-center" / "phase3" / "A7" / "GATE-MODEL.json"

# Distinctive one-line values so anchors resolve with exactly one hit.
MODEL: dict[str, Any] = {
    "architecture_class": "security-first",
    "architecture_id": "A7",
    "artifact_signing": {
        "applies_to_estate_local_receipts": True,
        "id": "CTL-A7-SIGN-EVERY-ARTIFACT",
        "required_before_write": True,
        "rule": "signing of estate-local receipts is required before Write",
    },
    "blocking_control_id": "CTL-A7-PER-CALL-WRITE-APPROVAL",
    "blocking_write_rule": (
        "Write of an estate-local receipt is DENY unless owner_approval is "
        "already attached, even for an owner-session agent on this worktree."
    ),
    "choke_point": {
        "approval_mode": "interactive-per-call",
        "evaluates_every_capability_invocation": True,
        "id": "a7.single-permission-choke",
        "require_owner_approval_for": ["Bash", "Write", "Edit", "Read", "Grep"],
        "security_first_sets_estate_local_owner_session_exempt": False,
    },
    "injection_boundary": {
        "forbidden_substrings": ["secret", "API key", "credential"],
        "id": "CTL-A7-PAYLOAD-TEXT-MATCH",
        "match_use_versus_mention": False,
        "mode": "payload-text-match",
        "rule": "A guard matching payload TEXT instead of the tool VERB",
        "surfaces": ["workflow", "council", "skill", "catalog-document"],
    },
    "not_success_arc_0045": True,
    "organizing_principle": (
        "security-first: gate density is the organizer; every capability "
        "invocation crosses a single permission choke point."
    ),
    "source": (
        "Instantiated from command-center/WORK-UNIT-CATALOG.json ARC-0045 "
        "and ARC-0051 questions because phase3/A7/DESIGN.json is absent. "
        "Not SUCCESS:ARC-0045. Not an ADV dossier rebuild."
    ),
    "structural_fingerprint": (
        "CTL-A7-PER-CALL-WRITE-APPROVAL/estate-local-G1-receipt/ARC-0051"
    ),
    "surviving_minimum_set": {
        "dropped_because_permission_theater": [
            "interactive-per-call owner_approval on estate-local owner sessions",
            "signing of estate-local receipts",
            "payload-text-match injection guards on trusted catalog/docs",
        ],
        "keep": [
            {
                "id": "CTL-P0-UNSIGNED-PLUGIN-FAIL-CLOSED",
                "non_negotiable": True,
                "rule": "Unsigned plugin install remains fail-closed in the surviving minimum set",
            },
            {
                "id": "CTL-P0-CANARY-SECRET-BUNDLE-SCAN",
                "non_negotiable": True,
                "rule": "Planted canary secret in an artifact bundle MUST be caught; mention of the word secret in a catalog document must not.",
            },
            {
                "id": "CTL-P0-UNTRUSTED-SURFACE-INJECTION-ISOLATION",
                "non_negotiable": True,
                "rule": "Untrusted workflow/council/skill USE is isolated by discourse ROLE, never by payload TEXT substring.",
            },
        ],
        "organizing_principle": (
            "Security is a constraint on untrusted surfaces, not the organizer "
            "of estate-local owner work."
        ),
        "surviving_set_drops_per_call_approval_for_estate_local_owner_sessions": True,
    },
    "unit_id": "ARC-0051",
}


def write_model() -> dict[str, Path]:
    text = json.dumps(MODEL, indent=2, sort_keys=True) + "\n"
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    DOSSIER.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(text, encoding="utf-8")
    DOSSIER.write_text(text, encoding="utf-8")
    return {"fixture": FIXTURE, "dossier": DOSSIER}


def load_model() -> dict[str, Any]:
    if not FIXTURE.is_file():
        write_model()
    return json.loads(FIXTURE.read_text(encoding="utf-8"))
