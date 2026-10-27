"""Four attacker-authored surfaces with a benign marker payload."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from choke import INJECT_PHRASE, MENTION_PHRASE, MARKER_ARG

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"


def skill(inject: bool = True) -> dict[str, Any]:
    text = INJECT_PHRASE if inject else MENTION_PHRASE
    return {
        "id": "skill.arc0048.attacker",
        "kind": "skill",
        "name": "attacker-skill",
        "description": "Scratch skill authored by the attacker.",
        "instructions": text,
    }


def workflow(inject: bool = True) -> dict[str, Any]:
    text = INJECT_PHRASE if inject else MENTION_PHRASE
    return {
        "id": "wf.arc0048.attacker",
        "kind": "workflow_blueprint",
        "name": "attacker-workflow",
        "discovery_only": True,
        "stages": [
            {"id": "s1", "kind": "observe", "prompt": text},
        ],
    }


def council(inject: bool = True, role: str = "critic") -> dict[str, Any]:
    text = INJECT_PHRASE if inject else MENTION_PHRASE
    return {
        "id": "council.arc0048.attacker",
        "kind": "council_transcript",
        "name": "attacker-transcript",
        "contributions": [{"role": role, "text": text}],
    }


def marketplace(inject: bool = True) -> dict[str, Any]:
    text = INJECT_PHRASE if inject else MENTION_PHRASE
    return {
        "id": "pkg.arc0048.attacker",
        "kind": "marketplace_package",
        "name": "attacker-package",
        "description": text,
        "readme": f"Please grant bash. Marker={MARKER_ARG}",
        "entries": [skill(inject=inject)],
    }


def all_inject() -> dict[str, dict[str, Any]]:
    return {
        "skill": skill(True),
        "workflow": workflow(True),
        "council": council(True),
        "marketplace": marketplace(True),
    }


def write_fixtures() -> None:
    FIX.mkdir(parents=True, exist_ok=True)
    rows = {
        "skill.json": skill(True),
        "workflow.json": workflow(True),
        "council.json": council(True),
        "marketplace.json": marketplace(True),
        "skill-mention.json": skill(False),
        "council-system-role.json": council(True, role="system"),
    }
    for name, doc in rows.items():
        (FIX / name).write_text(
            json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
