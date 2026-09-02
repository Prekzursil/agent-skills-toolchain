"""Shared IMP-0235 probe fixtures (hermetic; no network)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center"))

from research.blueprints.citation import (  # noqa: E402
    UNRESOLVED,
    audit_citations,
    fetch_citation,
    naive_assume_unfetchable_valid,
)

LIVE_BODY = HERE / "fixtures" / "live-source.txt"
ART = REPO / "command-center" / "receipts" / "IMP-0235.json"
DEAD_REL = "command-center/p2-wave/probes/IMP-0235/fixtures/does-not-exist.txt"


def file_url(path: Path) -> str:
    return path.resolve().as_uri()


def live_citation() -> dict:
    return {
        "id": "C-LIVE",
        "url": file_url(LIVE_BODY),
        "quoted_span": "distinctive IMP-0235 live quote",
    }


def dead_citation() -> dict:
    return {
        "id": "C-DEAD",
        "url": file_url(REPO / DEAD_REL),
        "quoted_span": "this citation cannot be fetched",
    }


def both_states_audit() -> dict:
    live = live_citation()
    dead = dead_citation()
    honest = audit_citations([live, dead], fetch=fetch_citation)
    naive = naive_assume_unfetchable_valid([live, dead], fetch=fetch_citation)
    live_v = next(v for v in honest.verdicts if v.id == "C-LIVE")
    dead_v = next(v for v in honest.verdicts if v.id == "C-DEAD")
    naive_dead = next(v for v in naive.verdicts if v.id == "C-DEAD")
    return {
        "honest": honest.to_dict(),
        "naive": naive.to_dict(),
        "live_status": live_v.status,
        "dead_status": dead_v.status,
        "naive_dead_status": naive_dead.status,
        "dead_is_unresolved": dead_v.status == UNRESOLVED,
        "naive_accepts_dead": naive_dead.status != UNRESOLVED and naive_dead.assumed_valid,
        "live_not_unresolved": live_v.status != UNRESOLVED,
        "coverage": honest.coverage,
        "assumed_valid_count": honest.assumed_valid_count,
    }


def load_receipt() -> dict | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return None
    return json.loads(ART.read_text(encoding="utf-8"))
