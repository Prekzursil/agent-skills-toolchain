"""CNF-0106 catalog contract constants (single source)."""
from __future__ import annotations

UNIT_ID = "CNF-0106"
OUTPUT_REL = "command-center/confirmation/CNF-0106-hermetic-run.json"
SCHEMA_REL = "command-center/schema/hermeticity-report.schema.json"
SENTINEL = (
    "SUCCESS:CNF-0106 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both the blocked and "
    "unblocked runs completed and the attempted-destination list is attached. "
    "Any other terminal state is FAILED:CNF-0106 <classification> with the "
    "diagnostic tail attached."
)
QUESTION = (
    "Does anything silently reach the network? Run the install and the full "
    "test suite with egress blocked and answer: which steps fail, and does any "
    "test that claims to be offline actually download something? The measured "
    "precedent is 14 tests silently downloading despite comments stating they "
    "never do."
)
# Proven live on this runner (TCP 443). Used as the silent-egress target.
EGRESS_HOST = "1.1.1.1"
EGRESS_PORT = 443
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0106/probe1_blocked_unblocked.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0106/probe2_detector_control.py"
)
LYING_COMMENT = (
    "This test never downloads and never touches the network; it is fully offline."
)
