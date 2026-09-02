"""SYN-0017 catalog contract constants (single source)."""
from __future__ import annotations

UNIT_ID = "SYN-0017"
OUTPUT_REL = "command-center/synthesis/SYN-0017.mechanism-dedup.json"
SCHEMA_REL = "command-center/schema/dedup-report.schema.json"
SENTINEL = (
    "SUCCESS:SYN-0017 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and all three planted mutants "
    "were caught and no distinct pair was collapsed. Any other terminal state "
    "is FAILED:SYN-0017 <classification> with the diagnostic tail attached."
)
QUESTION = (
    "Question (spec lens 3, _USER-PROMPTS.md:11092): do two synthesis findings "
    "or recommendations describe the SAME mechanism in different wording? "
    "Target: run two mechanically different detectors (lexical near-duplicate "
    "and embedding similarity) over the synthesis findings, collapse confirmed "
    "duplicates, and prove both detectors on planted mutants."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0017/probe1_planted_mutants.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0017/probe2_distinct_and_anchor_union.py"
)
LEXICAL_THRESHOLD = 0.48
EMBEDDING_THRESHOLD = 0.58
EMBED_DIM = 384
SYN_0011_REL = "command-center/synthesis/SYN-0011.adjudications.json"
CLAIM_REGISTRY_REL = "command-center/CLAIM-REGISTRY.json"
CC_0020_REL = "command-center/receipts/CC-0020.json"
UNIT_ID = UNIT_ID
OUTPUT_REL = OUTPUT_REL
SCHEMA_REL = SCHEMA_REL
P1 = P1
P2 = P2
EMBED_DIM = EMBED_DIM
