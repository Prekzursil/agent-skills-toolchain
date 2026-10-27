"""shard2 wave-2 shared constants."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

OUT_REL = {
    "ADV-0128": "command-center/adversarial/ADV-0128-offline-and-partition-degrade-loudly.json",
    "ARC-0012": "command-center/phase3/A2/FAILURE-MODES.json",
    "ARC-0015": "command-center/phase3/A2/TEST-PLAN.json",
    "ARC-0021": "command-center/phase3/A3/MIGRATION.json",
}

SENTINEL = {
    "ADV-0128": "SUCCESS:ADV-0128",
    "ARC-0012": "SUCCESS:ARC-0012",
    "ARC-0015": "SUCCESS:ARC-0015",
    "ARC-0021": "SUCCESS:ARC-0021",
}
