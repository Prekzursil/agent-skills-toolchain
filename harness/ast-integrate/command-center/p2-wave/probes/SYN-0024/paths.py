"""Stable paths and catalog strings for SYN-0024."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "SYN-0024"
OUT_REL = "command-center/receipts/SYN-0024.json"
SCHEMA_REL = "command-center/schema/negative-evidence-audit.schema.json"
SYNTHESIS_REL = "command-center/synthesis/SYN-0008.candidate-syntheses.json"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"

CATALOG_SENTINEL = (
    "SUCCESS:SYN-0024 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the survival rate is "
    "published with both denominators and every drop has a reason. Any other "
    "terminal state is FAILED:SYN-0024 <classification> with the diagnostic "
    "tail attached."
)

QUESTION = (
    "Question: how much of the negative, null and contradictory evidence "
    "collected in Phase 2 and Phase 10 survives into the synthesis? Count "
    "negative-result records at source and in the synthesis, and require a "
    "written reason for every one that did not survive."
)

PIN_REFUTED_ID = "NEG-PIN-REFUTED-001"

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0024/probe1_known_present.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0024/probe2_planted_drop.py"
)

FIXTURE_B03 = HERE / "fixtures" / "source" / "b03-contradiction-hunt.json"
FIXTURE_B08 = HERE / "fixtures" / "source" / "b08-red-and-survivors.json"
FIXTURE_SYN = HERE / "fixtures" / "synthesis" / "candidate.json"

SOURCE_RULE = (
    "A polarity-record is a JSON object that carries a stable identity in "
    "id|claim_id|record_id|test_id|mutant_id AND a polarity field in "
    "verdict|polarity|test_result|mutant_status. The work-unit `state` field "
    "is never polarity. Negative values (case-insensitive): REFUTED, "
    "CONTRADICTS, CONTRADICTION, NEGATIVE, NEGATIVE-RESULT, NULL, NULL-RESULT, "
    "FAILED, FAIL, RED, REGRESSED, SURVIVOR, MUTATION-SURVIVOR. Live roots "
    "are catalog output_path for RES phase-2 (B03) and TST phase-10 (B08) "
    "plus command-center/research and command-center/phase10. Fixture roots "
    "are probes/SYN-0024/fixtures/source."
)
SYNTHESIS_RULE = (
    "The same polarity-record rule applied to candidate syntheses: live file "
    "command-center/synthesis/SYN-0008.candidate-syntheses.json and "
    "command-center/synthesis/**, plus the fixture candidate. A source "
    "negative survives only when a synthesis record with the SAME id still "
    "has negative polarity. Identity is the id string, never title similarity."
)
IDENTITY_RULE = (
    "Join key is the record id string. Two records with similar titles and "
    "distinct ids are distinct; title similarity is not a join."
)
