"""CNF-0102 contract constants. Sentinel text is the catalog completion_sentinel."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

UNIT_ID = "CNF-0102"
OUTPUT_REL = "command-center/confirmation/CNF-0102-bundle-content-audit.json"
SCHEMA_REL = "command-center/schema/bundle-audit.schema.json"
RULES_REL = "command-center/p2-wave/probes/CNF-0102/inclusion_rules.json"
CANDIDATE_ZIP_REL = (
    "command-center/p2-wave/probes/CNF-0102/fixtures/candidate-shipped.zip"
)
POLLUTED_ZIP_REL = (
    "command-center/p2-wave/probes/CNF-0102/fixtures/deliberate-violation.zip"
)
PROOF_ZIP_REL = (
    "command-center/p2-wave/probes/CNF-0102/fixtures/enumeration-proof.zip"
)

SENTINEL = (
    "SUCCESS:CNF-0102 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the listing was enumerated "
    "from the artifact itself and the deliberate-violation control was flagged. "
    "Any other terminal state is FAILED:CNF-0102 <classification> with the "
    "diagnostic tail attached."
)

QUESTION = (
    "What is actually inside the shipped bundle? Enumerate every entry, and "
    "answer: does it contain repository metadata, caches, logs, transcripts, "
    "credential-shaped files, or any file above the declared size budget - "
    "and what is the total uncompressed size versus the declared budget? "
    "Spec line 10842 forbids shipping these."
)

EXTRA_MEMBER = "stray/not-in-allowlist.txt"
PLANTED_GIT = ".git/config"
PLANTED_ENV = ".env"
PLANTED_OVERSIZE = "blob.bin"

# Body used only inside the polluted zip. Auditor must never copy it into
# reports. Probes assert absence; they must not print this string.
PLANTED_CREDENTIAL_BODY = "PLANTED_CANARY_BODY_OMIT_CNF0102"

P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0102/probe1_enumerate_artifact.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0102/probe2_deliberate_violation.py"
)
