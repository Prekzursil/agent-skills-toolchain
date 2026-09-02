"""RES-0002 contract constants. Sentinel text is the catalog completion_sentinel."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT_ID = "RES-0002"
OUTPUT_REL = "command-center/research/RES-0002.json"
SCHEMA_REL = "command-center/schema/research-claim-record.schema.json"
CATALOG_SCHEMA_REL = "command-center/schema/measurement-run.schema.json"
FIXTURES = HERE / "fixtures"

SENTINEL = (
    "SUCCESS:RES-0002 in the receipt AND a recorded verdict per tool type "
    "PLUS the file:line of the comparison that maps HTTP 200 to FAILED, "
    "or an explicit REFUTED if no such line exists"
)

QUESTION = (
    "05-ECO section 6 records that a downstream reader who trusted the "
    "tool-sentinel would have discarded good evidence, and names the probe: "
    "does the tool-sentinel PostToolUse hook report FAILED (exit code 200) "
    "only for WebFetch, or does it also fire for WebSearch and Read in the "
    "same session - i.e. is the inversion WebFetch-specific or general?"
)

P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0002/probe1_locate_comparison.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0002/probe2_session_verdicts.py"
)

SESSION_TOOLS = ("WebSearch", "Read", "WebFetch")
SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        "deps",
        "vendor",
        "dist",
        "build",
        "site-packages",
    }
)
# Live estate scan must not treat this unit's own fixtures as the Windows hook.
LIVE_SCAN_SKIP_PREFIXES = (
    "command-center/p2-wave/probes/RES-0002/",
    "command-center/research/RES-0002.json",
)
HOOK_SUFFIXES = (".py", ".js", ".mjs", ".cjs", ".sh", ".bash")
STATUS_NAMES = frozenset(
    {"status", "status_code", "http_status", "httpStatus", "code"}
)
