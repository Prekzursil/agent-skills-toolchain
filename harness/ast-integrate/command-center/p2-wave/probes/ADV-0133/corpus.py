"""ADV-0133 constants, premise inventory, and path candidates."""
from __future__ import annotations

UNIT_ID = "ADV-0133"
OUT_REL = "command-center/adversarial/ADV-0133-premise-blast-radius.json"
SCHEMA_REL = "command-center/schema/blast-radius.schema.json"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
AUD0075_REL = "command-center/audit/AUD-0075-stale-premise-sweep.json"
ADV0134_REL = "command-center/adversarial/ADV-0134-supersession-integrity.json"
EVENTS_REL = "command-center/events/EVENTS.jsonl"
MANIFEST_REL = "command-center/ARTIFACT-MANIFEST.json"

SENTINEL = (
    "SUCCESS:ADV-0133 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every refuted premise has "
    "a three-join closure set with each member marked RE-DERIVED, "
    "CONFIRMED-UNAFFECTED or OPEN, and the M-NN worked case reaches beyond "
    "its source document. Any other terminal state is FAILED:ADV-0133 "
    "<classification> with the diagnostic tail attached."
)

QUESTION = (
    "For each premise this program has REFUTED, what is the complete set of "
    "artifacts, work units, decisions, dependency edges and downstream "
    "conclusions that were authored while it was believed - and has each one "
    "been re-derived or explicitly confirmed unaffected?"
)

SOURCE_DOC = "17-DECISION-LOG.md"
PINNED_BRIEF = "pinned-program-brief"
WORKED_PREMISE_ID = "P-MNN-COLLISION-LIVE"
CONFIRMED_PREMISE_ID = "P-CATALOG-EXISTS"

DECISION_CANDIDATES = (
    "17-DECISION-LOG.md",
    "command-center/17-DECISION-LOG.md",
    "docs/17-DECISION-LOG.md",
    "platform/corpus/17-DECISION-LOG.md",
)

BRIEF_CANDIDATES = (
    "PROGRAM-BRIEF.md",
    "command-center/PROGRAM-BRIEF.md",
    "PINNED-BRIEF.md",
    "command-center/PINNED-PROGRAM-BRIEF.md",
    "command-center/PINNED-BRIEF.md",
)

# Canonical token plus stated paraphrases of the live-collision claim.
MNN_NEEDLES = (
    "31-way M-NN",
    "31-way option-id collision",
    "M-NN option-id collision",
    "31-way collision",
    "Queued as P2-09",
    "31 option IDs resolve to two unrelated meanings",
    "F-B-02",
)

REFUTATION_MARKERS = (
    "collision count is now 0",
    "live collision count is 0",
    "literal collision count is now 0",
    "re-prefix was applied",
    "re-prefixed to MECH-NN",
    "re-prefix was already applied",
    "holds zero bare M-NN",
    "zero bare M-NN tokens",
    "contains zero MECH tokens",
    "MECH-NN since 2026-08-07",
)

LIVE_AS_CURRENT_MARKERS = (
    "as a live blocker",
    "as still-live",
    "pins a 31-way",
)

UNAFFECTED_MARKERS = (
    "NFC/NFD",
    "byte level rather than the namespace level",
)

# Window from catalog ground: present-tense decision-log assertion versus
# the 2026-08-07 18:41 MECH-NN re-prefix that refuted a live 31-way collision.
FIRST_ASSERTED = "2026-08-01T00:00:00Z"
REFUTED_AT = "2026-08-07T18:41:00Z"

STATUSES = frozenset({"RE-DERIVED", "CONFIRMED-UNAFFECTED", "OPEN"})

SKIP_DIR_PARTS = frozenset(
    {
        "__pycache__",
        ".git",
        "node_modules",
        "ADV-0133",
    }
)

PROBE1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0133/probe1_worked_case.py"
)
PROBE2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0133/probe2_controls.py"
)
