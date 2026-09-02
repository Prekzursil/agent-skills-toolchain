"""Shared paths and catalog constants for AUD-0085."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0085"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
OUT_REL = "command-center/audit/AUD-0085-encoding-bom-mojibake-census.json"
SCHEMA_REL = "command-center/schema/audit-finding.schema.json"
CATALOG = REPO / CATALOG_REL
OUT = REPO / OUT_REL
SCHEMA = REPO / SCHEMA_REL
FIXTURES = HERE / "fixtures"

COMPLETION_SENTINEL = (
    "SUCCESS:AUD-0085 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Which files are not valid UTF-8, carry a byte-order mark, or contain "
    "mojibake from a prior double-decode - and which of those are consumed "
    "by a strict parser?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0085/probe1_decode.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0085/probe2_mojibake.py"
)

# Planted-control relative paths (posix).
FX_DOUBLE = "command-center/p2-wave/probes/AUD-0085/fixtures/double_decoded.json"
FX_CORRECT = "command-center/p2-wave/probes/AUD-0085/fixtures/correct_nonascii.json"
FX_BOM = "command-center/p2-wave/probes/AUD-0085/fixtures/utf8_bom.json"
FX_INVALID = "command-center/p2-wave/probes/AUD-0085/fixtures/invalid_utf8.json"
FX_PLUGIN = "command-center/p2-wave/probes/AUD-0085/fixtures/plugin.json"

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        ".tox",
        ".mypy_cache",
        "__pycache__",
        "ovh-monitor",
        "error-pull",
        "delivery-pull",
        "scw-pull",
        "mcp",
        "editor",
        ".agents",
    }
)
SKIP_BASENAMES = frozenset(
    {
        "_extract_out.json",
        "_extract2_out.json",
        "_extract3_out.json",
        "_final_out.json",
        "_validate_out.json",
        "AUD-0085-encoding-bom-mojibake-census.json",
        "SUBAGENT-RETURN.json",
        "UNIT-ARTIFACT-MANIFEST.json",
    }
)
# Generated probe sidecars (except planted fixtures) must not enter the census
# or live re-walks drift when receipts are written after emit.
SELF_PROBE_PREFIX = "command-center/p2-wave/probes/AUD-0085/"
SELF_FIXTURE_PREFIX = "command-center/p2-wave/probes/AUD-0085/fixtures/"
BINARY_SUFFIXES = frozenset(
    {
        ".pyc",
        ".pyo",
        ".so",
        ".o",
        ".a",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".pdf",
        ".zip",
        ".gz",
        ".bz2",
        ".xz",
        ".7z",
        ".class",
        ".exe",
        ".dll",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".ico",
        ".bin",
        ".wasm",
        ".whl",
        ".egg",
    }
)
TEXT_SUFFIXES = frozenset(
    {
        ".json",
        ".jsonl",
        ".md",
        ".txt",
        ".py",
        ".yml",
        ".yaml",
        ".toml",
        ".xml",
        ".html",
        ".htm",
        ".css",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".sh",
        ".bash",
        ".zsh",
        ".ps1",
        ".csv",
        ".ini",
        ".cfg",
        ".conf",
        ".rst",
        ".svg",
        ".sql",
        ".c",
        ".h",
        ".cpp",
        ".hpp",
        ".java",
        ".rs",
        ".go",
        ".rb",
        ".php",
        ".lock",
        ".gitignore",
        ".editorconfig",
        ".env",
        ".properties",
    }
)
STRUCTURED_SUFFIXES = frozenset({".json", ".jsonl", ".yaml", ".yml"})
UNSTRUCTURED_MAX_BYTES = 2_000_000
STRUCTURED_MAX_BYTES = 8_000_000
# Aliases matching census.py import names
SKIP_BASENAMES = SKIP_BASENAMES
STRUCTURED_SUFFIXES = STRUCTURED_SUFFIXES
STRUCTURED_MAX_BYTES = STRUCTURED_MAX_BYTES
OUT_REL = OUT_REL

