#!/usr/bin/env python3
"""IMP-0369 fixture index: six capabilities, one ALWAYS-ON, five LAZY.

Bodies carry unique markers so a probe can prove a body was or was not
injected by searching the payload, independent of the load-trace list.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
INDEX_PATH = HERE / "fixtures" / "capability-index.json"
LAZY_PY = REPO / "tools" / "router" / "lazy.py"
RECEIPT = REPO / "command-center" / "receipts" / "IMP-0369.json"

ALWAYS_ON_ID = "skill.gamma"
SELECT_ID = "skill.alpha"
IDS = (
    "skill.alpha",
    "skill.beta",
    "skill.gamma",
    "skill.delta",
    "workflow.epsilon",
    "hook.zeta",
)
SUMMARIES = {
    "skill.alpha": "Index card for JSON-schema lint. Body is not this card.",
    "skill.beta": "Index card for git worktree isolate. Body is not this card.",
    "skill.gamma": "Index card for secret-scrub telemetry. ALWAYS-ON at turn zero.",
    "skill.delta": "Index card for markdown frontmatter parse. Body is not this card.",
    "workflow.epsilon": "Index card for docker sandbox exec. Body is not this card.",
    "hook.zeta": "Index card for receipt-schema validate. Body is not this card.",
}


def unique_marker(cid: str) -> str:
    return f"UNIQUE/{cid}/END"


def body_for(cid: str, n: int = 120) -> str:
    slug = cid.replace(".", "-")
    words = [f"{slug}-tok-{i:03d}" for i in range(n)]
    return (
        f"Full body for {cid}. This paragraph must not appear in a lazy "
        f"turn-zero payload unless the record is ALWAYS-ON or has been selected.\n"
        + " ".join(words)
        + f"\n{unique_marker(cid)}"
    )


def capabilities() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cid in IDS:
        rows.append(
            {
                "capability_id": cid,
                "summary": SUMMARIES[cid],
                "description": SUMMARIES[cid],
                "load_mode": "ALWAYS-ON" if cid == ALWAYS_ON_ID else "LAZY",
                "body": body_for(cid),
                "kind": cid.split(".", 1)[0],
            }
        )
    return rows


def index_document() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "unit_id": "IMP-0369",
        "source": (
            "labelled fixture for IMP-0369; IMP-0385 live six-root index "
            "and IMP-0392 budgeter are absent on this worktree"
        ),
        "capabilities": capabilities(),
    }


def write_index() -> Path:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(
        json.dumps(index_document(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return INDEX_PATH
