"""Shared constants for AUD-0086 shell-quoting hazard census."""
from __future__ import annotations

import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0086"
OUT_REL = "command-center/audit/AUD-0086-shell-quoting-hazard-census.json"
SCHEMA_REL = "command-center/schema/audit-finding.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0086 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Which scripted or generated command bodies in the codebase contain an "
    "apostrophe, a heredoc, a process substitution, or a caret that would be "
    "mangled by the shell that actually runs them?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0086/probe1_pattern_census.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0086/probe2_roundtrip.py"
)
SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        ".bin",
        ".venv",
        "venv",
        "runtime",
        "ovh-monitor",
        "delivery-pull",
        "error-pull",
        ".cache",
        ".grok",
        "captures",
        "_install",
        "_scratch",
        "extracted",
        "extracted-delta",
    }
)
SCAN_SUFFIXES = frozenset(
    {
        ".py",
        ".sh",
        ".bash",
        ".zsh",
        ".ps1",
        ".psm1",
        ".cmd",
        ".bat",
        ".yml",
        ".yaml",
    }
)
SHELL_SUFFIXES = frozenset(
    {".sh", ".bash", ".zsh", ".ps1", ".psm1", ".cmd", ".bat"}
)
SELF_PREFIX = "command-center/p2-wave/probes/AUD-0086/"
MAX_FILE_BYTES = 2 * 1024 * 1024


def relpath(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def is_self(rel: str) -> bool:
    r = rel.replace("\\", "/")
    return r.startswith(SELF_PREFIX) or r == OUT_REL
