"""WFA-0084 shared paths and named-probe commands."""

from __future__ import annotations

UNIT_ID = "WFA-0084"
OUT_REL = "command-center/wfa/WFA-0084-registry-query-interface.json"
SCHEMA_REL = (
    "command-center/p2-wave/probes/WFA-0084/handoff-contract.schema.json"
)
PACK_REL = "command-center/wfa/schema/wfa-schema-pack.json"
SENTINEL = "SUCCESS:WFA-0084"
QUESTION = (
    "Implementation target: a typed query interface - by disposition, family, "
    "mechanism, licence class, task class and fusibility - so downstream "
    "phases consume the registry through a stable contract instead of "
    "re-parsing four JSON files each with its own conventions."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0084/probe1_query_expected_sets.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0084/"
    "probe2_fusion_consumer_and_version.py"
)

LIVE_GRAPHS = {
    "registry": "command-center/wfa/WFA-0078-candidate-registry-v2.json",
    "provenance": "command-center/wfa/WFA-0079-provenance-license-graph-v2.json",
    "components": "command-center/wfa/WFA-0080-semantic-component-graph.json",
    "compat": "command-center/wfa/WFA-0081-merge-compatibility-map-v2.json",
}

FIXTURE_FILES = {
    "registry": "registry.json",
    "provenance": "provenance.json",
    "components": "components.json",
    "compat": "compat.json",
}

QUERY_TYPES = (
    "disposition",
    "family",
    "mechanism",
    "licence_class",
    "task_class",
    "fusibility",
)
