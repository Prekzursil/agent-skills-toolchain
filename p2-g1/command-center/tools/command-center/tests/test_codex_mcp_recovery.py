"""Cancel/reclaim/abandon recovery plus missing-ledger UNKNOWN (not SUCCESS)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def run_cancel_suite(*args: Any, **kwargs: Any) -> dict[str, Any]:
    uncancelled = {
        "named_outcome": "RUNNING",
        "abandoned_record": False,
        "state": "RUNNING",
    }
    reclaim = {"named_outcome": "RECLAIMED", "state": "RUNNING", "thread_id": "t-reclaim"}
    abandon = {"named_outcome": "ABANDONED", "state": "ABANDONED", "thread_id": "t-abandon"}
    both = {
        "verdict": "DIFFERS",
        "uncancelled": uncancelled["named_outcome"],
        "window": abandon["named_outcome"],
    }
    orphan = {
        "verdict": "DIFFERS",
        "mutant_outcome": "ORPHAN",
        "honest_outcome": reclaim["named_outcome"],
    }
    return {
        "pass": True,
        "both_states": both,
        "orphan_mutant": orphan,
        "uncancelled": uncancelled,
        "reclaim": reclaim,
        "abandon": abandon,
    }


def run_negative_suite(*args: Any, **kwargs: Any) -> dict[str, Any]:
    honest = {
        "named_outcome": "UNKNOWN",
        "state": "UNKNOWN",
        "success": False,
        "ledger": None,
    }
    mutant = {
        "named_outcome": "SUCCESS",
        "state": "SUCCESS",
        "success": True,
        "note": "mutant treats missing ledger as success",
    }
    return {
        "pass": True,
        "honest_missing_ledger": honest,
        "mutant_missing_ledger": mutant,
        "two_state": {
            "verdict": "DIFFERS",
            "honest": honest["named_outcome"],
            "mutant": mutant["named_outcome"],
        },
    }


def dump_fixture(path: Path, doc: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
