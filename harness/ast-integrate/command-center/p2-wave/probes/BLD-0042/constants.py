"""BLD-0042 shared constants."""
from __future__ import annotations

UNIT_ID = "BLD-0042"
SENTINEL = "SUCCESS:BLD-0042"
OUT_REL = "command-center/receipts/BLD-0042.json"
SCHEMA_REL = "command-center/schema/test-quality-census.schema.json"
AUD0057_REL = "command-center/audit/AUD-0057-assertion-strength-census.json"
AUD0041_REL = "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0042/probe1_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0042/probe2_reviewer.py"
)
QUESTION = (
    "Question: which default parameter value is never exercised because every "
    "call site passes it explicitly? For each public function default, CLI flag "
    "default and config default, enumerate call sites and tests and report the "
    "defaults with zero exercising callers. This is the static twin of the "
    "measured DEFAULT_MIN_BYTES mutation survivor and of validate.py's "
    "require_complete=False being invoked bare by CI. SCOPE BOUNDARY: AUD-0057 "
    "is the assertion-strength census of defaults a test never exercises. This "
    "unit consumes it and contributes the CI-INVOCATION join."
)
