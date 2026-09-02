"""SYN-0013 probe-local paths and named-probe commands."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT_ID = "SYN-0013"
OUT_REL = "command-center/receipts/SYN-0013.json"
SCHEMA_REL = "command-center/schema/digest-loss-report.schema.json"
LIB_REL = "tools/synthesis/digest_loss.py"
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0013/probe1_use_vs_mention.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0013/probe2_retention_and_evidence.py"
)
SENTINEL = (
    "SUCCESS:SYN-0013 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the use-vs-mention control "
    "passes and per-class retention rates are published. Any other terminal "
    "state is FAILED:SYN-0013 <classification> with the diagnostic tail attached."
)
P1_CMD = P1_CMD
P2_CMD = P2_CMD
LIB_REL = LIB_REL
SCHEMA_REL = SCHEMA_REL
OUT_REL = OUT_REL
