"""Shared constants for the WFA-0127 workflow-scout runner and IR."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
CORPUS = FIXTURES / "corpus"
ANCHORS = CORPUS / "anchors"
GOALS = FIXTURES / "goals"
WFA0019_CORPUS = (
    REPO / "command-center" / "p2-wave" / "probes" / "WFA-0019" / "fixtures" / "corpus"
)
ARTIFACT_REL = "command-center/wfa/WFA-0127-workflow-scout-executable-spec.json"
SCHEMA_REL = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/WorkflowIR"
UNIT_ID = "WFA-0127"
SENTINEL = "SUCCESS:WFA-0127"

SOURCE_CLASS_FILES = {
    "registry": "registry.json",
    "repository": "repository.json",
    "marketplace": "marketplace.json",
    "public-docs": "public_docs.json",
    "papers": "papers.json",
}
WFA0019_CLASS = "wfa-0019-fixture"
DEFAULT_SOURCE_CLASSES = list(SOURCE_CLASS_FILES) + [WFA0019_CLASS]

STAGE_IDS = [
    "ingest-goal",
    "fan-out-source-classes",
    "search-hits",
    "verify-provenance",
    "verify-licence",
    "decompose-mechanisms",
    "rank-dispositions",
    "anti-rebuild-gate",
    "characterise-gap",
    "emit-result",
]

ADEQUATE_COVERAGE = 0.5
ADOPT_COVERAGE = 1.0
ADAPT_COVERAGE = 0.5
ANTI_REBUILD_COVERAGE = 0.5
RANK_PAD_FORBIDDEN_BELOW = ADEQUATE_COVERAGE
MAX_RANKED = 12

PERMISSIVE = frozenset(
    {"MIT", "Apache-2.0", "BSD-3-Clause", "CC-BY-4.0", "BSD-2-Clause", "ISC"}
)
UNKNOWN_LICENCES = frozenset({"UNKNOWN", "", "null"})

