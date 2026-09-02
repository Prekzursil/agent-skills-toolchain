"""RES-0114 catalog contract constants (single source)."""
from __future__ import annotations

UNIT_ID = "RES-0114"
OUTPUT_REL = "command-center/research/RES-0114.json"
# Catalog declares the shared family; RES-0001 authors it. This unit validates
# against the local discriminating schema so G-1 does not wait on RES-0001.
CATALOG_SCHEMA_REL = "command-center/schema/research-claim-record.schema.json"
SCHEMA_REL = "command-center/p2-wave/probes/RES-0114/claim_record.schema.json"
SENTINEL = (
    "SUCCESS:RES-0114 in the receipt AND a property list with the "
    "silent-download case explicitly mapped and one impossible property named"
)
QUESTION = (
    "What does a hermetic build guarantee, what does it cost, and which "
    "hermeticity properties can an agent run adopt given that its inputs "
    "include a live model and a live web - a question the estate's own "
    "hermetic-probe experience makes concrete?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0114/probe1_silent_download_mapping.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0114/probe2_impossible_property.py"
)
CATCHING_PROPERTY_ID = "P-UNDECLARED-EGRESS"
IMPOSSIBLE_PROPERTY_ID = "P-CLOSED-WORLD-BIT-IDENTITY"
LYING_COMMENT = (
    "This test never downloads and never touches the network; it is fully offline."
)
MOTIVATING_CASE = (
    "14 tests silently downloaded get-pip.py from the network despite comments "
    "claiming they never download; a cache re-verify discarded the fixture and "
    "refetched"
)
