"""The three discovery_only artifacts WFA-0006 traces."""
from __future__ import annotations

ARTIFACTS: tuple[str, ...] = (
    "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
)

ROLE_DISCOVERY = "DISCOVERY-AWARE"
ROLE_CAPABILITY = "CAPABILITY-ASSERTING"
