"""SYN-0004 contract constants. Sentinel text is the catalog completion_sentinel."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

UNIT_ID = "SYN-0004"
OUTPUT_REL = "command-center/receipts/SYN-0004.json"
SCHEMA_REL = "command-center/schema/severity-reconciliation.schema.json"
HIERARCHY_REL = "command-center/synthesis/SYN-0001.root-cause-hierarchy.json"
CLAIM_REGISTRY_REL = "command-center/CLAIM-REGISTRY.json"
RISK_REGISTER_REL = "command-center/RISK-REGISTER.md"

SENTINEL = (
    "SUCCESS:SYN-0004 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and zero unexplained severity "
    "deltas remain open. Any other terminal state is FAILED:SYN-0004 "
    "<classification> with the diagnostic tail attached."
)

QUESTION = (
    "Question: after N findings collapse into one root cause, does the cause "
    "carry at least the maximum severity of its subtree? Target: recompute "
    "severity bottom-up over the hierarchy and emit every INVERSION (a P2 "
    "cause with a P0 child) and every DILUTION (a cause whose severity was "
    "averaged rather than maximised). Collapse is the moment a P0 silently "
    "becomes a bullet under a P2 heading."
)

P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0004/probe1_max_not_mean.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0004/probe2_planted_inversion.py"
)

PLANTED_CAUSE = "CAUSE-PLANTED-P3"
PLANTED_CHILD = "CHILD-PLANTED-P0"
MIN_BYTES = 2500
