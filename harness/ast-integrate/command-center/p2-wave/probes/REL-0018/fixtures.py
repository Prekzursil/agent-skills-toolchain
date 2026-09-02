"""Synthetic trees for REL-0018 mutation controls."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from conditions import CONDITIONS, EVIDENCE_SCHEMA, PACKET_SCHEMA, REL0003


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def evidence_doc(condition_id: int, verdict: str = "TRUE") -> dict[str, Any]:
    return {
        "schema": EVIDENCE_SCHEMA,
        "condition_id": condition_id,
        "verdict": verdict,
        "anchor": f"fixtures/synthetic:SC-{condition_id:02d}",
        "probe": "synthetic-known-good",
    }


def passing_wrong_schema(condition_id: int) -> dict[str, Any]:
    """Looks like a pass; missing the required schema id and condition_id type."""
    return {
        "ok": True,
        "pass": True,
        "verdict": "TRUE",
        "status": "PASS",
        "condition": condition_id,
        "evidence": "passing-looking but wrong schema",
    }


def rel0003_packet(receipts: list[str] | None = None, recorded: bool = True) -> dict:
    ruling: dict[str, Any] = {
        "recorded": recorded,
        "condition_13_equivalent": (
            "merged PR plus clean-profile install, upgrade and rollback rehearsal"
        ),
    }
    if receipts is not None:
        ruling["evidence_receipts"] = receipts
    return {
        "unit_id": "REL-0003",
        "schema": PACKET_SCHEMA,
        "question": (
            "Under binding PR-ONLY, what must succeed in place of stop "
            "condition 13 'release/canary succeeds'?"
        ),
        "recommendation": (
            "Redefine 13 as a merged PR plus a clean-profile install, upgrade "
            "and rollback rehearsal evidenced by REL-0004, REL-0005 and REL-0006."
        ),
        "default_if_unanswered": (
            "Leave condition 13 NOT-CHECKED until a ruling is recorded; "
            "do not mark N/A as a silent pass."
        ),
        "ruling": ruling,
    }


def named_receipt(unit_id: str) -> dict:
    return {
        "unit_id": unit_id,
        "state": "SUCCESS",
        "sentinel": f"SUCCESS:{unit_id}",
    }


def write_green_tree(root: Path) -> None:
    """All 21 TRUE: standard evidence plus REL-0003 ruling with named receipts."""
    named = [
        "command-center/receipts/REL-0004.json",
        "command-center/receipts/REL-0005.json",
        "command-center/receipts/REL-0006.json",
    ]
    for cond in CONDITIONS:
        if cond.get("special") == "rel-0003-ruling":
            _write(root / REL0003, rel0003_packet(named, recorded=True))
            for rel in named:
                _write(root / rel, named_receipt(Path(rel).stem))
        else:
            _write(root / cond["evidence_path"], evidence_doc(cond["id"], "TRUE"))


def write_canary_decoy(root: Path) -> None:
    """A canary-success file that condition 13 must ignore without REL-0003."""
    decoy = root / "command-center" / "receipts" / "canary-success.json"
    _write(
        decoy,
        {
            "canary": "succeeds",
            "release": "green",
            "verdict": "TRUE",
            "ok": True,
        },
    )
