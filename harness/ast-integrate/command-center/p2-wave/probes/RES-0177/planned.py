#!/usr/bin/env python3
"""Map catalog planned builds onto mechanisms already published in plugins."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

# Catalog units that would re-implement a mechanism already shipped by a
# published plugin. Anchored from RES-0177 inputs (11331) plus hook/loop/memory.
ANCHORS = {
    "IMP-0209": {
        "mechanism": "workflow-discovery / ranked existing-candidate search",
        "plugins": ["metaswarm", "superpowers"],
        "why": "workflow-scout searches local/marketplace sources for an incumbent; metaswarm already ships a 9-phase pipeline and superpowers already ships writing-plans / executing-plans skills.",
        "failure_class": "11331 workflow discovery ignores an existing superior workflow and rebuilds it",
    },
    "IMP-0193": {
        "mechanism": "generate-a-workflow-from-a-typed-goal",
        "plugins": ["metaswarm", "superpowers"],
        "why": "generator must REFUSE when scout finds an incumbent (11331). Rebuilding metaswarm/superpowers pipelines as a new Workflow is the named failure.",
        "failure_class": "11331",
    },
    "WFA-0046": {
        "mechanism": "9-phase gated pipeline to IR",
        "plugins": ["metaswarm"],
        "why": "adapter unit exists specifically so the control plane represents metaswarm's pipeline without importing metaswarm as a second runtime.",
        "failure_class": "runtime-import / second-control-plane",
    },
    "ARC-0088": {
        "mechanism": "hook contract (stdin JSON, exit codes, fail-open, Stop/PreToolUse)",
        "plugins": ["hookify", "ralph-loop", "remember", "claude-reflect"],
        "why": "hookify, ralph-loop, remember, and claude-reflect already register Stop/PreToolUse/PostToolUse/SessionStart/UserPromptSubmit hooks. A new hook runtime that ignores those plugins re-implements the same event surface.",
        "failure_class": "second-hook-control-plane",
    },
    "R-A16": {
        "mechanism": "self-improvement keep/revert loop",
        "plugins": ["ralph-loop"],
        "why": "R-A16 is the planned keep-only-measured-wins loop. ralph-loop already implements a Stop-hook while-true iteration with max-iterations and a completion promise.",
        "failure_class": "duplicate-loop-runtime",
    },
    "WFA-0127": {
        "mechanism": "workflow-scout executable spec",
        "plugins": ["metaswarm", "superpowers"],
        "why": "scout over archaeology surface; installed skill/plugin workflows are the first place to look before forging a new one.",
        "failure_class": "11331",
    },
    "WFA-0143": {
        "mechanism": "workflow-scout search/rank/provenance",
        "plugins": ["metaswarm", "superpowers"],
        "why": "same 11331 trap: a scout that does not join the live/plugin inventory will rebuild an incumbent.",
        "failure_class": "11331",
    },
}


def _units() -> list[dict]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return [u for u in (data.get("work_units") or []) if isinstance(u, dict)]
    return []


def planned_reimplementations() -> list[dict]:
    by_id = {u.get("id"): u for u in _units() if u.get("id")}
    rows = []
    for uid, spec in ANCHORS.items():
        unit = by_id.get(uid)
        rows.append(
            {
                "unit_id": uid,
                "present_in_catalog": unit is not None,
                "title": (unit or {}).get("title") or spec["why"][:80],
                "question": (unit or {}).get("question_or_target"),
                "output_path": (unit or {}).get("output_path"),
                "mechanism": spec["mechanism"],
                "overlaps_plugins": spec["plugins"],
                "why": spec["why"],
                "failure_class": spec["failure_class"],
                "reimplements_installed": True,
            }
        )
    return rows
