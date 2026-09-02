"""Live input locations and fixture paths for SYN-0002."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"

LIVE_GRAPH = "command-center/synthesis/SYN-0001.root-cause-hierarchy.json"
LIVE_CLAIMS = "command-center/CLAIM-REGISTRY.json"
LIVE_RISKS = "command-center/RISK-REGISTER.md"
LIVE_UNKNOWNS = "command-center/UNKNOWNS-REGISTER.md"
OUT = "command-center/receipts/SYN-0002.json"
SCHEMA = "command-center/schema/detector-control.schema.json"

GRAPH_CLEAN = FIXTURES / "graph.clean.json"
GRAPH_CYCLE = FIXTURES / "graph.cycle.json"
GRAPH_DANGLING = FIXTURES / "graph.dangling.json"
GRAPH_EMPTY = FIXTURES / "graph.empty_cause.json"
CLAIMS_CLEAN = FIXTURES / "claims.clean.json"
CLAIMS_ORPHAN = FIXTURES / "claims.orphan.json"
RISKS = FIXTURES / "risks.md"
UNKNOWNS = FIXTURES / "unknowns.md"

COMPLETION_SENTINEL = (
    "SUCCESS:SYN-0002 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both planted-defect runs "
    "are recorded as FIRED and the clean run as SILENT. Any other terminal "
    "state is FAILED:SYN-0002 <classification> with the diagnostic tail attached."
)
