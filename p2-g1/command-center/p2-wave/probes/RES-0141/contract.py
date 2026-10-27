"""RES-0141 catalog contract constants. No detector logic."""
from __future__ import annotations

UNIT_ID = "RES-0141"
OUTPUT_REL = (
    "command-center/research/sources-frontier/"
    "RES-0141-breaking-change-phrase-detection.json"
)
SCHEMA_REL = "command-center/schema/measurement-run.schema.json"
SENTINEL = "SUCCESS:RES-0141"
TITLE = "Detect breaking changes from release-note prose across the dependency ecosystem"
QUESTION = (
    "Which lexical and structural signals in changelogs actually predict a "
    "breaking change - a semver-major bump, a BREAKING CHANGE footer, a "
    "removal verb, a deprecation-then-removal pair - and what precision/"
    "recall does the best combination achieve on a hand-labelled set of "
    "100 real release notes?"
)
N_NOTES = 100
N_CONTROL_NEGATIVES = 20
N_CONTROL_NEGATIVES = N_CONTROL_NEGATIVES
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0141/probe1_labelled_set_precision_recall.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0141/probe2_negative_control_silence.py"
)
SHERMAN_KENT = {
    "almost-certain": (0.87, 0.99),
    "likely": (0.55, 0.80),
    "roughly-even": (0.40, 0.60),
    "unlikely": (0.13, 0.40),
    "remote": (0.01, 0.13),
}
SIGNAL_IDS = (
    "semver_major_bump",
    "breaking_change_footer",
    "removal_verb",
    "deprecation_then_removal",
)
REVIEWER_ID = "RES-0141-probe2-negative-control-silence"
