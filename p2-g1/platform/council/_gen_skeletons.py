"""Write-as-you-go skeletons for council protocol blueprints P37-P48.

Emits twelve schema-valid but DELIBERATELY EMPTY CouncilSpec instances so that
whatever is on disk is always truthful. Each carries the honesty marker in
metadata.notes. `_gen_protocols_37_48.py` overwrites these with the real specs.
"""

from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "protocols")

MARKER = (
    "SKELETON - UNKNOWN, not yet measured. If it still reads this way, the unit "
    "died before measuring anything and no field here may be cited."
)

SLUGS = [
    ("p37", "pairwise-comparison"),
    ("p38", "analysis-of-competing-hypotheses"),
    ("p39", "key-assumptions-check"),
    ("p40", "quality-of-information-check"),
    ("p41", "deception-detection"),
    ("p42", "argument-mapping"),
    ("p43", "premortem"),
    ("p44", "postmortem-5whys-causal"),
    ("p45", "scientific-peer-review"),
    ("p46", "architecture-review-board"),
    ("p47", "incident-war-room"),
    ("p48", "kill-the-company"),
]


def skeleton(num: str, slug: str) -> dict:
    return {
        "schema_version": "1.0.0",
        "council_id": f"{num}-{slug}",
        "objective": {
            "statement": "SKELETON - this protocol has not been authored yet.",
            "risk_tier": "moderate",
            "desired_output": "decision",
        },
        "participants": {
            "selection": {"mode": "automatic"},
            "count": {"mode": "range", "min": 1, "max": 2},
        },
        "topology": {"kind": "flat"},
        "protocol": {"sequence": [{"kind": "round_robin"}]},
        "voting": {"method": "synthesis_only"},
        "stopping": {
            "source_expression": "rounds_elapsed >= 1",
            "expression": {"metric": "rounds_elapsed", "op": ">=", "value": 1},
        },
        "outcomes": {"allowed": ["no_decision"]},
        "outputs": {"required": ["transcript"]},
        "metadata": {"title": f"{num.upper()} {slug} (SKELETON)", "notes": MARKER},
    }


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    written = 0
    for num, slug in SLUGS:
        path = os.path.join(OUT, f"{num}-{slug}.councilspec.json")
        if os.path.exists(path):
            print(f"SKIP (exists) {path}")
            continue
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(skeleton(num, slug), fh, indent=2, ensure_ascii=True)
            fh.write("\n")
        written += 1
    print(f"SUCCESS:council-skeletons wrote={written} dir={OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
