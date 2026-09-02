"""Repo paths and probe commands for WFA-0097."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "WFA-0097"
OUT_REL = "command-center/wfa/WFA-0097-differ-scope-disclosure.json"
SCHEMA_REL = "command-center/p2-wave/probes/WFA-0097/audit-report.schema.json"
CATALOG_SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/AuditReport"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0097/probe1_lint_planted_omission.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0097/probe2_envelope_and_scope.py"
)
CATALOG_SENTINEL = "SUCCESS:WFA-0097"
COMPLETION_SENTINEL = (
    "SUCCESS:WFA-0097 emitted only when the artifact at output_path exists, "
    "is non-empty, parses, every zero-duplicates verdict carries an adjacent "
    "machine-readable scope object, the planted omission lint fires, and each "
    "undetectable class names a settling experiment. Any other terminal state "
    "is FAILED:WFA-0097 <classification> with the diagnostic tail attached."
)
QUESTION = (
    "What class of duplicate does the combined lexical, embedding and "
    "structural detection provably NOT detect, and does every emitted "
    "no-duplicates verdict carry that scope statement adjacent to the claim "
    "rather than in a trailing limitations section?"
)
UPSTREAM = [
    "command-center/wfa/WFA-0007-lexical-duplicate-scan.json",
    "command-center/wfa/WFA-0008-embedding-duplicate-rescan.json",
    "command-center/wfa/WFA-0094-semantic-diff-engine.json",
    "command-center/wfa/WFA-0096-differ-mutant-control.json",
    "command-center/wfa/schema/wfa-schema-pack.json",
]
