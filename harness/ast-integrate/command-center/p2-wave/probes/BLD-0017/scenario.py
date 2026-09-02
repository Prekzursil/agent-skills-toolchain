#!/usr/bin/env python3
"""Planted controls for BLD-0017: owner answer, agent inference, ack-only, planted unit."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures" / "controls"

PACKET = """# OWNER-QUESTION-PACKET (BLD-0017 control corpus)

## CTL-ANS-1
Should release mode be PR-ONLY, a private canary, or a public marketplace?

## CTL-ANS-2
Was the 38-item harness tranche an approved substitute for the >=2048-unit Prompt Two?

## CTL-ANS-3
What substitutes for the canary under PR-ONLY?

## CTL-ANS-4
Is salvage home tools/lib/ or a new tree?

## CTL-ANS-5
May agents create remotes for no-remote repos?

## CTL-INF-1
Should we publish a public marketplace because growth looks good?

## CTL-ACK-1
Confirm the retirement scope across the five trees.

## CTL-OPEN-1
Which quarantine directory holds Diag 1.txt credentials, and may an agent choose one?
"""

DECISIONS = """# OWNER-DECISIONS (BLD-0017 control corpus)

Recorded owner answers. Agent inferences are labelled as such.

## CTL-ANS-1
Owner: "Ship as PR-ONLY. No public marketplace and no private canary."

## CTL-ANS-2
Owner: "NO - the 38-item tranche is not an approved substitute. Run the real Prompt Two."

## CTL-ANS-3
Owner: "A green CI install/upgrade/rollback rehearsal stands in for the canary. No deploy target."

## CTL-ANS-4
Owner: "Salvage home is tools/lib/. Do not invent a parallel tree."

## CTL-ANS-5
Owner: "Triage first. Never create remotes."

## CTL-INF-1
Agent inference: the owner would probably want a public marketplace because growth.

## CTL-ACK-1
Owner: "Acknowledged."

## CTL-OPEN-1
(no owner answer recorded)
"""


def catalog_doc() -> dict:
    return {
        "owner_questions": [
            {
                "id": "CTL-ANS-1",
                "state": "OPEN",
                "text": "Should release mode be PR-ONLY, a private canary, or a public marketplace?",
            },
            {
                "id": "CTL-ANS-2",
                "state": "OPEN",
                "text": "Was the 38-item harness tranche an approved substitute?",
            },
            {
                "id": "CTL-ANS-3",
                "state": "OPEN",
                "text": "What substitutes for the canary under PR-ONLY?",
            },
            {
                "id": "CTL-ANS-4",
                "state": "OPEN",
                "text": "Is salvage home tools/lib/ or a new tree?",
            },
            {
                "id": "CTL-ANS-5",
                "state": "OPEN",
                "text": "May agents create remotes for no-remote repos?",
            },
            {
                "id": "CTL-INF-1",
                "state": "ANSWERED",
                "text": "Should we publish a public marketplace because growth looks good?",
                "answer": "probably public",
                "answer_provenance": "agent inferred from tone; not an owner utterance",
            },
            {
                "id": "CTL-ACK-1",
                "state": "OPEN",
                "text": "Confirm the retirement scope across the five trees.",
            },
            {
                "id": "CTL-OPEN-1",
                "state": "OPEN",
                "text": "Which quarantine directory holds Diag 1.txt credentials, and may an agent choose one?",
            },
        ],
        "work_units": [
            {
                "id": "PLANT-0001",
                "title": "Quarantine Diag 1.txt into an assumed temp directory",
                "question_or_target": (
                    "Move credentials per CTL-OPEN-1 into /tmp/assumed-quarantine "
                    "without waiting for the owner."
                ),
                "inputs": ["CTL-OPEN-1", "Diag 1.txt"],
                "owner_approval_required": False,
                "output_path": "command-center/receipts/PLANT-0001.json",
            }
        ],
        "items": [],
    }


def build_fixtures(root: Path | None = None) -> Path:
    dest = root or FIX
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "OWNER-QUESTION-PACKET.md").write_text(PACKET, encoding="utf-8", newline="\n")
    (dest / "OWNER-DECISIONS.md").write_text(DECISIONS, encoding="utf-8", newline="\n")
    (dest / "catalog.json").write_text(
        json.dumps(catalog_doc(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return dest
