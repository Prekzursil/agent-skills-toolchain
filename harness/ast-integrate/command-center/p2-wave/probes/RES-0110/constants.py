"""RES-0110 contract constants. Sentinel text is the catalog completion_sentinel."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

UNIT_ID = "RES-0110"
OUTPUT_REL = "command-center/research/RES-0110.json"
SCHEMA_REL = "command-center/schema/research-registry.schema.json"
INDEX_REL = "command-center/p2-wave/probes/RES-0110/fixtures/implementation-index.json"
PAPERS_REL = "command-center/p2-wave/probes/RES-0110/fixtures/papers.json"

SENTINEL = (
    "SUCCESS:RES-0110 in the receipt AND a candidate register with a recorded "
    "implementation-search per row and a passing detector control"
)

QUESTION = (
    "Which published mechanisms relevant to this program have a clear enough "
    "specification to implement but no widely used implementation - the "
    "highest-leverage gem class because the work is done and the adoption is not?"
)

# Popular = first-class named API in a major agent framework, or a dedicated
# repo at or above this star floor. Research clones below the floor are recorded
# hits, not popular implementations.
MAJOR_FRAMEWORKS = frozenset(
    {
        "langchain",
        "langgraph",
        "llama-index",
        "autogen",
        "crewai",
        "semantic-kernel",
    }
)
STAR_FLOOR = 1000

CONTROL_ID = "react-interleaved-thought-action"
CONTROL_MECH_ID = CONTROL_ID
CONTROL_KNOWN_IMPL = "langgraph.prebuilt.create_react_agent"
PLANTED_ABSENT_ID = "planted-absent-zorp-orchestrator"

P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0110/probe1_search_per_row.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0110/probe2_detector_and_e3.py"
)
