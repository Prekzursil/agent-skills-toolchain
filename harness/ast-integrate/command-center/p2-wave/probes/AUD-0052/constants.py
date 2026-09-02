"""AUD-0052 paths, seeds, and probe commands."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0052"
OUT_REL = "command-center/audit/AUD-0052-test-order-dependence.json"
SCHEMA_REL = "command-center/schema/audit-finding.schema.json"
LAB_REL = "command-center/p2-wave/probes/AUD-0052/lab"
PRODUCT_ROOT_REL = "tools"
SEEDS = (101, 202, 303)
N_REPEATS = 5
PRODUCT_COLLECT_FLOOR = 50
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0052/probe1_three_seeds.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0052/probe2_five_repeats.py"
)
QUESTION = (
    "Which tests pass in declaration order but fail under a shuffled order, "
    "and which produce a different result across repeated identical runs?"
)
