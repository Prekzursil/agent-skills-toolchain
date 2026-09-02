"""AUD-0068 closed 29-artifact contract and live-root discovery.

The original Prompt One tree (harness-restore-20260806) is a Windows host
path. This module names a closed set of 29 catalog-attested primary
artifacts (one per major numbered document, plus JSON twins for the
quota-bearing libraries). It is not a byte copy of the missing tree.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0068"
OUT_REL = "command-center/audit/AUD-0068-claim-extraction-canonical.json"
SCHEMA_REL = "command-center/schema/claim-record.schema.json"
FIXTURE_CORPUS = HERE / "fixtures" / "corpus"
SENTINEL = (
    "SUCCESS:AUD-0068 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
PLANTED_TOKEN = "PLANTED:AUD-0068-SYNTHETIC"
PLANTED_HEADING = "PLANTED-SYNTHETIC-CLAIM AUD-0068"

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0068/probe1_coverage.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0068/probe2_reverse_trace.py"
)

# Closed 29: catalog-attested numbered primaries + JSON twins for quota libs.
# Derived because the named "29-artifact contract list" file is absent here
# and AUD-0067's census artifact is also absent.
CONTRACT_29: tuple[str, ...] = (
    "00-CURRENT-STATE-INVENTORY.md",
    "01-BLOCKER-REPRODUCTION.md",
    "02-BLOCKER-ROOT-CAUSE.md",
    "03-PLUGIN-LIFECYCLE-MAP.md",
    "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md",
    "06-PROGRAM-B-SCOPE-DOSSIER.md",
    "07-OPTION-UNIVERSE.md",
    "07-OPTION-UNIVERSE.json",
    "08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md",
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "09-RECONCILED-BACKLOG.md",
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "10-WORKFLOW-FORGE-SPEC.md",
    "11-COUNCIL-SPECIFICATION.md",
    "11-COUNCIL-SPECIFICATION.schema.json",
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.md",
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "13-ARCHITECTURE-CANDIDATES.md",
    "14-NO-REGRESSION-CONTRACT.md",
    "15-IMPLEMENTATION-PRECONDITIONS.md",
    "15-PROMPT-TWO-SPEC.md",
    "16-GRILL-QUEUE.md",
    "17-DECISION-LOG.md",
    "18-OPEN-UNKNOWNS-AND-PROBES.md",
    "19-SUBSTANCE-AUDIT-BLUEPRINTS.md",
    "24-REPO-RECONCILE.md",
    "31-LANE-foundry.md",
    "32-OWNER-DECISIONS.md",
    "33-INTEGRATION.md",
)

LIVE_ROOT_CANDIDATES = (
    Path.home() / ".claude" / "harness-restore-20260806",
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("/c/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("/opt/p2/harness-restore-20260806"),
    REPO / "harness-restore-20260806",
    REPO / "command-center" / "sources" / "harness-restore-20260806",
)

VERDICT_TAGS = (
    "CONFIRMED",
    "REFUTED",
    "PARTIAL",
    "NOT-CHECKED",
    "UNVERIFIED",
    "CONTESTED",
    "BLOCKED",
    "VERIFIED",
)

SCHEMA_STATUS = {
    "CONFIRMED": "CONFIRMED",
    "REFUTED": "REFUTED",
    "PARTIAL": "PARTIAL",
    "NOT-CHECKED": "NOT-CHECKED",
    "UNVERIFIED": "UNVERIFIED",
    "CONTESTED": "CONTESTED",
    "VERIFIED": "VERIFIED",
    "BLOCKED": "UNVERIFIED",
}

STRUCTURAL_HEADINGS = frozenset(
    {
        "table of contents",
        "revision history",
        "see also",
        "index",
        "appendix",
        "document title",
        "contents",
    }
)

JSON_HEADING_KEYS = frozenset(
    {"title", "heading", "section", "name", "h1", "h2", "h3"}
)

assert len(CONTRACT_29) == 29
assert len(set(CONTRACT_29)) == 29


def live_roots_present() -> list[str]:
    out: list[str] = []
    for root in LIVE_ROOT_CANDIDATES:
        if root.is_dir():
            out.append(str(root))
    return out


def find_live(name: str) -> Path | None:
    for root in LIVE_ROOT_CANDIDATES:
        cand = root / name
        if cand.is_file():
            return cand
    return None
