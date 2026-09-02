"""TST-0232 catalog contract (single source)."""
from __future__ import annotations

UNIT_ID = "TST-0232"
OUTPUT_REL = "command-center/receipts/TST-0232.json"
CATALOG_SCHEMA_REL = "command-center/schema/receipt.schema.json#/$defs/benchmark_result"
LOCAL_SCHEMA_REL = (
    "command-center/p2-wave/probes/TST-0232/holdout-gate-receipt.schema.json"
)
SENTINEL = "SUCCESS:TST-0232"
QUESTION = (
    "Can a candidate win by special-casing visible fixtures? PASS requires a "
    "holdout split never exposed to implementers, with the gate reporting BOTH "
    "scores and failing any candidate whose visible-vs-holdout gap exceeds a "
    "declared threshold."
)
TITLE = "A holdout set the implementer never sees defeats benchmark gaming"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0232/probe1_overfit_gap.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0232/probe2_holdout_provenance.py"
)
GAP_THRESHOLD = 0.25
THRESHOLD_VERSION = "tst-0232-gap-v1"
THRESHOLD_FORMULA = (
    "gap = accuracy(visible) - accuracy(holdout); FAIL_GAMING if gap > 0.25"
)
MIN_SPLIT = 12
VISIBLE_PREFIX_FILE = (
    "command-center/p2-wave/probes/TST-0232/fixtures/visible-cases.json"
)
HOLDOUT_PREFIX_FILE = (
    "command-center/p2-wave/probes/TST-0232/fixtures/holdout-cases.json"
)
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
SEED = 2322026
