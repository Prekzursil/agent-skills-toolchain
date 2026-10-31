"""ADV-0128 shared constants."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT_ID = "ADV-0128"
OUT_REL = "command-center/adversarial/ADV-0128-offline-and-partition-degrade-loudly.json"
SENTINEL = "SUCCESS:ADV-0128"

PATHS = ("registry", "research", "cloud-dispatch", "cross-vendor-mcp")

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0128/probe1_full_offline.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0128/probe2_mid_partition.py"
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT_ID} {msg}")
    return 1
