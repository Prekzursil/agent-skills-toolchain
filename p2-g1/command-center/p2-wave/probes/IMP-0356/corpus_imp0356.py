"""Census corpus for IMP-0356: 20 deterministic recorded-council fixtures.

Synthetic but honestly labelled: these are TEST fixtures shaped like recorded
council final artifacts. The deficiency pattern is chosen deterministically so
that "calibration" is the output missing (absent or vacuous) most often, which
is the receipt's published census claim; probe1 recomputes the census live from
these files rather than trusting the receipt.
"""
from __future__ import annotations

import json
from pathlib import Path

from council.outcomes.completeness import CHARTER_REQUIRED_OUTPUTS, complete_artifact

N_COUNCILS = 20

# Per-output deficiency plan (index -> kind). calibration must lead.
# kinds: "absent" = key not present, "vacuous" = key present but empty/TBD.
DEFICIENCY_PLAN: dict[str, dict[int, str]] = {
    "calibration": {
        0: "absent", 3: "absent", 6: "absent", 9: "absent", 12: "absent",
        15: "absent", 17: "absent", 18: "absent", 19: "absent",
        1: "vacuous", 7: "vacuous", 13: "vacuous",
    },
    "dissent": {2: "absent", 8: "vacuous"},
    "unknowns": {4: "vacuous"},
    "experiments": {10: "absent"},
    "idea_ledger": {11: "vacuous"},
    "votes": {16: "vacuous"},
}


def build_doc(i: int) -> dict:
    doc = complete_artifact(f"rec-{i:02d}")
    for key, plan in DEFICIENCY_PLAN.items():
        kind = plan.get(i)
        if kind == "absent":
            doc["outputs"].pop(key, None)
        elif kind == "vacuous":
            doc["outputs"][key] = {"items": [], "note": "TBD"}
    return doc


def corpus_docs() -> list[dict]:
    return [build_doc(i) for i in range(N_COUNCILS)]


def materialize(folder: Path) -> list[Path]:
    """Write rec-*.json fixtures idempotently and return the sorted paths."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, doc in enumerate(corpus_docs()):
        p = folder / f"rec-{i:02d}.json"
        p.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        paths.append(p)
    return sorted(folder.glob("rec-*.json"))


assert "calibration" in CHARTER_REQUIRED_OUTPUTS
