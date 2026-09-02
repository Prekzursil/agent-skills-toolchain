"""Shared paths and constants for AUD-0058."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0058"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
OUT_REL = "command-center/audit/AUD-0058-skill-load-trigger-audit.json"
SCHEMA_REL = "command-center/schema/audit-finding.schema.json"
CATALOG = REPO / CATALOG_REL
OUT = REPO / OUT_REL
SCHEMA = REPO / SCHEMA_REL
FIXTURE_ROOT = HERE / "fixtures" / "estate"

COMPLETION_SENTINEL = (
    "SUCCESS:AUD-0058 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "For every skill, does its frontmatter cause the intended load behaviour "
    "- always-on for those with no paths key, lazy for those with one - and "
    "which skills were unintentionally demoted by adding a paths glob?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0058/probe1_frontmatter.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0058/probe2_turn0.py"
)

ALWAYS_ON_MARKER = "TURN0-BODY:AUD0058-ALWAYS-ON"
BARE_MARKER = "TURN0-BODY:AUD0058-BARE"
LAZY_MARKER = "LAZY-BODY:AUD0058-LAZY"
DEMOTED_MARKER = "TURN0-BODY:AUD0058-DEMOTED"

INSTRUMENT = (
    "turn0-context-bag (injected body bytes, not a frontmatter classifier; "
    "equivalent of grok inspect --json on this worktree)"
)


def find_line(text: str, snippet: str) -> int:
    idx = text.find(snippet)
    if idx < 0:
        return -1
    return text[:idx].count("\n") + 1
