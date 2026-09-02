#!/usr/bin/env python3
"""Catalog constants for AUD-0034."""
from __future__ import annotations

UNIT_ID = "AUD-0034"
OUTPUT_REL = "command-center/audit/AUD-0034-option-id-crossref-resolution.json"
SCHEMA_REL = "command-center/schema/audit-finding.schema.json"
CATALOG_SENTINEL = (
    "SUCCESS:AUD-0034 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "For each of the 58 unsettled bare M-NN references in docs 16, 18 and 19, "
    "and every M-NN token elsewhere on disk, which of the four known namespaces "
    "does it belong to - or is it genuinely undecidable from context?"
)
TITLE = "Option-ID cross-reference resolution across the whole corpus"

# 31 historically colliding ids: numbers that existed as bare M-NN in both
# the option-universe family M and the pre-fix architecture-candidate cards.
HISTORICAL_COLLISION_IDS = [f"M-{n}" for n in range(1, 32)]

OPTION_IDS = [f"M-{n}" for n in range(1, 34)]  # family M, 33 ids
MECH_IDS = [f"MECH-{n}" for n in range(1, 39)]  # 38 post-fix mechanism cards
PRE_FIX_MECH_IDS = [f"M-{n}" for n in range(1, 39)]

NS_OPTION = "option-universe"
NS_MECH = "architecture-mechanisms"
NS_WAVE3 = "wave3-deliverable"
NS_WAVE1 = "wave1-mission"

CLASS_ONE = "RESOLVES-ONE"
CLASS_MANY = "RESOLVES-MANY"
CLASS_NONE = "RESOLVES-NONE"
CLASS_UNDECIDABLE = "UNDECIDABLE"
CLASS_MENTION = "MENTION"

MEANING = {
    NS_OPTION: "option-universe family-M card",
    NS_MECH: "architecture-candidate mechanism card (post-fix MECH-NN; pre-fix M-NN)",
    NS_WAVE3: "wave-3 Research Harness deliverable (M-16)",
    NS_WAVE1: "wave-1 mission-grade (M-1 / M-3)",
}

# Catalog cited source docs. These are the files whose absence forces the
# disclosed fixture reconstruction. A related command-center artifact (the
# 2026-08-09 OPTION-ID-RESOLUTION measurement) may exist without invalidating
# that reconstruction.
LIVE_SOURCE_PATHS = [
    "07-OPTION-UNIVERSE.md",
    "07-OPTION-UNIVERSE.json",
    "13-ARCHITECTURE-CANDIDATES.md",
    "16-GRILL-QUEUE.md",
    "17-DECISION-LOG.md",
    "18-OPEN-UNKNOWNS-AND-PROBES.md",
    "19-SUBSTANCE-AUDIT-BLUEPRINTS.md",
    "wave3/ast-cc/skills/deep-research/SKILL.md",
    "wave1/REGISTER.md",
]
LIVE_RELATED_PATHS = [
    "command-center/OPTION-ID-RESOLUTION.json",
]
LIVE_CANDIDATE_PATHS = LIVE_SOURCE_PATHS + LIVE_RELATED_PATHS

DOC16_REL = "16-GRILL-QUEUE.md"
DOC18_REL = "18-OPEN-UNKNOWNS-AND-PROBES.md"
DOC19_REL = "19-SUBSTANCE-AUDIT-BLUEPRINTS.md"
UNSETTLED_DOCS = (DOC16_REL, DOC18_REL, DOC19_REL)
EXPECTED_UNSETTLED = 58

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0034/probe1_mechanical_resolver.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0034/probe2_undecidable_side_by_side.py"
)
