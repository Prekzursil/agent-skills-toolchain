"""AUD-0011 paths and catalog constants."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0011"
OUT_REL = "command-center/audit/AUD-0011-rules-provenance-adjudication.json"
SCHEMA_REL = "command-center/schema/audit-drift.schema.json"
FIX = HERE / "fixtures"
REPO_RULES = FIX / "repo" / "rules"
LIVE_RULES = FIX / "live" / "rules"
LEDGER_REL = FIX / "committer-ledger.json"
CATALOG_SENTINEL = (
    "SUCCESS:AUD-0011 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "For each of the 28 rules files whose repo and live copies differ in real "
    "content, which side is AUTHORITATIVE — decided by commit time versus live "
    "mtime plus a content read, not by size?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0011/probe1_commit_vs_mtime.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0011/probe2_semantic_hunks.py"
)

# Catalog-pinned live-larger names and byte deltas (live - repo).
LIVE_LARGER = (
    ("common/owner-ops-authorization.md", 1001, "owner-ops-authorization"),
    ("common/performance.md", 178, "performance"),
    ("common/security.md", 97, "security"),
)

# Catalog-cited repo-larger pairs (repo_bytes, live_bytes) plus 21 fillers.
REPO_LARGER_EXACT = (
    ("common/agents.md", 2052, 314),
    ("common/hooks.md", 4828, 849),
    ("common/ci-hygiene.md", 8219, 4420),
)

IDENTICAL = (
    "common/logging.md",
    "project/owners.md",
    "project/branching.md",
    "project/secrets-policy.md",
    "common/testing.md",
)

HOST_CANDIDATES = (
    REPO / "rules",
    Path.home() / ".claude" / "rules",
    Path.home() / ".claude" / "rules",
    Path("/root/.claude/rules"),
    Path("/root/.claude/rules"),
    Path("/Users/Prekzursil/.claude/rules"),
    Path("C:/Users/Prekzursil/.claude/rules"),
    Path("C:/Users/Prekzursil/source/ast-integrate/rules"),
)
