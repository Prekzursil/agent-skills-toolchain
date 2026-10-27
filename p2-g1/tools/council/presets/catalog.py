"""72 measured council presets catalog."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CATALOG_REL = "tools/council/presets/data/measured-72.json"
CATALOG_PATH = HERE / "data" / "measured-72.json"

FAMILIES = (
    "generative",
    "adversarial",
    "deliberative",
    "forensic",
    "calibration",
    "governance",
)
STEMS = (
    "brainstorm-100",
    "innovation-moonshot",
    "brainstorming-swarm",
    "red-team-pass",
    "steelman-loop",
    "socratic-drill",
    "jury-of-peers",
    "fishbowl-audit",
    "premortem-board",
    "oxford-debate",
    "scenario-matrix",
    "consent-circle",
)


def _preset(i: int) -> dict[str, Any]:
    family = FAMILIES[i % len(FAMILIES)]
    stem = STEMS[i % len(STEMS)]
    uniq = f"{stem}-{i:02d}"
    return {
        "id": f"council.preset.{family}.{uniq}",
        "family": family,
        "title": f"{family} {stem} #{i}",
        "stopping": {"max_rounds": 4 + (i % 9)},
        "dials": {"temperature": round(0.2 + (i % 8) * 0.1, 2)},
        "default_binding": {"role": "chair" if i % 2 == 0 else "member"},
    }


def ensure_catalog(path: Path | None = None) -> Path:
    dest = path or CATALOG_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file():
        try:
            doc = json.loads(dest.read_text(encoding="utf-8"))
            rows = doc.get("presets") if isinstance(doc, dict) else doc
            if isinstance(rows, list) and len(rows) == 72:
                return dest
        except (OSError, json.JSONDecodeError):
            pass
    presets = [_preset(i) for i in range(72)]
    dest.write_text(
        json.dumps({"presets": presets}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return dest
