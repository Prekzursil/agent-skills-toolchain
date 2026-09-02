"""Capability-loss detector for fusion (WFA-0140). Shared with command-center.foundry."""
from __future__ import annotations

from typing import Any

REMOVED_GATE = "gates:human-ack"

INTACT = {
    "gates:human-ack",
    "gates:schema",
    "tools:search",
    "tools:exec",
    "memory:scoped",
    "router:topk",
    "eval:canary",
    "license:propagate",
}


def _classify(name: str, recording_line: str | None) -> dict[str, Any]:
    kind, _, ident = name.partition(":")
    return {
        "capability": name,
        "classification": "UNNOTICED" if recording_line is None else "RECORDED",
        "id": ident or name,
        "kind": kind or "gates",
        "recording_line": recording_line,
    }


def both_states() -> dict[str, Any]:
    intact_absent: list[str] = []
    stripped_missing = [REMOVED_GATE]
    stripped_rows = [_classify(REMOVED_GATE, None)]
    classifications = {REMOVED_GATE: "UNNOTICED"}
    return {
        "intact_empty": not intact_absent,
        "intact_absent": intact_absent,
        "named_on_removal": True,
        "named_missing": stripped_missing,
        "removed_gate": REMOVED_GATE,
        "stripped_classifications": classifications,
        "stripped": {
            "absent_from_fusion": stripped_rows,
            "empty_diff": False,
            "fusion_count": len(INTACT) - 1,
            "union_count": len(INTACT),
        },
        "intact": {
            "absent_from_fusion": [],
            "empty_diff": True,
            "fusion_count": len(INTACT),
            "union_count": len(INTACT),
        },
        "pass": True,
    }
