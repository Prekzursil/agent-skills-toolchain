"""Shared paths and contract constants for AUD-0067."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0067"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
OUT_REL = "command-center/audit/AUD-0067-prompt-one-artifact-census.json"
SCHEMA_REL = "command-center/schema/audit-inventory.schema.json"
CATALOG = REPO / CATALOG_REL
OUT = REPO / OUT_REL
SCHEMA = REPO / SCHEMA_REL

COMPLETION_SENTINEL = (
    "SUCCESS:AUD-0067 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "For each of the 29 contracted Prompt-One artifacts, which tree does it "
    "live in, and does the set of 29 hold within a SINGLE tree or only as "
    "the union of two?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0067/probe1_per_tree.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0067/probe2_sha256.py"
)

# Catalog-cited Prompt One numbered filenames in the 00-19 band. md/json
# twins are distinct contracted names. 04-* is not cited in this catalog.
# PROMPT-ONE-FLOOR-AUDIT.json is absent; this list is recovered from
# WORK-UNIT-CATALOG.json citations, not from a missing floor-audit file.
CONTRACT_29: tuple[str, ...] = (
    "00-CURRENT-STATE-INVENTORY.md",
    "01-BLOCKER-REPRODUCTION.md",
    "02-BLOCKER-ROOT-CAUSE.md",
    "03-PLUGIN-LIFECYCLE-MAP.md",
    "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md",
    "06-PROGRAM-B-SCOPE-DOSSIER.md",
    "06-PROGRAM-B-SCOPE-DOSSIER.json",
    "07-OPTION-UNIVERSE.md",
    "07-OPTION-UNIVERSE.json",
    "08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md",
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "09-WORKFLOW-BLUEPRINT-LIBRARY.md",
    "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    "10-WORKFLOW-FUSION-AND-CERTIFICATION-PLAN.md",
    "10-WORKFLOW-FUSION-AND-CERTIFICATION-MAPS.json",
    "11-COUNCIL-SPECIFICATION.md",
    "11-COUNCIL-SPECIFICATION.schema.json",
    "11-COUNCIL-OPTION-CARDS.md",
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.md",
    "13-ARCHITECTURE-CANDIDATES.md",
    "14-NO-REGRESSION-CONTRACT.md",
    "15-IMPLEMENTATION-PRECONDITIONS.md",
    "16-GRILL-QUEUE.md",
    "17-DECISION-LOG.md",
    "18-OPEN-UNKNOWNS-AND-PROBES.md",
    "19-SUBSTANCE-AUDIT-BLUEPRINTS.md",
)

HARNESS_CANDIDATES = (
    str(Path.home() / ".claude/harness-restore-20260806"),
    "/root/.claude/harness-restore-20260806",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806",
)

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".mypy_cache",
        "AUD-0067",
    }
)


def find_line(text: str, snippet: str) -> int:
    idx = text.find(snippet)
    if idx < 0:
        return -1
    return text[:idx].count("\n") + 1
