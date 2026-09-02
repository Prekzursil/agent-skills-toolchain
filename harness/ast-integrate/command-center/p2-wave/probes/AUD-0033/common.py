#!/usr/bin/env python3
"""Shared constants for AUD-0033 documentation-to-path integrity."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0033"
OUT_REL = "command-center/audit/AUD-0033-doc-path-reference-integrity.json"
SCHEMA_REL = "command-center/schema/audit-finding.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0033 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Does every filesystem path cited in a command-center document, rule, "
    "skill, or README resolve to a file that exists at that path today?"
)
TITLE = "Documentation-to-path reference integrity sweep"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0033/probe1_extract_existence.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0033/probe2_git_log_missing.py"
)
CONTROL_REL = (
    "command-center/p2-wave/probes/AUD-0033/fixtures/control-fence-vs-prose.md"
)
FENCE_PRESENT = "command-center/schema/audit-finding.schema.json"
FENCE_MISSING = "command-center/does-not-exist/AUD-0033-planted-missing.json"
PROSE_FALSE_PATH = "docs/never/cited/from/prose-only.md"
TICK_PATH = "tools/command-center/unit_manifest.py"
SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        ".venv",
        "venv",
    }
)
SKIP_FILE_NAMES = frozenset(
    {
        "SUBAGENT-RETURN.json",
        "UNIT-ARTIFACT-MANIFEST.json",
        "AUD-0033-doc-path-reference-integrity.json",
    }
)
SKIP_NAME_PREFIXES = (
    "P2-CLOUD-LEFTOVER",
    "CLOUD-DONE-FROM-LOGS",
    "P2-CLOUD-PROGRESS",
)
HARNESS_ROOTS = (
    Path.home() / ".claude",
    Path.home() / ".mcp.json",
    Path.home() / ".cursor" / "mcp.json",
    Path.home() / ".cursor" / "cli.json",
    Path.home() / ".cursor" / "skills-cursor",
    Path.home() / ".cursor" / "skills",
)
