"""TST-0133 catalog contract constants (single source)."""
from __future__ import annotations

UNIT_ID = "TST-0133"
OUTPUT_REL = "command-center/receipts/TST-0133.json"
SCHEMA_REL = "command-center/schema/receipt.schema.json"
SCHEMA_DEF = "fault_injection_report"
SENTINEL = "SUCCESS:TST-0133"
QUESTION = (
    "Run the full suite with all egress blocked and enumerate every test that "
    "changes outcome. Target: produce the exact list of tests whose green "
    "depends on undeclared network access, and add an explicit `network` "
    "declaration to each. PASS requires: after remediation, the egress-blocked "
    "run and the egress-allowed run produce identical outcomes for every test "
    "not declaring network."
)
PLANTED_ID = "test_planted_url_fetch"
DOWNLOAD_ID = "test_package_download_get"
DECLARED_ID = "test_declared_healthcheck"
HERMETIC_IDS = ("test_local_index_parse", "test_cached_blob_digest")
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0133/probe1_delta_egress.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0133/probe2_detector_both_states.py"
)
