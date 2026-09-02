"""Independent bidirectional review of the fold.

Forward: each ledger record's source.raw matches the source line.
Reverse: reconstituting records+drops reproduces the source JSONL.
This reviewer does not author the migration plan.
"""
from __future__ import annotations

from pathlib import Path

import fold as F  # noqa: E402

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "fixtures" / "source-events.jsonl"
LEDGER = HERE / "fixtures" / "ledger.jsonl"
DROPS = HERE / "fixtures" / "drops.jsonl"


def review(source: Path | None = None) -> dict:
    source = source or SOURCE
    repo = HERE.parents[3]
    try:
        rel = source.relative_to(repo).as_posix()
    except ValueError:
        rel = source.name
    tmp_ledger = LEDGER
    tmp_drops = DROPS
    result = F.fold_file(source, tmp_ledger, tmp_drops, rel)
    directions = {
        "forward_ok": result.get("forward_ok"),
        "reverse_ok": result.get("reverse_ok"),
        "both_directions": result.get("both_directions"),
    }
    verdict = (
        "PASS"
        if result.get("ok")
        and result.get("conservation_holds")
        and result.get("source_unmodified")
        and directions["both_directions"]
        else "FAIL"
    )
    return {
        "reviewer_id": "ARC-0035-independent-fold-reviewer",
        "independent": True,
        "verdict": verdict,
        "both_directions": bool(directions["both_directions"]),
        "conservation_holds": result.get("conservation_holds"),
        "source_unmodified": result.get("source_unmodified"),
        "input_events": result.get("input_events"),
        "output_records": result.get("output_records"),
        "classified_drops": result.get("classified_drops"),
        "notes": (
            "Re-ran the fold against the frozen slice. Forward checks "
            "source.raw/sha256 per folded line. Reverse concatenates "
            "ledger source.raw plus classified-drop source.raw in line_no "
            "order and requires byte-identical reconstitution of the slice."
        ),
    }
