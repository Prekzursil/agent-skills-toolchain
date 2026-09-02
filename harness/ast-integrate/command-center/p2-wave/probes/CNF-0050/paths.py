"""Stable paths for CNF-0050."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "CNF-0050"
OUT_REL = "command-center/confirmation/CNF-0050-rollback-guide-conformance.json"
SCHEMA_REL = "command-center/schema/conformance-report.schema.json"
MANIFEST_REL = "command-center/ROLLBACK-MANIFEST.md"
RUNBOOK_REL = "command-center/RUNBOOK.md"
CATALOG_SENTINEL = (
    "SUCCESS:CNF-0050 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every step in the guide "
    "has a recorded exit code or an explicit deviation note; no step is "
    "unexecuted. Any other terminal state is FAILED:CNF-0050 <classification> "
    "with the diagnostic tail attached."
)
QUESTION = (
    "Can an operator actually follow the rollback guide? Execute it literally, "
    "top to bottom, with no improvisation, and answer: which steps fail, which "
    "are ambiguous enough that two operators would diverge, and which are "
    "missing entirely?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0050/probe1_literal.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0050/probe2_detector.py"
)
PAYLOAD = b"CNF-0050-rollback-payload-v1\n"
PAYLOAD_SHA256 = "9ee6c45cd7356bfa5545cc59dce8bfdc8368eb6fef624c46beea5271e8aee443"
CORRECTED_BLOB_RECIPE = "git cat-file -p <rev>:<path>"
