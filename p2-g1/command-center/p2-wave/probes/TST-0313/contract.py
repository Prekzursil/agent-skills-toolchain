"""TST-0313 catalog contract constants."""
from __future__ import annotations

UNIT_ID = "TST-0313"
OUTPUT_REL = "command-center/receipts/TST-0313.json"
SCHEMA_REL = "command-center/schema/receipt.schema.json"
SENTINEL = "SUCCESS:TST-0313"
QUESTION = (
    "Implementation target: step 10 of the loop at :11148 requires updating "
    "the benchmark so the same failure cannot silently return. Enforce it "
    "structurally: a defect record cannot move to CLOSED until a case exists "
    "whose oracle FAILS on the pre-fix commit and PASSES on the post-fix "
    "commit. Both runs must be recorded. A test written after the fix and "
    "never run against the broken state proves nothing, which is the ordinary "
    "way this requirement is satisfied on paper and violated in fact."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0313/probe1_prefix_missing.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0313/probe2_census_debt.py"
)
